"""
Servicio de Scheduling Inteligente
    - Determina el próximo mejor horario para cada plataforma
    - Ejecuta los posts programados con APScheduler
    - Actualiza el estado de los posts en la base de datos
"""

import logging
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import TIMEZONE, UPLOAD_DIR, BRANDS
from database import db, Post

logger = logging.getLogger(__name__)

COL_TZ = ZoneInfo(TIMEZONE)
BRAND_TIMEZONES = {
    "milita": "America/Mexico_City",
}

SCHEDULE_SLOTS = {
    "gaming": {
        "tiktok": {
            1: ["20:00"],
            2: ["21:00"],
            3: ["19:30", "23:00"],
            4: ["20:00"],
            5: ["20:00", "22:00"],
        },
    },
    "acc_gimnasio": {
        "tiktok": {1: ["20:00"], 3: ["20:00"]},
        "instagram": {1: ["12:00", "19:00"], 3: ["12:00", "19:00"]},
        "facebook": {1: ["12:00", "19:00"], 3: ["12:00", "19:00"]},
    },
    "pilates_yoga": {
        "tiktok": {2: ["19:30"], 5: ["19:30"]},
        "instagram": {2: ["11:00", "19:00"], 5: ["11:00", "19:00"]},
        "facebook": {2: ["09:00", "19:00"], 5: ["09:00", "19:00"]},
    },
    "sup_naturales": {
        "tiktok": {1: ["20:00"], 2: ["20:00"]},
        "instagram": {1: ["11:00", "19:00"], 2: ["11:00", "19:00"]},
        "facebook": {1: ["09:00", "19:00"], 2: ["09:00", "19:00"]},
    },
    "ropa_deportiva": {
        "tiktok": {1: ["20:00"], 3: ["20:00"]},
        "instagram": {1: ["12:00", "19:00"], 3: ["12:00", "19:00"]},
        "facebook": {1: ["12:00", "19:00"], 3: ["12:00", "19:00"]},
    },
    "sup_deportivos": {
        "tiktok": {1: ["20:00"], 2: ["20:00"]},
        "instagram": {1: ["11:00", "19:00"], 2: ["11:00", "19:00"]},
        "facebook": {1: ["09:00", "19:00"], 2: ["09:00", "19:00"]},
    },
    "home_gym": {
        "tiktok": {3: ["19:30"], 4: ["19:30"]},
        "instagram": {3: ["12:00", "19:30"], 4: ["12:00", "19:30"]},
        "facebook": {3: ["12:00", "19:00"], 4: ["12:00", "19:00"]},
    },
    "milita_beauty": {
        "tiktok": {
            1: ["09:00", "13:00"],
            2: ["10:00"],
            3: ["19:30"],
            4: ["10:00", "19:30"],
            6: ["10:00"],
        },
    },
}


def _brand_timezone(brand: str) -> ZoneInfo:
    tz_name = BRAND_TIMEZONES.get(str(brand or "").lower(), TIMEZONE)
    return ZoneInfo(tz_name)


def _parse_time_slot(slot) -> tuple[int, int]:
    if isinstance(slot, int):
        return int(slot), 0

    if isinstance(slot, (tuple, list)) and len(slot) == 2:
        return int(slot[0]), int(slot[1])

    txt = str(slot or "").strip()
    if not txt:
        return 10, 0
    if ":" in txt:
        hh, mm = txt.split(":", 1)
        return int(hh), int(mm)
    return int(txt), 0


