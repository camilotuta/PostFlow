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
import requests
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from flask import (
    Flask, request, jsonify, render_template,
    send_from_directory, abort, redirect, session, Response
)
from flask_cors import CORS
from werkzeug.utils import secure_filename

import config
from database import db, Video, Post
from services.hashtag_service   import HashtagService
from services.scheduler_service import SchedulerService

# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

COL_TZ = ZoneInfo(config.TIMEZONE)

# ──────────────────────────────────────────────────────────────
#   APP FACTORY
# ──────────────────────────────────────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    @app.route('/favicon.ico')
    def favicon():
        return '', 204


    # Config
    app.config["SECRET_KEY"]          = config.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"]  = config.MAX_VIDEO_MB * 1024 * 1024
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.after_request
    def add_no_cache_headers(response):
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # DB
    db.init_app(app)
    with app.app_context():
        db.create_all()
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)

    # Servicios
    hashtag_svc   = HashtagService()
    scheduler_svc = SchedulerService()
    scheduler_svc.start(app)

    # ──────────────────────────────────────────────────────────
    #  RUTAS PRINCIPALES
    # ──────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/auth/tiktok")
    def auth_tiktok():
        # Iniciar flujo OAuth con TikTok
        state = secrets.token_urlsafe(32)
        session['oauth_state'] = state
        
        # URL de autorización de TikTok
        auth_params = {
            'client_key': config.BRANDS['gymark']['tiktok_client_key'],
            'scope': 'user.info.profile,user.info.stats,video.list,video.upload',
            'response_type': 'code',
            'redirect_uri': f"{config.PUBLIC_BASE_URL}/callback",
            'state': state
        }
        
        # Para sandbox, usar endpoint de sandbox
        auth_url = f"https://sandbox-open-api.tiktok.com/auth/authorize/?{urlencode(auth_params)}"
        return redirect(auth_url)

    @app.route("/callback")
    def oauth_callback():
        # Manejar callback OAuth de TikTok
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")
        
        # Verificar estado para seguridad
        if not state or state != session.get('oauth_state'):
            return "<h2>Error OAuth</h2><p>Estado inválido. Posible ataque CSRF.</p>", 400
        
        if error:
            return f"<h2>Error OAuth</h2><p>Error: {error}</p><p>Descripción: {request.args.get('error_description', 'Sin descripción')}</p>", 400
        
        if not code:
            return "<h2>Error OAuth</h2><p>No se recibió código de autorización.</p>", 400
        
        # Intercambiar código por tokens
        try:
            token_data = {
                'client_key': config.BRANDS['gymark']['tiktok_client_key'],
                'client_secret': config.BRANDS['gymark']['tiktok_client_secret'],
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': f"{config.PUBLIC_BASE_URL}/callback"
            }
            
            # Para sandbox, usar endpoint de sandbox
            response = requests.post(
                'https://sandbox-open-api.tiktok.com/oauth/token/',
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code == 200:
                tokens = response.json()
                access_token = tokens.get('access_token')
                open_id = tokens.get('open_id')
                
                if access_token and open_id:
                    # Mostrar tokens para copiar al .env
                    file_path = "C:/Users/tutaa/Workspace/Python/Projects/Subir Videos/.env"
                    return f"""<h2>🎉 OAuth Exitoso!</h2>
                    <p><strong>Copia estos valores a tu archivo .env:</strong></p>
                    <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px;">
GYMARK_TIKTOK_ACCESS_TOKEN={access_token}
GYMARK_TIKTOK_OPEN_ID={open_id}
                    </pre>
                    <p><strong>Archivo:</strong> <code>{file_path}</code></p>
                    <p><a href="/">← Volver a la aplicación</a></p>
                    <script>console.log('Access Token:', '{access_token}'); console.log('Open ID:', '{open_id}');</script>
                    """
                else:
                    return f"<h2>Error OAuth</h2><p>Tokens faltantes en respuesta: {tokens}</p>", 400
            else:
                return f"<h2>Error OAuth</h2><p>Error del servidor: {response.status_code}</p><p>Respuesta: {response.text}</p>", 400
                
        except Exception as e:
            return f"<h2>Error OAuth</h2><p>Excepción: {str(e)}</p>", 500

    @app.route("/tiktokvMpBF2nnx9wF8HkcdB6FQfB8ksMO9Isq.txt")
    def tiktok_verification():
        # TikTok domain verification file - serve from static
        return send_from_directory("static", "tiktokvMpBF2nnx9wF8HkcdB6FQfB8ksMO9Isq.txt", mimetype='text/plain')

    @app.route("/api/brands", methods=["GET"])
    def list_brands():
        from config import BRANDS, BRAND_CATEGORIES
        result = []
        for key, cfg in BRANDS.items():
            result.append({
                "key":        key,
                "label":      cfg["label"],
                "color":      cfg["color"],
                "platforms":  cfg["platforms"],
                "categories": BRAND_CATEGORIES.get(key, []),
            })
        return jsonify(result)

    # ── Videos ────────────────────────────────────────────────

    @app.route("/api/videos", methods=["GET"])
    def list_videos():
        videos = Video.query.order_by(Video.uploaded_at.desc()).all()
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
            return jsonify({"error": f"Formato no permitido. Usa: {', '.join(config.ALLOWED_EXTENSIONS)}"}), 400

        unique_name = f"{uuid.uuid4().hex}.{ext}"
        file_path   = os.path.join(config.UPLOAD_DIR, unique_name)
        file.save(file_path)

        file_size = os.path.getsize(file_path)
        duration  = _get_video_duration(file_path)
        thumbnail = _generate_thumbnail(file_path, unique_name)
        brand     = request.form.get("brand", "gymark")
        category_id = request.form.get("category_id", "")
        if brand not in config.BRANDS:
            brand = "gymark"

        if not category_id and brand == "tatuct":
            category_id = "gaming"
        brand_categories = config.BRAND_CATEGORIES.get(brand, [])
        allowed_categories = set(brand_categories)
        if category_id and category_id not in allowed_categories:
            category_id = brand_categories[0] if brand_categories else ""

        video = Video(
            filename      = unique_name,
            original_name = secure_filename(file.filename),
            brand         = brand,
            file_path     = file_path,
            file_size     = file_size,
            duration      = duration,
            thumbnail     = thumbnail,
            category_id   = category_id,
        )
        db.session.add(video)
        db.session.commit()

        logger.info(f"Video subido: {unique_name} ({round(file_size/1e6, 1)} MB)")
        return jsonify(video.to_dict()), 201

    @app.route("/api/videos/<int:video_id>", methods=["DELETE"])
    def delete_video(video_id):
        video = Video.query.get_or_404(video_id)
        # Eliminar archivo físico
        if os.path.exists(video.file_path):
            os.remove(video.file_path)
        if video.thumbnail:
            thumb_path = os.path.join(config.UPLOAD_DIR, "thumbs", video.thumbnail)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        db.session.delete(video)
        db.session.commit()
        return jsonify({"message": "Video eliminado"})

    # ── AI Auto-Generate ──────────────────────────────────────
    @app.route("/api/ai/generate", methods=["POST"])
    def ai_generate():
        data = request.json
        if not data or "video_id" not in data:
            return jsonify({"error": "Falta video_id"}), 400
        
        video = Video.query.get(data["video_id"])
        if not video:
            return jsonify({"error": "Video no encontrado"}), 404
        
        brand = data.get("brand", video.brand)
        if brand not in config.BRANDS:
            return jsonify({"error": f"Marca inválida: {brand}"}), 400

        category_id = str(data.get("category_id", "") or "").strip()
        brand_categories = config.BRAND_CATEGORIES.get(brand, [])
        allowed_categories = set(brand_categories)

        if not category_id and brand == "tatuct":
            category_id = "gaming"
        if category_id and category_id not in allowed_categories:
            return jsonify({"error": f"Categoría '{category_id}' no permitida para la marca {brand}"}), 400

        try:
            from services.ai_service import AIService
            ai_svc = AIService()
            
            # Use real absolute path
            real_path = os.path.abspath(video.file_path)
            
            if not os.path.exists(real_path):
                return jsonify({"error": "El archivo de video físico no existe."}), 404
            
            result = ai_svc.generate_metadata(real_path, brand, category_id)
            video.ai_title = result.get("titulo", "")
            video.ai_description = result.get("descripcion", "")
            video.ai_hashtags = json.dumps(result.get("hashtags", []))
            resolved_category = str(result.get("category_id") or category_id or "").strip()
            if resolved_category and resolved_category not in allowed_categories:
                resolved_category = brand_categories[0] if brand_categories else ""

            video.brand = brand
            video.category_id = resolved_category or None
            db.session.commit()
            payload = dict(result)
            payload["brand"] = video.brand
            payload["category_id"] = video.category_id
            return jsonify(payload)
            
        except Exception as e:
            logger.error(f"Error AI: {e}")
            err = str(e)
            low = err.lower()
            if "429" in low or "quota" in low or "resourceexhausted" in low or "exceeded your current quota" in low:
                retry_after = None
                match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err, re.IGNORECASE)
                if not match:
                    match = re.search(r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s", err, re.IGNORECASE)
                if match:
                    try:
                        retry_after = int(float(match.group(1)))
                    except Exception:
                        retry_after = None
                payload = {"error": err}
                if retry_after is not None:
                    payload["retry_after"] = retry_after
                return jsonify(payload), 429
            return jsonify({"error": err}), 500

    # ── Posts ─────────────────────────────────────────────────

    @app.route("/api/posts", methods=["GET"])
    def list_posts():
        status   = request.args.get("status")
        platform = request.args.get("platform")
        q = Post.query.order_by(Post.scheduled_at.asc())
        if status:
            q = q.filter(Post.status == status)
        if platform:
            q = q.filter(Post.platform == platform)
        return jsonify([p.to_dict() for p in q.all()])

    @app.route("/calendar.ics", methods=["GET"])
    def calendar_ics():
        posts = (
            Post.query.filter(Post.status.in_(["scheduled", "posting", "published"]))
            .order_by(Post.scheduled_at.asc())
            .all()
        )

        def esc(value: str) -> str:
            return (
                (value or "")
                .replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\n", "\\n")
            )

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Gymark//Subir Videos//ES",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Gymark Publicaciones",
            "X-WR-TIMEZONE:America/Bogota",
        ]

        now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        for post in posts:
            local_dt = post.scheduled_at.replace(tzinfo=COL_TZ)
            start_utc = local_dt.astimezone(ZoneInfo("UTC"))
            end_utc = start_utc + timedelta(minutes=30)

            summary = f"{post.title} [{post.platform.upper()}]"
            description = f"Marca: {post.brand}\\nEstado: {post.status}"
            if post.description:
                description += f"\\n{post.description}"

            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:post-{post.id}@gymark.local",
                    f"DTSTAMP:{now_utc}",
                    f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
                    f"SUMMARY:{esc(summary)}",
                    f"DESCRIPTION:{esc(description)}",
                    "END:VEVENT",
                ]
            )

        lines.append("END:VCALENDAR")
        ics_content = "\r\n".join(lines) + "\r\n"

        return Response(
            ics_content,
            mimetype="text/calendar",
            headers={"Content-Disposition": "inline; filename=gymark-calendar.ics"},
        )

    @app.route("/api/posts/schedule", methods=["POST"])
    def schedule_post():
        data = request.get_json(force=True)

        # Validación
        required = ["video_id", "platforms", "title", "content_type"]
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Faltan campos: {', '.join(missing)}"}), 400

        video = Video.query.get(data["video_id"])
        if not video:
            return jsonify({"error": "Video no encontrado"}), 404

        brand        = data.get("brand", "gymark")
        platforms    = data["platforms"]    # list
        title        = data["title"].strip()
        description  = data.get("description", "").strip()
        content_type = data["content_type"]
        custom_tags  = data.get("custom_hashtags") or data.get("hashtags") or []
        auto_time    = data.get("auto_time", True)
        manual_dt    = data.get("scheduled_at")        # "2025-12-25T10:00"

        if not custom_tags and video.ai_hashtags:
            try:
                parsed_tags = json.loads(video.ai_hashtags)
                if isinstance(parsed_tags, list):
                    custom_tags = parsed_tags
            except Exception:
                pass

        if brand not in config.BRANDS:
            return jsonify({"error": f"Marca inválida: {brand}"}), 400

        allowed_platforms = set(config.BRANDS[brand].get("platforms", []))
        invalid_platforms = [p for p in platforms if p not in allowed_platforms]
        if invalid_platforms:
            return jsonify({
                "error": f"Plataformas no permitidas para {brand}: {', '.join(invalid_platforms)}"
            }), 400

        allowed_categories = set(config.BRAND_CATEGORIES.get(brand, []))
        if content_type not in allowed_categories:
            return jsonify({
                "error": f"Categoría '{content_type}' no permitida para la marca {brand}"
            }), 400

        created_posts = []

        for platform in platforms:
            # Hashtags
            hashtags = hashtag_svc.get_hashtags(content_type, platform, custom_tags, brand=brand)

            # Horario – ahora usa content_type para el cálculo
            if auto_time:
                scheduled_at = scheduler_svc.get_next_best_time(platform, content_type=content_type, brand=brand)
            else:
                if not manual_dt:
                    return jsonify({"error": "scheduled_at requerido cuando auto_time=false"}), 400
                scheduled_at = datetime.fromisoformat(manual_dt).replace(tzinfo=COL_TZ)

            post = Post(
                video_id     = video.id,
                brand        = brand,
                platform     = platform,
                title        = title,
                description  = description,
                hashtags     = json.dumps(hashtags),
                content_type = content_type,
                scheduled_at = scheduled_at.replace(tzinfo=None),
                status       = "scheduled",
            )
            db.session.add(post)
            db.session.flush()   # get id
            created_posts.append(post.to_dict())

        db.session.commit()
        logger.info(f"Programados {len(created_posts)} posts para video {video.id} (marca: {brand})")
        return jsonify({"posts": created_posts}), 201

    @app.route("/api/posts/<int:post_id>", methods=["DELETE"])
    def cancel_post(post_id):
        post = Post.query.get_or_404(post_id)
        if post.status == "published":
            return jsonify({"error": "No se puede cancelar un post ya publicado"}), 400
        post.status = "cancelled"
        db.session.commit()
        return jsonify({"message": "Post cancelado"})

    @app.route("/api/posts/<int:post_id>/publish-now", methods=["POST"])
    def publish_now(post_id):
        """Fuerza la publicación inmediata de un post programado."""
        post = Post.query.get_or_404(post_id)
        if post.status not in ("scheduled", "failed"):
            return jsonify({"error": f"No se puede publicar con estado: {post.status}"}), 400
        # Mover scheduled_at a ahora para que el scheduler lo tome
        post.scheduled_at = datetime.now(COL_TZ).replace(tzinfo=None)
        post.status       = "scheduled"
        db.session.commit()
        # Publicar directamente en este request (sin esperar al scheduler)
        scheduler_svc._publish_post(post)
        return jsonify(post.to_dict())

    # ── Hashtags ──────────────────────────────────────────────

    @app.route("/api/hashtags/suggest", methods=["GET"])
    def suggest_hashtags():
        content_type = request.args.get("content_type", "gaming")
        platform     = request.args.get("platform", "tiktok")
        tags = hashtag_svc.get_hashtags(content_type, platform)
        return jsonify({"hashtags": tags})

    @app.route("/api/hashtags/content-types", methods=["GET"])
    def content_types():
        return jsonify(hashtag_svc.get_content_types())

    # ── Scheduling preview ────────────────────────────────────

    @app.route("/api/schedule/preview", methods=["POST"])
    def schedule_preview():
        data         = request.get_json(force=True)
        platforms    = data.get("platforms", ["tiktok", "instagram", "facebook"])
        content_type = data.get("content_type", "acc_gimnasio")
        preview      = scheduler_svc.get_schedule_preview(platforms, content_type)
        return jsonify(preview)

    # ── Status / Dashboard ────────────────────────────────────

    @app.route("/api/dashboard", methods=["GET"])
    def dashboard():
        from sqlalchemy import func
        total_videos    = Video.query.count()
        total_posts     = Post.query.count()
        published       = Post.query.filter_by(status="published").count()
        scheduled       = Post.query.filter_by(status="scheduled").count()
        failed          = Post.query.filter_by(status="failed").count()

        by_platform = db.session.query(
            Post.platform,
            func.count(Post.id).label("total"),
        ).group_by(Post.platform).all()

        # Próximos 5 posts
        upcoming = Post.query.filter(
            Post.status == "scheduled"
        ).order_by(Post.scheduled_at.asc()).limit(5).all()

        # Últimos 5 publicados
        recent = Post.query.filter(
            Post.status == "published"
        ).order_by(Post.posted_at.desc()).limit(5).all()

        return jsonify({
            "total_videos": total_videos,
            "total_posts":  total_posts,
            "published":    published,
            "scheduled":    scheduled,
            "failed":       failed,
            "by_platform":  {row.platform: row.total for row in by_platform},
            "upcoming":     [p.to_dict() for p in upcoming],
            "recent":       [p.to_dict() for p in recent],
        })

    # ── Config status ─────────────────────────────────────────

    @app.route("/api/config/status", methods=["GET"])
    def config_status():
        from config import BRANDS
        status = {"timezone": config.TIMEZONE, "brands": {}}
        for brand_key in BRANDS:
            brand_cfg = BRANDS[brand_key]
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
                brand_cfg.get("facebook_page_id")
                and brand_cfg.get("facebook_access_token")
            )
            status["brands"][brand_key] = {
                "tiktok":    tiktok_ok,
                "instagram": instagram_ok,
                "facebook":  facebook_ok,
            }
        # flatten para compatibilidad legado
        status["tiktok"] = status["brands"].get("gymark", {}).get("tiktok", False)
        status["instagram"] = status["brands"].get("gymark", {}).get("instagram", False)
        status["facebook"] = status["brands"].get("gymark", {}).get("facebook", False)
        return jsonify(status)

    # ── Archivos estáticos (thumbnails + uploads) ─────────────

    @app.route("/static/uploads/thumbs/<path:filename>")
    def serve_thumb(filename):
        thumb_dir = os.path.join(config.UPLOAD_DIR, "thumbs")
        return send_from_directory(thumb_dir, filename)

    @app.teardown_appcontext
    def shutdown_scheduler(exception=None):
        pass   # scheduler se mantiene durante toda la vida del proceso

    return app


# ──────────────────────────────────────────────────────────────
#   HELPERS
# ──────────────────────────────────────────────────────────────

def _get_video_duration(path: str) -> float:
    """Obtiene duración en segundos usando moviepy (si está disponible)."""
    try:
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(path)
        dur  = clip.duration
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


# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
