"""
Instagram Graph API – Reels / Video Posts
Documentación: https://developers.facebook.com/docs/instagram-api/guides/content-publishing

PASOS para conectar:
1. Crea una app en https://developers.facebook.com/ (tipo Business)
2. Agrega el producto "Instagram Graph API"
3. Conecta tu cuenta profesional de Instagram a una Página de Facebook
4. Obtén un Page Access Token (largo plazo)
5. Encuentra tu Instagram Account ID con:
   GET /me/accounts → toma el page id
   GET /{page-id}?fields=instagram_business_account
6. Copia INSTAGRAM_ACCOUNT_ID y FACEBOOK_ACCESS_TOKEN al .env
"""

import requests
import logging
import os
from config import (
    INSTAGRAM_ACCOUNT_ID,
    FACEBOOK_ACCESS_TOKEN,
)

logger = logging.getLogger(__name__)

FB_GRAPH = "https://graph.facebook.com/v20.0"


class InstagramService:

    def __init__(self, brand: str = "gymark"):
        from config import BRANDS
        cfg = BRANDS.get(brand, BRANDS["gymark"])
        self.brand        = brand
        self.account_id   = cfg["instagram_account_id"]
        self.access_token = cfg["facebook_access_token"]
        self._demo_mode   = not bool(self.account_id and self.access_token)

    # ─────────────────────────────────────────────────────────
    #  Publicar Reel / Video
    # ─────────────────────────────────────────────────────────
    def post_video(self, video_url: str, caption: str, hashtags: list[str]) -> dict:
        """
        video_url debe ser una URL pública accesible desde internet.
        Si estás corriendo localmente, usa ngrok o sube el video a un CDN primero.
        """
        if self._demo_mode:
            return self._demo_post(caption, hashtags)

        full_caption = f"{caption}\n\n{' '.join(hashtags)}"[:2200]

        # 1 – Crear contenedor
        container = self._create_container(video_url, full_caption)
        if not container.get("id"):
            return {"success": False, "error": container, "platform": "instagram"}

        container_id = container["id"]

        # 2 – Esperar que esté listo (polling)
        status = self._wait_for_container(container_id)
        if status != "FINISHED":
            return {"success": False, "error": f"Container status: {status}", "platform": "instagram"}

        # 3 – Publicar
        result = self._publish_container(container_id)
        if "id" in result:
            return {"success": True, "post_id": result["id"], "platform": "instagram"}
        return {"success": False, "error": result, "platform": "instagram"}

    def _create_container(self, video_url: str, caption: str) -> dict:
        resp = requests.post(
            f"{FB_GRAPH}/{self.account_id}/media",
            params={
                "video_url":    video_url,
                "caption":      caption,
                "media_type":   "REELS",
                "access_token": self.access_token,
            },
        )
        return resp.json()

    def _wait_for_container(self, container_id: str, max_wait: int = 120) -> str:
        import time
        for _ in range(max_wait // 5):
            resp = requests.get(
                f"{FB_GRAPH}/{container_id}",
                params={"fields": "status_code", "access_token": self.access_token},
            )
            data  = resp.json()
            code  = data.get("status_code", "")
            if code == "FINISHED":
                return "FINISHED"
            if code == "ERROR":
                return "ERROR"
            time.sleep(5)
        return "TIMEOUT"

    def _publish_container(self, container_id: str) -> dict:
        resp = requests.post(
            f"{FB_GRAPH}/{self.account_id}/media_publish",
            params={
                "creation_id":  container_id,
                "access_token": self.access_token,
            },
        )
        return resp.json()

    # ─────────────────────────────────────────────────────────
    #  Modo demo
    # ─────────────────────────────────────────────────────────
    def _demo_post(self, caption: str, hashtags: list[str]) -> dict:
        logger.warning("[Instagram] DEMO MODE – credenciales no configuradas")
        return {
            "success":  True,
            "demo":     True,
            "platform": "instagram",
            "message":  "Post simulado (configura INSTAGRAM_ACCOUNT_ID y FACEBOOK_ACCESS_TOKEN en .env)",
            "caption":  caption,
            "hashtags": hashtags,
        }

    def is_configured(self) -> bool:
        return not self._demo_mode
