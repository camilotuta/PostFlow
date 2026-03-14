"""
TikTok Content Posting API v2
Documentación: https://developers.tiktok.com/doc/content-posting-api-get-started

PASOS para conectar:
1. Crea una app en https://developers.tiktok.com/
2. Activa el product "Content Posting API"
3. Configura el redirect URI en tu app
4. Copia Client Key y Client Secret al .env
5. El usuario debe autorizar la app (flujo OAuth 2.0)
"""

import requests
import json
import os
import logging
from config import (
    TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET,
    TIKTOK_ACCESS_TOKEN, TIKTOK_OPEN_ID,
    UPLOAD_DIR
)

logger = logging.getLogger(__name__)

TIKTOK_API_BASE  = "https://open.tiktokapis.com/v2"
TIKTOK_AUTH_URL  = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


class TikTokService:

    def __init__(self, brand: str = "gymark"):
        from config import BRANDS
        cfg = BRANDS.get(brand, BRANDS["gymark"])
        self.brand        = brand
        self.access_token = cfg["tiktok_access_token"]
        self.open_id      = cfg["tiktok_open_id"]
        self.client_key   = cfg["tiktok_client_key"]
        self.client_secret = cfg["tiktok_client_secret"]
        self._demo_mode   = not bool(self.access_token and self.open_id)

    # ─────────────────────────────────────────────────────────
    #  OAuth helpers
    # ─────────────────────────────────────────────────────────
    def get_oauth_url(self, redirect_uri: str, state: str = "gymark") -> str:
        scopes = "video.publish,video.upload,user.info.basic"
        url = (
            f"{TIKTOK_AUTH_URL}"
            f"?client_key={self.client_key}"
            f"&scope={scopes}"
            f"&response_type=code"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )
        return url

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        resp = requests.post(
            TIKTOK_TOKEN_URL,
            data={
                "client_key":    self.client_key,
                "client_secret": self.client_secret,
                "code":          code,
                "grant_type":    "authorization_code",
                "redirect_uri":  redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return resp.json()

    # ─────────────────────────────────────────────────────────
    #  Publicar video
    # ─────────────────────────────────────────────────────────
    def post_video(self, video_path: str, title: str, hashtags: list[str]) -> dict:
        if self._demo_mode:
            return self._demo_post(title, hashtags)

        # 1 – Inicializar subida
        file_size = os.path.getsize(video_path)
        init_resp = self._init_video_upload(title, hashtags, file_size)
        if "error" in init_resp:
            return init_resp

        upload_url  = init_resp["data"]["upload_url"]
        publish_id  = init_resp["data"]["publish_id"]

        # 2 – Subir archivo
        upload_result = self._upload_video_file(video_path, upload_url, file_size)
        if not upload_result.get("ok"):
            return {"success": False, "error": f"Error subiendo video a TikTok: {upload_result}"}

        # 3 – Confirmar publicación
        return {"success": True, "publish_id": publish_id, "platform": "tiktok"}

    def _init_video_upload(self, title: str, hashtags: list[str], file_size: int) -> dict:
        caption = f"{title} {' '.join(hashtags)}"[:2200]
        payload = {
            "post_info": {
                "title":         caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet":  False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source":    "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }
        resp = requests.post(
            f"{TIKTOK_API_BASE}/post/publish/video/init/",
            headers={
                "Authorization":  f"Bearer {self.access_token}",
                "Content-Type":   "application/json; charset=UTF-8",
            },
            json=payload,
        )
        data = resp.json()
        if resp.status_code != 200 or data.get("error", {}).get("code") != "ok":
            return {"success": False, "error": data}
        return data

    def _upload_video_file(self, video_path: str, upload_url: str, file_size: int) -> dict:
        with open(video_path, "rb") as f:
            resp = requests.put(
                upload_url,
                data=f,
                headers={
                    "Content-Type":   "video/mp4",
                    "Content-Length": str(file_size),
                    "Content-Range":  f"bytes 0-{file_size - 1}/{file_size}",
                },
            )
        return {"ok": resp.status_code in (200, 201, 204), "status": resp.status_code}

    # ─────────────────────────────────────────────────────────
    #  Modo demo (sin credenciales)
    # ─────────────────────────────────────────────────────────
    def _demo_post(self, title: str, hashtags: list[str]) -> dict:
        logger.warning("[TikTok] DEMO MODE – credenciales no configuradas")
        return {
            "success":    True,
            "demo":       True,
            "platform":   "tiktok",
            "message":    "Post simulado (configura TIKTOK_ACCESS_TOKEN en .env para publicar de verdad)",
            "title":      title,
            "hashtags":   hashtags,
        }

    def is_configured(self) -> bool:
        return not self._demo_mode
