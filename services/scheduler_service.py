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

from config import TIMEZONE, UPLOAD_DIR
from database import db, Post

logger = logging.getLogger(__name__)

COL_TZ = ZoneInfo(TIMEZONE)

PERFECT_BEST_TIMES = {
    "gaming": {
        "tiktok": {3: [19, 21, 23], 4: [19, 21, 23], 5: [19, 21, 23], 6: [19, 21, 23]},
        "instagram": {1: [17, 19, 21], 2: [17, 19, 21], 3: [17, 19, 21], 5: [17, 19, 21]},
        "facebook": {0: [9, 15, 18], 1: [9, 15, 18], 2: [9, 15, 18], 3: [9, 15, 18], 4: [9, 15, 18]},
    },
    "acc_gimnasio": {
        "tiktok": {0: [17, 19, 21], 1: [17, 19, 21], 2: [17, 19, 21], 3: [17, 19, 21], 4: [17, 19, 21]},
        "instagram": {1: [11, 14, 17], 2: [11, 14, 17], 3: [11, 14, 17]},
        "facebook": {0: [9, 12, 15], 1: [9, 12, 15], 2: [9, 12, 15], 3: [9, 12, 15]},
    },
    "pilates_yoga": {
        "tiktok": {0: [17, 19, 20], 1: [17, 19, 20], 2: [17, 19, 20], 6: [17, 19, 20]},
        "instagram": {1: [11, 14, 19], 2: [11, 14, 19], 3: [11, 14, 19]},
        "facebook": {1: [9, 11, 15], 2: [9, 11, 15], 3: [9, 11, 15]},
    },
    "sup_naturales": {
        "tiktok": {1: [14, 17, 19], 2: [14, 17, 19], 3: [14, 17, 19]},
        "instagram": {0: [11, 14, 17], 1: [11, 14, 17], 2: [11, 14, 17]},
        "facebook": {1: [9, 10, 14], 2: [9, 10, 14], 3: [9, 10, 14]},
    },
    "ropa_deportiva": {
        "tiktok": {0: [15, 18, 20], 1: [15, 18, 20], 2: [15, 18, 20], 3: [15, 18, 20], 4: [15, 18, 20]},
        "instagram": {1: [11, 14, 17], 2: [11, 14, 17], 3: [11, 14, 17]},
        "facebook": {0: [9, 12, 15], 1: [9, 12, 15], 2: [9, 12, 15], 3: [9, 12, 15]},
    },
    "sup_deportivos": {
        "tiktok": {0: [17, 19, 21], 1: [17, 19, 21], 2: [17, 19, 21], 3: [17, 19, 21], 4: [17, 19, 21]},
        "instagram": {1: [11, 14, 17], 2: [11, 14, 17], 3: [11, 14, 17]},
        "facebook": {0: [9, 12, 15], 1: [9, 12, 15], 2: [9, 12, 15], 3: [9, 12, 15]},
    },
    "home_gym": {
        "tiktok": {0: [17, 19, 21], 1: [17, 19, 21], 2: [17, 19, 21], 3: [17, 19, 21], 4: [17, 19, 21]},
        "instagram": {1: [11, 14, 17], 2: [11, 14, 17], 3: [11, 14, 17]},
        "facebook": {0: [9, 12, 15], 1: [9, 12, 15], 2: [9, 12, 15], 3: [9, 12, 15]},
    },
    # ──────────────────────────────────────────────────────────────
    # 💄 MILITA BEAUTY  (Milita – TikTok México UTC-6)
    # Horas almacenadas en Colombia (UTC-5) = hora MX + 1
    # Días estrella: Mar(1) Mié(2) Jue(3) Vie(4) Sáb(5)
    # ──────────────────────────────────────────────────────────────
    "milita_beauty": {
        "tiktok": {
            1: [10, 16, 20],      # Martes  ★ (MX 09/15/19h)
            2: [10, 16, 20],      # Miércoles ★
            3: [10, 16, 20, 23],  # Jueves  ★★ prime (MX 09/15/19/22h)
            4: [10, 17, 20],      # Viernes ★ (MX 09/16/19h)
            5: [15, 20],          # Sábado self-care (MX 14/19h)
        },
    },
}


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
        Si `after` es None, usa ahora (Colombia).
        """
        now = after or datetime.now(COL_TZ)
        # Tabla: PERFECT_BEST_TIMES[content_type][platform]
        cat_times = PERFECT_BEST_TIMES.get(content_type, PERFECT_BEST_TIMES["acc_gimnasio"])
        table = cat_times.get(platform, cat_times.get("tiktok", {}))

        # Intentar en los próximos días, respetando SOLO los días configurados
        for days_ahead in range(15):
            candidate_date = now.date() + timedelta(days=days_ahead)
            weekday        = candidate_date.weekday()  # 0=lunes
            hours = table.get(weekday, [])

            if not hours:
                continue

            for hour in sorted(hours):
                candidate = datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    hour, 0, 0,
                    tzinfo=COL_TZ,
                )
                # Mínimo 5 minutos en el futuro
                if candidate > now + timedelta(minutes=5):
                    # Check database for slots taken at this hour
                    start_of_hour = candidate.replace(tzinfo=None)
                    end_of_hour = start_of_hour + timedelta(hours=1)
                    
                    posts_in_slot = Post.query.filter(
                        Post.platform == platform,
                        Post.brand == brand,
                        Post.status.in_(["scheduled", "posting"]),
                        Post.scheduled_at >= start_of_hour,
                        Post.scheduled_at < end_of_hour
                    ).count()
                    
                    if posts_in_slot < 2:
                        return candidate

        # Fallback de seguridad: mañana a las 10 am
        tomorrow = now + timedelta(days=1)
        return datetime(
            tomorrow.year, tomorrow.month, tomorrow.day,
            10, 0, 0, tzinfo=COL_TZ,
        )

    def get_schedule_preview(
        self, platforms: list[str], content_type: str = "acc_gimnasio"
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
                slot  = self.get_next_best_time(platform, after, content_type)
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
            now   = datetime.now(COL_TZ).replace(tzinfo=None)
            posts = Post.query.filter(
                Post.status == "scheduled",
                Post.scheduled_at <= now,
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
