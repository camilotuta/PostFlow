"""
Facebook Graph API – Video Posts en Página
Documentación: https://developers.facebook.com/docs/video-api/guides/reels-publishing

PASOS para conectar:
1. Crea una app en https://developers.facebook.com/
2. Agrega "Pages API" y "Video API"
3. Genera un Page Access Token de larga duración:
   GET /oauth/access_token?client_id=APP_ID&client_secret=APP_SECRET&grant_type=fb_exchange_token&fb_exchange_token=SHORT_TOKEN
4. Copia FACEBOOK_PAGE_ID y FACEBOOK_ACCESS_TOKEN al .env
"""

import requests
import logging
from config import FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN

logger = logging.getLogger(__name__)

FB_GRAPH = "https://graph-video.facebook.com/v20.0"
FB_API   = "https://graph.facebook.com/v20.0"


class FacebookService:

    def __init__(self, brand: str = "gymark"):
        from config import BRANDS
        cfg = BRANDS.get(brand, BRANDS["gymark"])
        self.brand        = brand
        self.page_id      = cfg["facebook_page_id"]
        self.access_token = cfg["facebook_access_token"]
        self._demo_mode   = not bool(self.page_id and self.access_token)

    # ─────────────────────────────────────────────────────────
    #  Publicar video en una página
    # ─────────────────────────────────────────────────────────
    def post_video(self, video_path: str, title: str, description: str, hashtags: list[str]) -> dict:
        if self._demo_mode:
            return self._demo_post(title, hashtags)

        # Opción A: subida directa (archivos hasta ~1 GB)
        full_description = f"{description}\n\n{' '.join(hashtags)}"
        file_size = __import__("os").path.getsize(video_path)

        # 1 – Iniciar sesión de subida
        session = self._start_upload_session(file_size, title)
        if "video_id" not in session:
            return {"success": False, "error": session, "platform": "facebook"}

        video_id    = session["video_id"]
        upload_url  = session.get("uri", "")

        # 2 – Subir chunks (chunk único para simplicidad)
        with open(video_path, "rb") as f:
            data = f.read()
        upload_resp = self._upload_chunk(upload_url, data, file_size)
        if not upload_resp.get("success"):
            return {"success": False, "error": upload_resp, "platform": "facebook"}

        # 3 – Publicar
        publish_resp = self._publish_video(video_id, title, full_description)
        if publish_resp.get("success"):
            return {"success": True, "video_id": video_id, "platform": "facebook"}
        return {"success": False, "error": publish_resp, "platform": "facebook"}

    def _start_upload_session(self, file_size: int, title: str) -> dict:
        resp = requests.post(
            f"{FB_GRAPH}/{self.page_id}/videos",
            data={
                "upload_phase":  "start",
                "file_size":     file_size,
                "title":         title,
                "access_token":  self.access_token,
            },
        )
        return resp.json()

    def _upload_chunk(self, upload_url: str, data: bytes, file_size: int) -> dict:
        import io
        resp = requests.post(
            upload_url,
            data={
                "upload_phase":       "transfer",
                "start_offset":       0,
                "access_token":       self.access_token,
            },
            files={"video_file_chunk": ("chunk.mp4", io.BytesIO(data), "video/mp4")},
        )
        result = resp.json()
        return {"success": result.get("start_offset") is not None or resp.status_code in (200, 201), "data": result}

    def _publish_video(self, video_id: str, title: str, description: str) -> dict:
        resp = requests.post(
            f"{FB_API}/{self.page_id}/videos",
            data={
                "upload_phase":  "finish",
                "video_id":      video_id,
                "title":         title,
                "description":   description,
                "published":     True,
                "access_token":  self.access_token,
            },
        )
        result = resp.json()
        return {"success": result.get("success", False) or "id" in result, "data": result}

    # ─────────────────────────────────────────────────────────
    #  Modo demo
    # ─────────────────────────────────────────────────────────
    def _demo_post(self, title: str, hashtags: list[str]) -> dict:
        logger.warning("[Facebook] DEMO MODE – credenciales no configuradas")
        return {
            "success":  True,
            "demo":     True,
            "platform": "facebook",
            "message":  "Post simulado (configura FACEBOOK_PAGE_ID y FACEBOOK_ACCESS_TOKEN en .env)",
            "title":    title,
            "hashtags": hashtags,
        }

    def is_configured(self) -> bool:
        return not self._demo_mode
