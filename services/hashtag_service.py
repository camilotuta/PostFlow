"""
Servicio de Hashtags Inteligentes
Genera hashtags optimizados según:
  - Categoría de contenido (gaming, gym, etc.)
  - Plataforma destino (tiktok, instagram, facebook)
  - Límites de la plataforma
"""

import random
from config import HASHTAGS, MAX_HASHTAGS


# Map de etiquetas "bonitas" → clave interna
CONTENT_TYPE_LABELS = {
    "gaming":        "gaming",
    "acc_gimnasio":  "acc_gimnasio",
    "pilates_yoga":  "pilates_yoga",
    "sup_naturales": "sup_naturales",
    "ropa_deportiva":"ropa_deportiva",
    "sup_deportivos":"sup_deportivos",
    "home_gym":      "home_gym",
}

# Hashtags universales de alto alcance para relleno
UNIVERSAL_TAGS = [
    "#colombia", "#colombia🇨🇴", "#viral", "#fyp", "#parati",
    "#explorepage", "#trending", "#2025", "#reels", "#contenido",
]


class HashtagService:

    def get_hashtags(
        self,
        content_type: str,
        platform: str,
        custom_extra: list[str] | None = None,
        brand: str | None = None,
        count: int | None = None,
    ) -> list[str]:
        """
        Devuelve lista de hashtags optimizada para la plataforma.
        
        Args:
            content_type: clave del tipo de contenido (ej: 'gaming', 'home_gym')
            platform: 'tiktok', 'instagram' o 'facebook'
            custom_extra: hashtags adicionales del usuario
            count: número deseado (si None, usa el máximo de la plataforma)
        """
        max_tags = count or MAX_HASHTAGS.get(platform, 10)

        # Fallback de categoría por marca (si llega una categoría inválida/vacía)
        fallback_type = "gaming" if brand == "tatuct" else "acc_gimnasio"
        effective_type = content_type if content_type in HASHTAGS else fallback_type

        base_tags = list(HASHTAGS.get(effective_type, HASHTAGS[fallback_type]))
        extra_tags = [str(t).strip() for t in (custom_extra or []) if str(t).strip()]

        # Regla clave: priorizar hashtags de IA/custom sobre los genéricos de categoría.
        prioritized = _dedupe(extra_tags + base_tags)

        if len(prioritized) < max_tags:
            fill = [t for t in UNIVERSAL_TAGS if t.lower() not in {x.lower() for x in prioritized}]
            random.shuffle(fill)
            prioritized += fill

        selected = prioritized[:max_tags]
        return [_normalize_hashtag(t) for t in selected]

    def get_suggestions(self, content_type: str) -> dict:
        """
        Devuelve sugerencias de hashtags por plataforma para mostrar en la UI.
        """
        return {
            "tiktok":    self.get_hashtags(content_type, "tiktok"),
            "instagram": self.get_hashtags(content_type, "instagram"),
            "facebook":  self.get_hashtags(content_type, "facebook"),
        }

    @staticmethod
    def get_content_types() -> list[dict]:
        """Lista de tipos de contenido con etiqueta visible."""
        return [
            {"key": "gaming",         "label": "Gaming / Twitch"},
            {"key": "acc_gimnasio",   "label": "Acc. Gimnasio"},
            {"key": "pilates_yoga",   "label": "Pilates & Yoga"},
            {"key": "sup_naturales",  "label": "Sup. Naturales"},
            {"key": "ropa_deportiva", "label": "Ropa Deportiva"},
            {"key": "sup_deportivos", "label": "Sup. Deportivos"},
            {"key": "home_gym",       "label": "Home Gym"},
        ]


# ─────────────────────────────────────────────────────────────
def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item.lower() not in seen:
            seen.add(item.lower())
            result.append(item)
    return result


def _normalize_hashtag(tag: str) -> str:
    txt = str(tag or "").strip()
    if not txt:
        return ""
    if not txt.startswith("#"):
        txt = f"#{txt}"
    return txt
