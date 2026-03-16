from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz, json
from config import TIMEZONE

db = SQLAlchemy()

COL_TZ = pytz.timezone(TIMEZONE)


# ──────────────────────────────────────────────────────────────
#   VIDEO  –  archivo subido por el usuario
# ──────────────────────────────────────────────────────────────
class Video(db.Model):
    __tablename__ = "videos"

    id           = db.Column(db.Integer, primary_key=True)
    filename     = db.Column(db.String(256), nullable=False)
    original_name = db.Column(db.String(256), nullable=False)
    brand        = db.Column(db.String(32),  nullable=False, default="gymark")  # gymark | tatuct
    file_path    = db.Column(db.String(512), nullable=False)
    file_size    = db.Column(db.BigInteger, default=0)   # bytes
    duration     = db.Column(db.Float, default=0)        # segundos
    thumbnail    = db.Column(db.String(512), nullable=True)
    uploaded_at  = db.Column(db.DateTime, default=lambda: datetime.now(COL_TZ))

    category_id    = db.Column(db.String(64), nullable=True)
    ai_title       = db.Column(db.String(512), nullable=True)
    ai_description = db.Column(db.Text, nullable=True)

    posts = db.relationship("Post", backref="video", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":            self.id,
            "filename":      self.filename,
            "original_name": self.original_name,
            "brand":         self.brand,
            "file_size_mb":  round(self.file_size / (1024 * 1024), 2),
            "duration":      self.duration,            "thumbnail":     self.thumbnail,
            "uploaded_at":   self.uploaded_at.strftime("%Y-%m-%d %H:%M") if self.uploaded_at else "",
            "category_id":   self.category_id,
            "ai_title":      self.ai_title,
            "ai_description":self.ai_description,
            "posts":         [p.to_dict() for p in self.posts],
        }


# ──────────────────────────────────────────────────────────────
#   POST  –  publicación programada o ya publicada
# ──────────────────────────────────────────────────────────────
class Post(db.Model):
    __tablename__ = "posts"

    id           = db.Column(db.Integer, primary_key=True)
    video_id     = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False)

    # metadata de la publicación
    brand        = db.Column(db.String(32),  nullable=False, default="gymark")  # gymark | tatuct
    platform     = db.Column(db.String(32),  nullable=False)  # tiktok | instagram | facebook
    title        = db.Column(db.String(512), nullable=False)
    description  = db.Column(db.Text,        nullable=True)
    hashtags     = db.Column(db.Text,        nullable=True)   # JSON list
    content_type = db.Column(db.String(64),  nullable=True)   # gaming | acc_gimnasio | ...

    # scheduling
    scheduled_at = db.Column(db.DateTime, nullable=False)
    posted_at    = db.Column(db.DateTime, nullable=True)

    # estado
    status       = db.Column(db.String(32), default="scheduled")
    # scheduled | posting | published | failed | cancelled

    # resultado de la API
    platform_post_id = db.Column(db.String(256), nullable=True)
    error_message    = db.Column(db.Text,        nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(COL_TZ))

    def hashtags_list(self):
        try:
            return json.loads(self.hashtags) if self.hashtags else []
        except Exception:
            return []

    def to_dict(self):
        return {
            "id":               self.id,
            "video_id":         self.video_id,
            "brand":            self.brand,
            "platform":         self.platform,
            "title":            self.title,
            "description":      self.description,
            "hashtags":         self.hashtags_list(),
            "content_type":     self.content_type,
            "scheduled_at":     self.scheduled_at.strftime("%Y-%m-%d %H:%M") if self.scheduled_at else "",
            "posted_at":        self.posted_at.strftime("%Y-%m-%d %H:%M") if self.posted_at else None,
            "status":           self.status,
            "platform_post_id": self.platform_post_id,
            "error_message":    self.error_message,
        }
