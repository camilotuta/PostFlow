"""
Subir Videos  –  Gymark / Twitch Auto-Publisher
Flask backend para publicar videos automáticamente en
TikTok, Instagram y Facebook en los mejores horarios.
"""

import os
import uuid
import json
import re
import logging
import shutil
import subprocess
import tempfile
import requests
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_from_directory,
    send_file,
    abort,
    redirect,
    session,
    Response,
)
from flask_cors import CORS
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

import config
from database import db, Video, Post
from services.hashtag_service import HashtagService
from services.scheduler_service import SchedulerService

# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

COL_TZ = ZoneInfo(config.TIMEZONE)
BRAND_TIMEZONES = {
    "milita": "America/Mexico_City",
    "escape": "America/New_York",
}


def _brand_timezone(brand: str) -> ZoneInfo:
    tz_name = BRAND_TIMEZONES.get(str(brand or "").strip().lower(), config.TIMEZONE)
    return ZoneInfo(tz_name)


def _default_content_type_for_brand(brand: str | None) -> str:
    key = str(brand or "").strip().lower()
    if key == "tatuct":
        return "gaming"
    if key == "milita":
        return "milita_beauty"
    if key == "escape":
        return "escape_proctoring"
    return "acc_gimnasio"


VIDEO_PROCESSING_LOCK = threading.Lock()
_AI_STATUS_DIR = "/tmp/postflow_ai_status"
os.makedirs(_AI_STATUS_DIR, exist_ok=True)
_VIDEO_PROCESS_LOCK_PATH = "/tmp/postflow_video_processing.lock"


def _ai_status_path(request_id: str) -> str:
    # Sanitize to prevent path traversal
    safe = "".join(c for c in request_id if c.isalnum() or c in "-_")
    return os.path.join(_AI_STATUS_DIR, f"{safe}.json")


def _set_ai_request_status(request_id: str, **payload):
    if not request_id:
        return
    path = _ai_status_path(request_id)
    try:
        # Read-modify-write with a simple rename-based atomic write
        try:
            with open(path, "r") as f:
                current = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            current = {}
        current.update(payload)
        current["updated_at"] = datetime.utcnow().isoformat() + "Z"
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(current, f)
        os.replace(tmp, path)
    except Exception:
        pass


def _clear_ai_request_status(request_id: str):
    if not request_id:
        return
    try:
        os.remove(_ai_status_path(request_id))
    except FileNotFoundError:
        pass


@contextmanager
def _video_processing_guard():
    """
    Serialize MoviePy/FFMPEG processing across all gunicorn workers.
    Falls back to in-process lock on environments without fcntl.
    """
    lock_fd = None
    try:
        import fcntl

        lock_fd = open(_VIDEO_PROCESS_LOCK_PATH, "w", encoding="utf-8")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    except ImportError:
        with VIDEO_PROCESSING_LOCK:
            yield
    finally:
        if lock_fd is not None:
            try:
                lock_fd.close()
            except Exception:
                pass


