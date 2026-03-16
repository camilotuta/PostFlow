"""
Servicio de Hashtags Fijos
Devuelve hashtags estáticos por cuenta/categoría.
"""

from config import HASHTAGS, GYMARK_VIRAL_HASHTAGS


# Map de etiquetas "bonitas" → clave interna
CONTENT_TYPE_LABELS = {
    "gaming":        "gaming",
    "acc_gimnasio":  "acc_gimnasio",
    "pilates_yoga":  "pilates_yoga",
    "sup_naturales": "sup_naturales",
    "ropa_deportiva":"ropa_deportiva",
    "sup_deportivos":"sup_deportivos",
    "home_gym":      "home_gym",
    "milita_beauty": "milita_beauty",
}

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
        Devuelve lista de hashtags fijos para la plataforma.
        
        Args:
            content_type: clave del tipo de contenido (ej: 'gaming', 'home_gym')
            platform: 'tiktok', 'instagram' o 'facebook'
            custom_extra: parámetro legacy (se ignora)
            count: límite opcional explícito
        """
        # Fallback de categoría por marca (si llega una categoría inválida/vacía)
        fallback_type = (
            "gaming" if brand == "tatuct"
            else "milita_beauty" if brand == "milita"
            else "acc_gimnasio"
        )
        effective_type = content_type if content_type in HASHTAGS else fallback_type

        base_tags = list(HASHTAGS.get(effective_type, HASHTAGS[fallback_type]))
        fixed_tags = list(base_tags)

        # Gymark: siempre agregar los virales fijos en todas las categorías/plataformas.
        if brand == "gymark":
            fixed_tags = _dedupe(fixed_tags + list(GYMARK_VIRAL_HASHTAGS))

        # Tatuct / Milita en TikTok: mantener salida fija en rango sugerido (8-12)
        limit = count
        if limit is None and platform == "tiktok" and brand in {"tatuct", "milita"}:
            limit = 12
        if limit is None:
            limit = len(fixed_tags)

        selected = fixed_tags[:max(1, int(limit))]
        return [_normalize_hashtag(t) for t in selected if str(t).strip()]

    def get_suggestions(self, content_type: str, brand: str | None = None) -> dict:
        """
        Devuelve sugerencias de hashtags por plataforma para mostrar en la UI.
        """
        return {
            "tiktok":    self.get_hashtags(content_type, "tiktok", brand=brand),
            "instagram": self.get_hashtags(content_type, "instagram", brand=brand),
            "facebook":  self.get_hashtags(content_type, "facebook", brand=brand),
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
            {"key": "milita_beauty",  "label": "Beauty & Fitness"},
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