# ──────────────────────────────────────────────────────────────
class SchedulerService:

    def __init__(self, app=None):
        self.app       = app
        self._scheduler = BackgroundScheduler(timezone=TIMEZONE)
        self._started   = False

    # ─────────────────────────────────────
    #  Iniciar
    # ─────────────────────────────────────
    def start(self, app):
        self.app = app
        if not self._started:
            # Check pending posts each minute
            self._scheduler.add_job(
                self._process_due_posts,
                IntervalTrigger(minutes=1),
                id="process_due_posts",
                replace_existing=True,
            )
            self._scheduler.start()
            self._started = True
            logger.info("[Scheduler] Iniciado – revisando cada minuto.")

    def shutdown(self):
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False

    # ─────────────────────────────────────
    #  Calcular mejor horario automático
    # ─────────────────────────────────────
    def get_next_best_time(
        self,
        platform: str,
        after: datetime | None = None,
        content_type: str = "acc_gimnasio",
        brand: str = "gymark",
    ) -> datetime:
        """
        Devuelve el próximo slot óptimo para la plataforma y categoría dada.
        Si `after` es None, usa ahora en timezone de la marca.
        """
        brand_tz = _brand_timezone(brand)
        if after is None:
            now = datetime.now(brand_tz)
        elif after.tzinfo is None:
            now = after.replace(tzinfo=brand_tz)
        else:
            now = after.astimezone(brand_tz)

        cat_times = SCHEDULE_SLOTS.get(content_type, SCHEDULE_SLOTS["acc_gimnasio"])
        table = cat_times.get(platform, cat_times.get("tiktok", {}))

        # Intentar en los próximos días, respetando SOLO los días configurados
        for days_ahead in range(15):
            candidate_date = now.date() + timedelta(days=days_ahead)
            weekday        = candidate_date.weekday()  # 0=lunes
            hours = table.get(weekday, [])

            if not hours:
                continue

            for slot in hours:
                hour, minute = _parse_time_slot(slot)
                candidate = datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    hour,
                    minute,
                    0,
                    tzinfo=brand_tz,
                )
                # Mínimo 5 minutos en el futuro
                if candidate > now + timedelta(minutes=5):
                    start_of_slot = candidate.replace(tzinfo=None)
                    end_of_slot = start_of_slot + timedelta(minutes=1)
                    
                    posts_in_slot = Post.query.filter(
                        Post.platform == platform,
                        Post.brand == brand,
                        Post.status.in_(["scheduled", "posting"]),
                        Post.scheduled_at >= start_of_slot,
                        Post.scheduled_at < end_of_slot,
                    ).count()
                    
                    if posts_in_slot < 2:
                        return candidate

        # Fallback de seguridad: mañana a las 10 am
        tomorrow = now + timedelta(days=1)
        return datetime(
            tomorrow.year, tomorrow.month, tomorrow.day,
            10, 0, 0, tzinfo=brand_tz,
        )

    def get_schedule_preview(
        self,
        platforms: list[str],
        content_type: str = "acc_gimnasio",
        brand: str = "gymark",
    ) -> dict:
        """
        Devuelve los próximos 3 mejores horarios por plataforma y categoría.
        Útil para mostrar en la UI antes de confirmar.
        """
        preview = {}
        for platform in platforms:
            slots = []
            after = None
            for _ in range(3):
                slot  = self.get_next_best_time(platform, after, content_type, brand=brand)
                slots.append(slot.strftime("%A %d %b · %H:%M"))
                after = slot + timedelta(minutes=10)
            preview[platform] = slots
        return preview

    # ─────────────────────────────────────
    #  Procesar posts que ya vencieron
    # ─────────────────────────────────────
    def _process_due_posts(self):
        """Corre cada minuto. Publica los posts cuyo scheduled_at ya llegó."""
        if not self.app:
            return
        with self.app.app_context():
            for brand in BRANDS.keys():
                now_brand = datetime.now(_brand_timezone(brand)).replace(tzinfo=None)
                posts = Post.query.filter(
                    Post.status == "scheduled",
                    Post.brand == brand,
                    Post.scheduled_at <= now_brand,
                ).all()
                for post in posts:
                    self._publish_post(post)

    def _publish_post(self, post: Post):
        """Publica un post individual y actualiza su estado."""
        video     = post.video
        video_path = video.file_path
        hashtags   = post.hashtags_list()

        brand = getattr(post, "brand", "gymark") or "gymark"
        try:
            post.status = "posting"
            db.session.commit()

            result = self._simulate_publish(post=post, video_path=video_path, hashtags=hashtags)

            if result.get("success"):
                post.status           = "published"
                post.posted_at        = datetime.now(COL_TZ).replace(tzinfo=None)
                post.platform_post_id = str(result.get("publish_id") or result.get("post_id") or result.get("video_id", ""))
                logger.info(f"[Scheduler] Post {post.id} publicado en {post.platform}")
            else:
                post.status        = "failed"
                post.error_message = json.dumps(result.get("error", "unknown"))
                logger.error(f"[Scheduler] Post {post.id} FALLÓ: {post.error_message}")

        except Exception as exc:
            post.status        = "failed"
            post.error_message = str(exc)
            logger.exception(f"[Scheduler] Excepción publicando post {post.id}")
        finally:
            db.session.commit()

    def _simulate_publish(self, post: Post, video_path: str, hashtags: list[str]) -> dict:
        if post.platform not in {"tiktok", "instagram", "facebook"}:
            return {"success": False, "error": f"Plataforma desconocida: {post.platform}"}

        publish_id = f"demo-{post.platform}-{post.id}"
        logger.info(
            "[Scheduler] Publicación simulada (%s) para post=%s, video=%s, hashtags=%s",
            post.platform,
            post.id,
            os.path.basename(video_path),
            len(hashtags),
        )
        return {
            "success": True,
            "demo": True,
            "platform": post.platform,
            "publish_id": publish_id,
        }