# ──────────────────────────────────────────────────────────────
#   APP FACTORY
# ──────────────────────────────────────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__)
    # Trust Railway's reverse proxy headers so request.host_url is the public domain
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    CORS(app)

    @app.route("/favicon.ico")
    def favicon():
        return "", 204

    # Config
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_VIDEO_MB * 1024 * 1024
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.after_request
    def add_no_cache_headers(response):
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # DB
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _ensure_video_schema()
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        os.makedirs(os.path.join(config.UPLOAD_DIR, "thumbs"), exist_ok=True)

    # Servicios
    hashtag_svc = HashtagService()
    scheduler_svc = SchedulerService()

    # Guard: with gunicorn multi-worker, only ONE worker should run the scheduler.
    # Use an exclusive non-blocking file lock (/tmp) — first worker wins.
    _scheduler_started = False
    try:
        import fcntl

        _sched_lock_path = "/tmp/postflow_scheduler.lock"
        _sched_lock_fd = open(_sched_lock_path, "w")
        fcntl.flock(_sched_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Keep fd open so the lock is held for the lifetime of this process
        app._scheduler_lock_fd = _sched_lock_fd
        _scheduler_started = True
    except (ImportError, OSError):
        # fcntl not available (Windows dev) or lock already held by another worker
        # Fall back: always start on Windows, skip on Linux if lock is held
        import platform

        _scheduler_started = platform.system() != "Linux"

    if _scheduler_started:
        scheduler_svc.start(app)

    def _auth_brand() -> str | None:
        brand = session.get("auth_brand")
        if brand in config.BRANDS:
            return brand
        return None

    @app.before_request
    def require_authentication():
        if request.method == "OPTIONS":
            return None

        public_endpoints = {
            "favicon",
            "terms",
            "privacy",
            "login",
            "tiktok_verification",
            "serve_thumb",
            "public_calendar_feed",
        }

        if request.endpoint in public_endpoints or request.path.startswith("/static/"):
            return None

        if _auth_brand():
            return None

        if request.path.startswith("/api/"):
            return jsonify({"error": "No autenticado"}), 401

        return redirect("/login")

    def _calendar_posts_for_brand(brand: str):
        return (
            Post.query.filter(
                Post.brand == brand,
                Post.status.in_(["scheduled", "posting", "published"]),
            )
            .order_by(Post.scheduled_at.asc())
            .all()
        )

    def _calendar_ics_response(
        brand: str, posts: list[Post], public_feed: bool = False
    ):
        brand_cfg = config.BRANDS.get(brand, {})
        calendar_label = str(brand_cfg.get("label") or brand).strip()

        brand_tz_name = BRAND_TIMEZONES.get(brand, config.TIMEZONE)
        brand_tz = ZoneInfo(brand_tz_name)

        def esc(value: str) -> str:
            return (
                (value or "")
                .replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\n", "\\n")
            )

        feed_type = "Public" if public_feed else "Privado"
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:-//PostFlow//{calendar_label}//ES",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{esc(calendar_label)} - PostFlow ({feed_type})",
            f"X-WR-TIMEZONE:{brand_tz_name}",
            "X-WR-CALDESC:Calendario de publicaciones PostFlow",
            "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
            "X-PUBLISHED-TTL:PT1H",
        ]

        now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        for post in posts:
            # scheduled_at se almacena naive en hora local de la marca
            local_dt = post.scheduled_at.replace(tzinfo=brand_tz)
            start_utc = local_dt.astimezone(ZoneInfo("UTC"))
            end_utc = start_utc + timedelta(minutes=30)

            plat = (post.platform or "").upper()
            summary = f"[{plat}] {post.title}"
            description_parts = [
                f"Plataforma: {plat}",
                f"Estado: {post.status}",
                f"Marca: {post.brand}",
            ]
            if post.description:
                description_parts.append(post.description)
            description = "\\n".join(description_parts)

            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:post-{post.id}-{brand}@postflow",
                    f"DTSTAMP:{now_utc}",
                    f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
                    f"SUMMARY:{esc(summary)}",
                    f"DESCRIPTION:{esc(description)}",
                    f"STATUS:{'CONFIRMED' if post.status == 'published' else 'TENTATIVE'}",
                    "END:VEVENT",
                ]
            )

        lines.append("END:VCALENDAR")
        ics_content = "\r\n".join(lines) + "\r\n"

        response = Response(
            ics_content,
            mimetype="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": f"inline; filename={brand}-calendar.ics",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
        return response

    # ──────────────────────────────────────────────────────────
    #  RUTAS PRINCIPALES
    # ──────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        brand = _auth_brand()
        return render_template(
            "index.html",
            auth_brand=brand,
            auth_label=config.BRANDS.get(brand, {}).get("label", ""),
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            if _auth_brand():
                return redirect("/")
            return render_template("login.html", brands=config.BRANDS, error="")

        data = request.get_json(silent=True) if request.is_json else request.form
        brand = str(data.get("brand", "")).strip()
        password = str(data.get("password", ""))
        expected_password = config.BRAND_LOGIN_PASSWORDS.get(brand)

        if not expected_password or password != expected_password:
            if request.is_json:
                return jsonify({"error": "Credenciales inválidas"}), 401
            return render_template(
                "login.html", brands=config.BRANDS, error="Credenciales inválidas"
            )

        session["auth_brand"] = brand
        if request.is_json:
            return jsonify({"message": "Login exitoso", "brand": brand})
        return redirect("/")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.pop("auth_brand", None)
        session.pop("oauth_state", None)
        session.pop("oauth_brand", None)
        return redirect("/login")

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/auth/tiktok")
    def auth_tiktok():
        brand = _auth_brand() or "gymark"
        # Iniciar flujo OAuth con TikTok
        state = secrets.token_urlsafe(32)
        session["oauth_state"] = state
        session["oauth_brand"] = brand

        # URL de autorización de TikTok
        auth_params = {
            "client_key": config.BRANDS[brand]["tiktok_client_key"],
            "scope": "user.info.profile,user.info.stats,video.list,video.upload",
            "response_type": "code",
            "redirect_uri": f"{config.PUBLIC_BASE_URL}/callback",
            "state": state,
        }

        # Para sandbox, usar endpoint de sandbox
        auth_url = f"https://sandbox-open-api.tiktok.com/auth/authorize/?{urlencode(auth_params)}"
        return redirect(auth_url)

    @app.route("/callback")
    def oauth_callback():
        # Manejar callback OAuth de TikTok
        brand = session.get("oauth_brand") or _auth_brand() or "gymark"
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        # Verificar estado para seguridad
        if not state or state != session.get("oauth_state"):
            return (
                "<h2>Error OAuth</h2><p>Estado inválido. Posible ataque CSRF.</p>",
                400,
            )

        if error:
            return (
                f"<h2>Error OAuth</h2><p>Error: {error}</p><p>Descripción: {request.args.get('error_description', 'Sin descripción')}</p>",
                400,
            )

        if not code:
            return (
                "<h2>Error OAuth</h2><p>No se recibió código de autorización.</p>",
                400,
            )

        # Intercambiar código por tokens
        try:
            token_data = {
                "client_key": config.BRANDS[brand]["tiktok_client_key"],
                "client_secret": config.BRANDS[brand]["tiktok_client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{config.PUBLIC_BASE_URL}/callback",
            }

            # Para sandbox, usar endpoint de sandbox
            response = requests.post(
                "https://sandbox-open-api.tiktok.com/oauth/token/",
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code == 200:
                tokens = response.json()
                access_token = tokens.get("access_token")
                open_id = tokens.get("open_id")

                if access_token and open_id:
                    # Mostrar tokens para copiar al .env
                    file_path = (
                        "C:/Users/tutaa/Workspace/Python/Projects/Subir Videos/.env"
                    )
                    brand_prefix = str(brand).upper()
                    return f"""<h2>🎉 OAuth Exitoso!</h2>
                    <p><strong>Copia estos valores a tu archivo .env:</strong></p>
                    <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px;">
{brand_prefix}_TIKTOK_ACCESS_TOKEN={access_token}
{brand_prefix}_TIKTOK_OPEN_ID={open_id}
                    </pre>
                    <p><strong>Archivo:</strong> <code>{file_path}</code></p>
                    <p><a href="/">← Volver a la aplicación</a></p>
                    <script>console.log('Access Token:', '{access_token}'); console.log('Open ID:', '{open_id}');</script>
                    """
                else:
                    return (
                        f"<h2>Error OAuth</h2><p>Tokens faltantes en respuesta: {tokens}</p>",
                        400,
                    )
            else:
                return (
                    f"<h2>Error OAuth</h2><p>Error del servidor: {response.status_code}</p><p>Respuesta: {response.text}</p>",
                    400,
                )

        except Exception as e:
            return f"<h2>Error OAuth</h2><p>Excepción: {str(e)}</p>", 500

    @app.route("/tiktokvMpBF2nnx9wF8HkcdB6FQfB8ksMO9Isq.txt")
    def tiktok_verification():
        # TikTok domain verification file - serve from static
        return send_from_directory(
            "static",
            "tiktokvMpBF2nnx9wF8HkcdB6FQfB8ksMO9Isq.txt",
            mimetype="text/plain",
        )

    @app.route("/api/brands", methods=["GET"])
    def list_brands():
        from config import BRANDS, BRAND_CATEGORIES

        auth_brand = _auth_brand()
        if not auth_brand:
            return jsonify([])

        cfg = BRANDS.get(auth_brand)
        if not cfg:
            return jsonify([])

        result = []
        result.append(
            {
                "key": auth_brand,
                "label": cfg["label"],
                "color": cfg["color"],
                "platforms": cfg["platforms"],
                "categories": BRAND_CATEGORIES.get(auth_brand, []),
            }
        )
        return jsonify(result)

    # ── Videos ────────────────────────────────────────────────

    @app.route("/api/videos", methods=["GET"])
    def list_videos():
        auth_brand = _auth_brand()
        videos = (
            Video.query.filter(Video.brand == auth_brand)
            .order_by(Video.uploaded_at.desc())
            .all()
        )
        return jsonify([v.to_dict() for v in videos])

    @app.route("/api/videos/upload", methods=["POST"])
    def upload_video():
        if "video" not in request.files:
            return jsonify({"error": "No se encontró el campo 'video'"}), 400

        file = request.files["video"]
        if not file.filename:
            return jsonify({"error": "Nombre de archivo vacío"}), 400

        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in config.ALLOWED_EXTENSIONS:
            return (
                jsonify(
                    {
                        "error": f"Formato no permitido. Usa: {', '.join(config.ALLOWED_EXTENSIONS)}"
                    }
                ),
                400,
            )

        unique_name = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(config.UPLOAD_DIR, unique_name)
        file.save(file_path)

        try:
            _strip_video_metadata_in_place(file_path)
        except Exception as exc:
            logger.exception("No se pudo limpiar metadatos del video subido: %s", exc)
            try:
                os.remove(file_path)
            except Exception:
                pass
            return (
                jsonify(
                    {
                        "error": "No se pudieron eliminar los metadatos del video. Intenta con otro archivo."
                    }
                ),
                400,
            )

        file_size = os.path.getsize(file_path)
        duration = _get_video_duration(file_path)
        thumbnail = _generate_thumbnail(file_path, unique_name)
        brand = _auth_brand() or "gymark"
        category_id = request.form.get("category_id", "")

        if not category_id:
            category_id = _default_content_type_for_brand(brand)
        brand_categories = config.BRAND_CATEGORIES.get(brand, [])
        allowed_categories = set(brand_categories)
        if category_id and category_id not in allowed_categories:
            category_id = brand_categories[0] if brand_categories else ""

        video = Video(
            filename=unique_name,
            original_name=secure_filename(file.filename),
            brand=brand,
            file_path=file_path,
            source_file_path=file_path,
            file_size=file_size,
            duration=duration,
            thumbnail=thumbnail,
            category_id=category_id,
        )
        db.session.add(video)
        db.session.commit()

        # Note: Auto-apply disabled to avoid thread conflicts with customize-all endpoint
        # Users can apply intro/outro manually via customize tab or use "Aplicar a todos"
        # _flask_app = app
        # _video_id = video.id
        # def _bg():
        #     with _flask_app.app_context():
        #         _v = Video.query.get(_video_id)
        #         if _v:
        #             try:
        #                 if _apply_brand_defaults_to_video(_v):
        #                     db.session.commit()
        #             except Exception:
        #                 logger.exception("No se pudo aplicar intro/outro por defecto")
        # threading.Thread(target=_bg, daemon=True).start()

        logger.info(f"Video subido: {unique_name} ({round(file_size/1e6, 1)} MB)")
        payload = video.to_dict()
        payload["metadata_stripped"] = True
        return jsonify(payload), 201

    @app.route("/api/videos/<int:video_id>", methods=["DELETE"])
    def delete_video(video_id):
        try:
            auth_brand = _auth_brand()
            if not auth_brand:
                return jsonify({"error": "No autenticado"}), 401

            video = Video.query.filter(
                Video.id == video_id, Video.brand == auth_brand
            ).first_or_404()

            _cleanup_video_assets(video)
            db.session.delete(video)
            db.session.commit()
            logger.info(f"Video {video_id} eliminado por brand {auth_brand}")
            return jsonify({"message": "Video eliminado"})
        except Exception as e:
            logger.exception(f"Error eliminando video {video_id}: %s", str(e))
            db.session.rollback()
            return jsonify({"error": f"Error eliminando video: {str(e)}"}), 500

    # ── Brand Assets (intro / outro per account) ─────────────────

    def _get_brand_asset_path(brand: str, asset_type: str) -> str | None:
        asset_dir = (
            config.VIDEO_INTROS_DIR
            if asset_type == "intro"
            else config.VIDEO_OUTROS_DIR
        )
        prefix = f"{brand}-{asset_type}."
        try:
            for fname in os.listdir(asset_dir):
                if fname.startswith(prefix):
                    return os.path.join(asset_dir, fname)
        except FileNotFoundError:
            pass
        return None

    def _brand_asset_url(path: str | None) -> str | None:
        if not path or not os.path.exists(path):
            return None
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(config.BASE_DIR))
        url_path = rel.replace(os.sep, "/")
        if url_path.startswith("static/"):
            return "/" + url_path
        return None

    def _validate_video_asset(path: str | None, label: str):
        target = str(path or "").strip()
        if not target:
            return
        if not os.path.exists(target):
            raise ValueError(f"No se encontró el archivo de {label}.")

        try:
            from moviepy.editor import VideoFileClip
        except Exception as exc:
            raise ValueError("No se pudo cargar MoviePy para validar el clip.") from exc

        clip = None
        try:
            clip = VideoFileClip(target)
            duration = float(getattr(clip, "duration", 0) or 0)
            probe_points = [0.0]
            if duration > 0.25:
                probe_points.append(min(duration - 0.05, duration * 0.5))

            for point in probe_points:
                clip.get_frame(max(0.0, float(point)))
        except Exception as exc:
            raise ValueError(
                f"El archivo de {label} está dañado o incompleto. Súbelo de nuevo en MP4/H264."
            ) from exc
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception:
                    pass

    def _brand_asset_info(brand: str, asset_type: str) -> dict:
        path = _get_brand_asset_path(brand, asset_type)
        return {
            "has_file": bool(path),
            "name": os.path.basename(path) if path else None,
            "url": _brand_asset_url(path),
        }

    @app.route("/api/brand/assets", methods=["GET"])
    def get_brand_assets():
        brand = _auth_brand()
        return jsonify(
            {
                "intro": _brand_asset_info(brand, "intro"),
                "outro": _brand_asset_info(brand, "outro"),
            }
        )

    # AI Auto-Generate
    @app.route("/api/ai/generate", methods=["POST"])
    def ai_generate():
        data = request.json
        if not data or "video_id" not in data:
            return jsonify({"error": "Falta video_id"}), 400
        auth_brand = _auth_brand()
        request_id = str(data.get("request_id", "") or "").strip()

        video = Video.query.filter(
            Video.id == data["video_id"], Video.brand == auth_brand
        ).first()
        if not video:
            return jsonify({"error": "Video no encontrado"}), 404

        brand = auth_brand

        category_id = str(data.get("category_id", "") or "").strip()
        brand_categories = config.BRAND_CATEGORIES.get(brand, [])
        allowed_categories = set(brand_categories)

        if not category_id:
            category_id = _default_content_type_for_brand(brand)
        if category_id and category_id not in allowed_categories:
            return (
                jsonify(
                    {
                        "error": f"Categoría '{category_id}' no permitida para la marca {brand}"
                    }
                ),
                400,
            )

        try:
            _set_ai_request_status(
                request_id, status="starting", model=None, phase="queued"
            )

            from services.ai_service import AIService

            ai_svc = AIService()

            # Use real absolute path
            real_path = os.path.abspath(video.get_source_path())

            if not os.path.exists(real_path):
                return jsonify({"error": "El archivo de video físico no existe."}), 404

            result = ai_svc.generate_metadata(
                real_path,
                brand,
                category_id,
                progress_callback=lambda model_name, phase: _set_ai_request_status(
                    request_id,
                    status="processing",
                    model=model_name,
                    phase=phase,
                ),
            )
            video.ai_title = result.get("titulo", "")
            video.ai_description = result.get("descripcion", "")

            ai_title_clean = str(video.ai_title or "").strip()
            if ai_title_clean:
                current_ext = os.path.splitext(str(video.filename or ""))[1].strip()
                video.original_name = (
                    f"{ai_title_clean}{current_ext}" if current_ext else ai_title_clean
                )

            resolved_category = str(
                result.get("category_id") or category_id or ""
            ).strip()
            if resolved_category and resolved_category not in allowed_categories:
                resolved_category = brand_categories[0] if brand_categories else ""

            if not resolved_category:
                resolved_category = brand_categories[0] if brand_categories else ""

            fixed_hashtags = hashtag_svc.get_hashtags(
                resolved_category,
                "tiktok",
                brand=brand,
            )

            video.brand = brand
            video.category_id = resolved_category or None
            db.session.commit()
            payload = dict(result)
            payload["hashtags"] = fixed_hashtags
            payload["brand"] = video.brand
            payload["category_id"] = video.category_id
            _set_ai_request_status(
                request_id,
                status="completed",
                model=result.get("model_used"),
                phase="done",
            )
            return jsonify(payload)

        except Exception as e:
            logger.error(f"Error AI: {e}")
            err = str(e)
            low = err.lower()
            if (
                "429" in low
                or "quota" in low
                or "resourceexhausted" in low
                or "exceeded your current quota" in low
            ):
                retry_after = None
                match = re.search(
                    r"retry_delay\s*\{\s*seconds:\s*(\d+)", err, re.IGNORECASE
                )
                if not match:
                    match = re.search(
                        r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s", err, re.IGNORECASE
                    )
                if match:
                    try:
                        retry_after = int(float(match.group(1)))
                    except Exception:
                        retry_after = None
                payload = {"error": err}
                if retry_after is not None:
                    payload["retry_after"] = retry_after
                _set_ai_request_status(
                    request_id, status="failed", model=None, phase="quota", error=err
                )
                return jsonify(payload), 429
            _set_ai_request_status(
                request_id, status="failed", model=None, phase="error", error=err
            )
            return jsonify({"error": err}), 500

    @app.route("/api/ai/status/<request_id>", methods=["GET"])
    def ai_status(request_id: str):
        auth_brand = _auth_brand()
        if not auth_brand:
            return jsonify({"error": "No autenticado"}), 401

        request_id = str(request_id or "").strip()
        try:
            with open(_ai_status_path(request_id), "r") as f:
                payload = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            payload = {}

        if not payload:
            return jsonify({"status": "unknown", "model": None, "phase": None}), 404

        return jsonify(payload)

    # ── Posts ─────────────────────────────────────────────────

    @app.route("/api/posts", methods=["GET"])
    def list_posts():
        auth_brand = _auth_brand()
        status = request.args.get("status")
        platform = request.args.get("platform")
        q = Post.query.filter(Post.brand == auth_brand).order_by(
            Post.scheduled_at.asc()
        )
        if status:
            q = q.filter(Post.status == status)
        if platform:
            q = q.filter(Post.platform == platform)
        return jsonify([p.to_dict() for p in q.all()])

    @app.route("/calendar.ics", methods=["GET"])
    def calendar_ics():
        auth_brand = _auth_brand()
        posts = _calendar_posts_for_brand(auth_brand)
        return _calendar_ics_response(auth_brand, posts, public_feed=False)

    @app.route("/calendar/feed/<brand>.ics", methods=["GET"])
    def public_calendar_feed(brand: str):
        brand = str(brand or "").strip().lower()
        if brand not in config.BRANDS:
            return abort(404)

        token = str(request.args.get("token", "")).strip()
        expected = str(config.BRAND_CALENDAR_TOKENS.get(brand, "")).strip()
        if not expected or token != expected:
            return abort(403)

        posts = _calendar_posts_for_brand(brand)
        return _calendar_ics_response(brand, posts, public_feed=True)

    @app.route("/api/calendar/feed-info", methods=["GET"])
    def calendar_feed_info():
        brand = _auth_brand() or "gymark"
        token = config.BRAND_CALENDAR_TOKENS.get(brand, "")

        # Siempre usar el host real del request – es el mismo servidor que sirve el feed
        base = request.host_url.rstrip("/")

        feed_url = f"{base}/calendar/feed/{brand}.ics?{urlencode({'token': token})}"
        webcal_url = feed_url.replace("https://", "webcal://").replace(
            "http://", "webcal://"
        )
        google_subscribe_url = (
            "https://calendar.google.com/calendar/render?"
            + urlencode({"cid": webcal_url})
        )
        return jsonify(
            {
                "brand": brand,
                "feed_url": feed_url,
                "webcal_url": webcal_url,
                "google_subscribe_url": google_subscribe_url,
            }
        )

    @app.route("/api/posts/schedule", methods=["POST"])
    def schedule_post():
        data = request.get_json(force=True)

        # Validación
        required = ["video_id", "platforms", "title"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Faltan campos: {', '.join(missing)}"}), 400

        auth_brand = _auth_brand()
        video = Video.query.filter(
            Video.id == data["video_id"], Video.brand == auth_brand
        ).first()
        if not video:
            return jsonify({"error": "Video no encontrado"}), 404

        brand = auth_brand
        platforms = data["platforms"]  # list
        title = data["title"].strip()
        description = data.get("description", "").strip()
        content_type = str(data.get("content_type", "") or "").strip()
        auto_time = data.get("auto_time", True)
        manual_dt = data.get("scheduled_at")  # "2025-12-25T10:00"

        if brand not in config.BRANDS:
            return jsonify({"error": f"Marca inválida: {brand}"}), 400

        allowed_platforms = set(config.BRANDS[brand].get("platforms", []))
        invalid_platforms = [p for p in platforms if p not in allowed_platforms]
        if invalid_platforms:
            return (
                jsonify(
                    {
                        "error": f"Plataformas no permitidas para {brand}: {', '.join(invalid_platforms)}"
                    }
                ),
                400,
            )

        if brand == "gymark":
            content_type = str(video.category_id or "").strip()
            if not content_type:
                return (
                    jsonify(
                        {
                            "error": "Este video de Gymark no tiene categoría detectada por IA. Analízalo con IA antes de programar."
                        }
                    ),
                    400,
                )
        elif not content_type:
            content_type = _default_content_type_for_brand(brand)

        allowed_categories = set(config.BRAND_CATEGORIES.get(brand, []))
        if content_type not in allowed_categories:
            return (
                jsonify(
                    {
                        "error": f"Categoría '{content_type}' no permitida para la marca {brand}"
                    }
                ),
                400,
            )

        created_posts = []
        extra_brand_day_counts: dict[str, int] = {}
        extra_platform_day_counts: dict[str, int] = {}

        for platform in platforms:
            # Hashtags
            hashtags = hashtag_svc.get_hashtags(content_type, platform, brand=brand)
            day_key = ""
            platform_day_key = ""

            # Horario – ahora usa content_type para el cálculo
            if auto_time:
                try:
                    cursor_after = None
                    for _ in range(240):
                        scheduled_at = scheduler_svc.get_next_best_time(
                            platform,
                            after=cursor_after,
                            content_type=content_type,
                            brand=brand,
                            extra_brand_day_counts=extra_brand_day_counts,
                            extra_platform_day_counts=extra_platform_day_counts,
                        )
                        day_key = scheduled_at.date().isoformat()
                        platform_day_key = f"{day_key}:{platform}"
                        allowed_slot, _ = scheduler_svc.check_daily_limits(
                            brand=brand,
                            platform=platform,
                            scheduled_at=scheduled_at,
                            extra_brand_day=extra_brand_day_counts.get(day_key, 0),
                            extra_platform_day=extra_platform_day_counts.get(
                                platform_day_key, 0
                            ),
                        )
                        if allowed_slot:
                            break
                        cursor_after = scheduled_at + timedelta(minutes=10)
                    else:
                        return (
                            jsonify(
                                {
                                    "error": f"No hay cupo disponible para {platform}. Intenta de nuevo para reprogramar en la siguiente semana."
                                }
                            ),
                            400,
                        )
                except ValueError as exc:
                    return jsonify({"error": str(exc)}), 400
            else:
                if not manual_dt:
                    return (
                        jsonify(
                            {"error": "scheduled_at requerido cuando auto_time=false"}
                        ),
                        400,
                    )
                scheduled_at = datetime.fromisoformat(manual_dt).replace(
                    tzinfo=_brand_timezone(brand)
                )

            if not day_key:
                day_key = scheduled_at.date().isoformat()
                platform_day_key = f"{day_key}:{platform}"
            allowed_slot, limit_error = scheduler_svc.check_daily_limits(
                brand=brand,
                platform=platform,
                scheduled_at=scheduled_at,
                extra_brand_day=extra_brand_day_counts.get(day_key, 0),
                extra_platform_day=extra_platform_day_counts.get(platform_day_key, 0),
            )
            if not allowed_slot:
                db.session.rollback()
                return jsonify({"error": limit_error}), 400

            post = Post(
                video_id=video.id,
                brand=brand,
                platform=platform,
                title=title,
                description=description,
                hashtags=json.dumps(hashtags),
                content_type=content_type,
                scheduled_at=scheduled_at.replace(tzinfo=None),
                status="scheduled",
            )
            db.session.add(post)
            db.session.flush()  # get id
            created_posts.append(post.to_dict())
            extra_brand_day_counts[day_key] = extra_brand_day_counts.get(day_key, 0) + 1
            extra_platform_day_counts[platform_day_key] = (
                extra_platform_day_counts.get(platform_day_key, 0) + 1
            )

        db.session.commit()
        logger.info(
            f"Programados {len(created_posts)} posts para video {video.id} (marca: {brand})"
        )
        return jsonify({"posts": created_posts}), 201

    @app.route("/api/posts/clear", methods=["DELETE"])
    def clear_all_posts():
        """Elimina TODOS los posts de la marca autenticada (no toca los videos)."""
        auth_brand = _auth_brand()
        if not auth_brand:
            return jsonify({"error": "No autenticado"}), 401
        deleted = Post.query.filter(Post.brand == auth_brand).delete()
        db.session.commit()
        return jsonify({"message": f"{deleted} posts eliminados", "deleted": deleted})

    @app.route("/api/posts/<int:post_id>", methods=["DELETE"])
    def cancel_post(post_id):
        auth_brand = _auth_brand()
        post = Post.query.filter(
            Post.id == post_id, Post.brand == auth_brand
        ).first_or_404()
        if post.status == "published":
            return jsonify({"error": "No se puede cancelar un post ya publicado"}), 400
        post.status = "cancelled"
        db.session.commit()
        return jsonify({"message": "Post cancelado"})

    @app.route("/api/posts/<int:post_id>/regenerate", methods=["POST"])
    def regenerate_post(post_id):
        """Regenera título y descripción con IA, y reaplica hashtags fijos.
        Acepta feedback opcional del usuario para mejorar el resultado."""
        auth_brand = _auth_brand()
        post = Post.query.filter(
            Post.id == post_id, Post.brand == auth_brand
        ).first_or_404()

        data = request.get_json(force=True) or {}
        feedback = str(data.get("feedback", "")).strip()

        video = Video.query.filter(Video.id == post.video_id).first()
        if not video:
            return jsonify({"error": "Video del post no encontrado"}), 404

        real_path = os.path.abspath(video.get_source_path())
        if not os.path.exists(real_path):
            return jsonify({"error": "Archivo de video físico no encontrado"}), 404

        try:
            from services.ai_service import AIService

            ai_svc = AIService()

            category_id = post.content_type or video.category_id or ""
            extra_ctx = (
                f"Feedback del usuario para mejorar: {feedback}" if feedback else ""
            )

            result = ai_svc.generate_metadata(
                real_path, post.brand, category_id, extra_context=extra_ctx
            )

            post.title = result.get("titulo", post.title)
            post.description = result.get("descripcion", post.description)

            platform_hashtags = hashtag_svc.get_hashtags(
                post.content_type,
                post.platform,
                brand=post.brand,
            )
            post.hashtags = json.dumps(platform_hashtags)

            db.session.commit()
            logger.info(
                f"Post {post_id} regenerado con IA (feedback: {bool(feedback)})"
            )
            return jsonify(post.to_dict())

        except Exception as e:
            logger.error(f"Error regenerando post {post_id}: {e}")
            err = str(e)
            low = err.lower()
            if "429" in low or "quota" in low or "resourceexhausted" in low:
                return jsonify({"error": err}), 429
            return jsonify({"error": err}), 500

    @app.route("/api/posts/<int:post_id>/publish-now", methods=["POST"])
    def publish_now(post_id):
        """Fuerza la publicación inmediata de un post programado."""
        auth_brand = _auth_brand()
        post = Post.query.filter(
            Post.id == post_id, Post.brand == auth_brand
        ).first_or_404()
        if post.status not in ("scheduled", "failed"):
            return (
                jsonify({"error": f"No se puede publicar con estado: {post.status}"}),
                400,
            )
        # Mover scheduled_at a ahora para que el scheduler lo tome
        post.scheduled_at = datetime.now(_brand_timezone(post.brand)).replace(
            tzinfo=None
        )
        post.status = "scheduled"
        db.session.commit()
        # Publicar directamente en este request (sin esperar al scheduler)
        scheduler_svc._publish_post(post)
        return jsonify(post.to_dict())

    @app.route("/api/posts/<int:post_id>/download-video", methods=["GET"])
    def download_post_video(post_id):
        """Descarga el archivo que se publicará para este post."""
        auth_brand = _auth_brand()
        post = Post.query.filter(
            Post.id == post_id, Post.brand == auth_brand
        ).first_or_404()
        video = Video.query.filter(
            Video.id == post.video_id, Video.brand == auth_brand
        ).first()
        if not video:
            return jsonify({"error": "Video no encontrado"}), 404

        real_path = os.path.abspath(video.get_publish_path())
        if not os.path.exists(real_path):
            return jsonify({"error": "Archivo de video no encontrado"}), 404

        base_title = (
            str(post.title or "").strip()
            or str(video.ai_title or "").strip()
            or os.path.splitext(str(video.original_name or ""))[0].strip()
            or f"video-{video.id}"
        )
        safe_title = secure_filename(base_title) or f"video-{video.id}"
        extension = (
            os.path.splitext(os.path.basename(real_path))[1].strip().lower() or ".mp4"
        )
        download_name = f"{safe_title}{extension}"

        return send_file(real_path, as_attachment=True, download_name=download_name)

    # ── Hashtags ──────────────────────────────────────────────

    @app.route("/api/hashtags/suggest", methods=["GET"])
    def suggest_hashtags():
        auth_brand = _auth_brand() or "gymark"
        default_type = _default_content_type_for_brand(auth_brand)
        content_type = request.args.get("content_type", default_type)
        platform = request.args.get("platform", "tiktok")
        allowed = set(config.BRAND_CATEGORIES.get(auth_brand, []))
        if content_type not in allowed:
            content_type = default_type
        tags = hashtag_svc.get_hashtags(content_type, platform, brand=auth_brand)
        return jsonify({"hashtags": tags})

    @app.route("/api/hashtags/content-types", methods=["GET"])
    def content_types():
        auth_brand = _auth_brand() or "gymark"
        allowed = set(config.BRAND_CATEGORIES.get(auth_brand, []))
        types = [
            ct for ct in hashtag_svc.get_content_types() if ct.get("key") in allowed
        ]
        return jsonify(types)

    # ── Scheduling preview ────────────────────────────────────

    @app.route("/api/schedule/preview", methods=["POST"])
    def schedule_preview():
        auth_brand = _auth_brand() or "gymark"
        data = request.get_json(force=True)
        allowed_platforms = set(
            config.BRANDS.get(auth_brand, {}).get("platforms", ["tiktok"])
        )
        platforms = [
            p for p in data.get("platforms", ["tiktok"]) if p in allowed_platforms
        ]
        if not platforms:
            platforms = list(allowed_platforms)

        default_type = _default_content_type_for_brand(auth_brand)
        content_type = data.get("content_type", default_type)
        if content_type not in set(config.BRAND_CATEGORIES.get(auth_brand, [])):
            content_type = default_type
        preview = scheduler_svc.get_schedule_preview(
            platforms, content_type, brand=auth_brand
        )
        return jsonify(preview)

    # ── Status / Dashboard ────────────────────────────────────

    @app.route("/api/dashboard", methods=["GET"])
    def dashboard():
        auth_brand = _auth_brand()
        from sqlalchemy import func

        total_videos = Video.query.filter(Video.brand == auth_brand).count()
        total_posts = Post.query.filter(Post.brand == auth_brand).count()
        published = Post.query.filter(
            Post.brand == auth_brand, Post.status == "published"
        ).count()
        scheduled = Post.query.filter(
            Post.brand == auth_brand, Post.status == "scheduled"
        ).count()
        failed = Post.query.filter(
            Post.brand == auth_brand, Post.status == "failed"
        ).count()

        by_platform = (
            db.session.query(
                Post.platform,
                func.count(Post.id).label("total"),
            )
            .filter(Post.brand == auth_brand)
            .group_by(Post.platform)
            .all()
        )

        # Próximos 5 posts
        upcoming = (
            Post.query.filter(Post.brand == auth_brand, Post.status == "scheduled")
            .order_by(Post.scheduled_at.asc())
            .limit(5)
            .all()
        )

        # Últimos 5 publicados
        recent = (
            Post.query.filter(Post.brand == auth_brand, Post.status == "published")
            .order_by(Post.posted_at.desc())
            .limit(5)
            .all()
        )

        return jsonify(
            {
                "total_videos": total_videos,
                "total_posts": total_posts,
                "published": published,
                "scheduled": scheduled,
                "failed": failed,
                "by_platform": {row.platform: row.total for row in by_platform},
                "upcoming": [p.to_dict() for p in upcoming],
                "recent": [p.to_dict() for p in recent],
            }
        )

    # ── Config status ─────────────────────────────────────────

    @app.route("/api/config/status", methods=["GET"])
    def config_status():
        auth_brand = _auth_brand() or "gymark"
        from config import BRANDS

        status = {"timezone": config.TIMEZONE, "brands": {}}
        brand_cfg = BRANDS.get(auth_brand, {})
        tiktok_ok = bool(
            brand_cfg.get("tiktok_client_key")
            and brand_cfg.get("tiktok_client_secret")
            and brand_cfg.get("tiktok_access_token")
            and brand_cfg.get("tiktok_open_id")
        )
        instagram_ok = bool(
            brand_cfg.get("instagram_account_id")
            and brand_cfg.get("facebook_access_token")
        )
        facebook_ok = bool(
            brand_cfg.get("facebook_page_id") and brand_cfg.get("facebook_access_token")
        )
        status["brands"][auth_brand] = {
            "tiktok": tiktok_ok,
            "instagram": instagram_ok,
            "facebook": facebook_ok,
        }
        # flatten para compatibilidad legado
        status["tiktok"] = tiktok_ok
        status["instagram"] = instagram_ok
        status["facebook"] = facebook_ok
        return jsonify(status)

    # ── Archivos estáticos (thumbnails + uploads) ─────────────

    @app.route("/static/uploads/thumbs/<path:filename>")
    def serve_thumb(filename):
        thumb_dir = os.path.join(config.UPLOAD_DIR, "thumbs")
        return send_from_directory(thumb_dir, filename)

    @app.teardown_appcontext
    def shutdown_scheduler(exception=None):
        pass  # scheduler se mantiene durante toda la vida del proceso

    return app


# ──────────────────────────────────────────────────────────────
#   HELPERS
# ──────────────────────────────────────────────────────────────


def _strip_video_metadata_in_place(path: str):
    """Reescribe el video eliminando metadatos del contenedor antes del procesamiento de IA."""
    source_path = os.path.abspath(path)
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Archivo no encontrado para limpiar metadatos: {path}")

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg no está disponible en el entorno.")

    source_dir = os.path.dirname(source_path) or "."
    suffix = os.path.splitext(source_path)[1] or ".mp4"
    fd, temp_output = tempfile.mkstemp(
        prefix="clean-meta-", suffix=suffix, dir=source_dir
    )
    os.close(fd)

    def _run_ffmpeg(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

    copy_cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        source_path,
        "-map",
        "0",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-metadata",
        "title=",
        "-metadata",
        "comment=",
        "-metadata",
        "description=",
        "-metadata",
        "copyright=",
        "-c",
        "copy",
        temp_output,
    ]

    reencode_cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        source_path,
        "-map",
        "0:v:0?",
        "-map",
        "0:a?",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-metadata",
        "title=",
        "-metadata",
        "comment=",
        "-metadata",
        "description=",
        "-metadata",
        "copyright=",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        temp_output,
    ]

    result = _run_ffmpeg(copy_cmd)
    if result.returncode != 0:
        result = _run_ffmpeg(reencode_cmd)

    if result.returncode != 0:
        try:
            os.remove(temp_output)
        except Exception:
            pass
        raise RuntimeError(
            "No se pudieron eliminar metadatos con ffmpeg. "
            + (result.stderr or "").strip()[-600:]
        )

    if not os.path.exists(temp_output) or os.path.getsize(temp_output) <= 0:
        try:
            os.remove(temp_output)
        except Exception:
            pass
        raise RuntimeError("La salida de ffmpeg quedó vacía al limpiar metadatos.")

    os.replace(temp_output, source_path)


def _get_video_duration(path: str) -> float:
    """Obtiene duración en segundos usando moviepy (si está disponible)."""
    try:
        from moviepy.editor import VideoFileClip

        clip = VideoFileClip(path)
        dur = clip.duration
        clip.close()
        return round(dur, 1)
    except Exception:
        return 0.0


def _generate_thumbnail(video_path: str, unique_name: str) -> str | None:
    """Genera un thumbnail del primer frame del video."""
    try:
        thumb_dir = os.path.join(config.UPLOAD_DIR, "thumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_name = unique_name.rsplit(".", 1)[0] + ".jpg"
        thumb_path = os.path.join(thumb_dir, thumb_name)

        from moviepy.editor import VideoFileClip

        clip = VideoFileClip(video_path)
        clip.save_frame(thumb_path, t=min(1, clip.duration - 0.1))
        clip.close()
        return f"/static/uploads/thumbs/{thumb_name}"
    except Exception:
        return None


def _ensure_video_schema():
    inspector = inspect(db.engine)
    if "videos" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("videos")}
    missing = []
    if "source_file_path" not in existing:
        missing.append("ALTER TABLE videos ADD COLUMN source_file_path VARCHAR(512)")
    if "processed_file_path" not in existing:
        missing.append("ALTER TABLE videos ADD COLUMN processed_file_path VARCHAR(512)")
    if "customization_json" not in existing:
        missing.append("ALTER TABLE videos ADD COLUMN customization_json TEXT")

    for statement in missing:
        db.session.execute(text(statement))
    if missing:
        db.session.commit()


def _form_bool(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def _store_uploaded_asset(
    uploaded_file, target_dir: str, prefix: str, allowed_extensions: set[str]
) -> str:
    if uploaded_file is None or not getattr(uploaded_file, "filename", ""):
        raise ValueError("Archivo no válido")

    filename = secure_filename(uploaded_file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not ext or ext not in allowed_extensions:
        raise ValueError(
            f"Formato no permitido. Usa: {', '.join(sorted(allowed_extensions))}"
        )

    os.makedirs(target_dir, exist_ok=True)
    disk_name = f"{prefix}-{uuid.uuid4().hex}.{ext}"
    disk_path = os.path.join(target_dir, disk_name)
    uploaded_file.save(disk_path)
    return disk_path


def _safe_remove_managed_file(path: str | None):
    txt = str(path or "").strip()
    if not txt:
        return

    managed_roots = [
        config.UPLOAD_DIR,
        config.VIDEO_CUSTOMIZATION_DIR,
    ]
    abs_path = os.path.abspath(txt)
    if not any(abs_path.startswith(os.path.abspath(root)) for root in managed_roots):
        return
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except Exception:
            pass


def _thumbnail_to_disk_path(thumbnail_url: str | None) -> str | None:
    txt = str(thumbnail_url or "").strip()
    if not txt:
        return None
    if txt.startswith("/static/"):
        rel = txt.lstrip("/").replace("/", os.sep)
        return os.path.join(config.BASE_DIR, rel)
    return txt


def _sync_video_media_fields(video: Video, active_path: str):
    active_path = os.path.abspath(str(active_path or ""))
    if not active_path or not os.path.exists(active_path):
        raise FileNotFoundError("El archivo de video resultante no existe.")

    old_thumb_disk = _thumbnail_to_disk_path(video.thumbnail)
    unique_name = os.path.basename(active_path)
    new_thumb = _generate_thumbnail(active_path, unique_name)
    if old_thumb_disk and old_thumb_disk != _thumbnail_to_disk_path(new_thumb):
        _safe_remove_managed_file(old_thumb_disk)

    video.thumbnail = new_thumb
    video.file_size = os.path.getsize(active_path)
    video.duration = _get_video_duration(active_path)


def _apply_brand_defaults_to_video(video: Video) -> bool:
    from services.video_processing_service import VideoProcessingService

    def _find_brand_asset(asset_dir: str, brand: str, asset_type: str) -> str | None:
        prefix = f"{brand}-{asset_type}."
        try:
            for fname in os.listdir(asset_dir):
                if fname.startswith(prefix):
                    return os.path.join(asset_dir, fname)
        except FileNotFoundError:
            pass
        return None

    intro_path = _find_brand_asset(config.VIDEO_INTROS_DIR, video.brand, "intro")
    outro_path = _find_brand_asset(config.VIDEO_OUTROS_DIR, video.brand, "outro")

    use_intro = bool(intro_path)
    use_outro = bool(outro_path)
    if not use_intro and not use_outro:
        return False

    output_name = f"video-{video.id}-{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(config.VIDEO_PROCESSED_DIR, output_name)

    svc = VideoProcessingService()
    svc.build_video(
        source_path=video.get_source_path(),
        output_path=output_path,
        intro_path=intro_path,
        outro_path=outro_path,
    )

    _safe_remove_managed_file(video.processed_file_path)
    video.processed_file_path = output_path
    video.customization_json = json.dumps(
        {
            "intro_enabled": use_intro,
            "intro_name": os.path.basename(intro_path) if intro_path else "",
            "outro_enabled": use_outro,
            "outro_name": os.path.basename(outro_path) if outro_path else "",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
    )
    _sync_video_media_fields(video, output_path)
    return True


def _cleanup_video_assets(video: Video):
    _safe_remove_managed_file(video.processed_file_path)
    _safe_remove_managed_file(video.get_source_path())
    _safe_remove_managed_file(_thumbnail_to_disk_path(video.thumbnail))


# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
