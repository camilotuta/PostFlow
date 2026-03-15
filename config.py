import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
#   GENERAL
# ─────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR  = os.path.join(BASE_DIR, "static", "uploads")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'socialmedia.db')}")
SECRET_KEY  = os.environ.get("SECRET_KEY", "gymark-subirvideos-secret-2025")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL") or \
    ("https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"] if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else "http://localhost:5000")
MAX_VIDEO_MB = 500
ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}

# ─────────────────────────────────────────
#   API KEYS EXTRA
# ─────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ34HnWbVfoA5lCozTJ94N-_ofjwcKrr0")

# Rotación multi-key (primero se usan estas en orden). Puede sobreescribirse por env GEMINI_API_KEYS
_default_gemini_keys = [
    "AIzaSyDXg0xtuOlLVcVzRNnmIdF4OoHvZDxZ_iQ",
    "AIzaSyCfw6kr_DeY6-DoQmEt5E9n9Lh-1vNjZi8",
    "AIzaSyCk28khT8N7mooOzfhVXos23K2tjVB_Ivc",
    "AIzaSyDhbs8I0Jp-5faV-h6I3vSQFKUu-1nFtyQ",
]
_env_gemini_keys = os.environ.get("GEMINI_API_KEYS", "")
if _env_gemini_keys.strip():
    GEMINI_API_KEYS = [k.strip() for k in _env_gemini_keys.split(",") if k.strip()]
else:
    GEMINI_API_KEYS = _default_gemini_keys

# Asegurar fallback con key legacy si no viene en la lista
if GEMINI_API_KEY and GEMINI_API_KEY not in GEMINI_API_KEYS:
    GEMINI_API_KEYS.append(GEMINI_API_KEY)

# ─────────────────────────────────────────
#   TIMEZONE  (Colombia UTC-5)
# ─────────────────────────────────────────
TIMEZONE = "America/Bogota"

# ─────────────────────────────────────────────────────────────────
#   MARCAS / CUENTAS
#
#   gymark  → marca de gym  (TikTok + Instagram)
#   tatuct  → canal gaming  (solo TikTok)
#   milita  → belleza/fitness MX (solo TikTok)
# ─────────────────────────────────────────────────────────────────

BRANDS = {
    "gymark": {
        "label":    "Gymark 🏋️",
        "color":    "#6c63ff",
        "platforms": ["tiktok", "instagram"],
    },
    "tatuct": {
        "label":    "TatuCT 🎮",
        "color":    "#ff0050",
        "platforms": ["tiktok"],
    },
    "milita": {
        "label":    "Milita 💄",
        "color":    "#ff69b4",
        "platforms": ["tiktok"],
    },
}

# ─────────────────────────────────────────────────────────────────
#   MEJORES HORARIOS POR CATEGORÍA Y PLATAFORMA  (Colombia UTC-5)
#
#  Investigación basada en:
#   - Later.com / Sprout Social / HubSpot 2025
#   - Audiencia latinoamericana Colombia
#   - Comportamiento real de cada nicho
#
#  Formato:
#    BEST_TIMES[content_type][platform][weekday(0=lunes)] = [hora, ...]
#
#  Lógica detrás de cada categoría:
#   🎮 gaming   → gente conectada de noche/fines de semana jugando
#   🏋️ gym      → madrugadores + pausa almuerzo + post-trabajo
#   🧘 pilates  → mañana temprano o noche relajación
#   🌿 suplementos → antes de entrenar (mañana) o recovery (noche)
#   👕 ropa     → pico de compras online: mediodía y tarde
# ─────────────────────────────────────────────────────────────────

BEST_TIMES = {

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  🎮 GAMING  (TatuCT)
    #  Fuente: Sprout Social 2025 + Hootsuite entertainment
    #  TikTok: Jue-Dom evenings sólidos; Lun-Mié mantienen buen engagement
    #  IG: Mar-Jue + Sáb 17-21h; FB: Lun-Vie 9/15/18h
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "gaming": {
        "tiktok": {
            0: [19, 21],           # Lunes   – menor pero activo
            1: [19, 21],           # Martes
            2: [19, 21],           # Miércoles
            3: [19, 21, 23],       # Jueves  ★ prime gaming
            4: [19, 21, 23],       # Viernes ★ máximo
            5: [19, 21, 23],       # Sábado  ★
            6: [19, 21, 23],       # Domingo ★
        },
        "instagram": {
            0: [17, 19],
            1: [17, 19, 21],       # Martes  ★
            2: [17, 19, 21],       # Miércoles ★
            3: [17, 19, 21],       # Jueves  ★
            4: [17, 19],
            5: [17, 19, 21],       # Sábado  ★
            6: [17, 19],
        },
        "facebook": {
            0: [9, 15, 18],
            1: [9, 15, 18],
            2: [9, 15, 18],
            3: [9, 15, 18],
            4: [9, 15, 18],
            5: [9, 15],
            6: [9, 15],
        },
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  🏋️ ACCESORIOS GIMNASIO  (Gymark)
    #  Fuente: Sprout Social 2025 – fitness/retail patterns
    #  TikTok: Lun-Vie 17-21h post-entreno; Vie extiende 15h
    #  IG: Mar-Jue 11/14/17h; FB: Lun-Jue 9/12/15h
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "acc_gimnasio": {
        "tiktok": {
            0: [17, 19, 21],       # Lunes  ★ motivación inicio semana
            1: [17, 19, 21],
            2: [17, 19, 21],
            3: [17, 19, 21],       # Jueves ★
            4: [15, 19, 21],       # Viernes – inicia antes
            5: [17, 19],
            6: [17, 19],
        },
        "instagram": {
            0: [11, 17],
            1: [11, 14, 17],       # Martes  ★
            2: [11, 14, 17],       # Miércoles ★
            3: [11, 14, 17],       # Jueves  ★
            4: [11, 17],
            5: [11, 17],
            6: [11, 17],
        },
        "facebook": {
            0: [9, 12, 15],
            1: [9, 12, 15],
            2: [9, 12, 15],
            3: [9, 12, 15],
            4: [9, 12],
            5: [9, 12],
            6: [9, 12],
        },
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  🧘 PILATES & YOGA  (Gymark)
    #  Fuente: Sprout Social 2025 – healthcare/wellness
    #  TikTok: Lun-Mié + Dom 17-20h relajación; IG/FB midweek mornings
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "pilates_yoga": {
        "tiktok": {
            0: [17, 19, 20],       # Lunes  ★ nuevo inicio semana
            1: [17, 19, 20],       # Martes ★
            2: [17, 19, 20],       # Miércoles ★
            3: [17, 19],
            4: [17, 19],
            5: [17, 19],
            6: [17, 19, 20],       # Domingo ★ relajación
        },
        "instagram": {
            0: [11, 19],
            1: [11, 14, 19],       # Martes  ★
            2: [11, 14, 19],       # Miércoles ★
            3: [11, 14, 19],       # Jueves  ★
            4: [11, 19],
            5: [11, 19],
            6: [11, 19],
        },
        "facebook": {
            0: [9, 11],
            1: [9, 11, 15],        # Martes  ★
            2: [9, 11, 15],        # Miércoles ★
            3: [9, 11, 15],        # Jueves  ★
            4: [9, 11],
            5: [9, 11],
            6: [9, 11],
        },
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  🌿 SUPLEMENTOS NATURALES  (Gymark)
    #  Fuente: Sprout Social 2025 – healthcare patterns
    #  TikTok: Mar-Jue 14/17/19h educación salud; IG Lun-Mié; FB mornings
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "sup_naturales": {
        "tiktok": {
            0: [14, 17],
            1: [14, 17, 19],       # Martes  ★
            2: [14, 17, 19],       # Miércoles ★
            3: [14, 17, 19],       # Jueves  ★
            4: [14, 17],
            5: [14, 17],
            6: [14, 17],
        },
        "instagram": {
            0: [11, 14, 17],       # Lunes  ★
            1: [11, 14, 17],       # Martes ★
            2: [11, 14, 17],       # Miércoles ★
            3: [11, 14, 17],
            4: [11, 17],
            5: [11, 17],
            6: [11, 17],
        },
        "facebook": {
            0: [9, 14],
            1: [9, 10, 14],        # Martes  ★
            2: [9, 10, 14],        # Miércoles ★
            3: [9, 10, 14],        # Jueves  ★
            4: [9, 14],
            5: [9, 14],
            6: [9, 14],
        },
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  👕 ROPA DEPORTIVA  (Gymark)
    #  Fuente: Sprout Social 2025 – retail/fashion patterns
    #  TikTok: Lun-Vie 15/18/20h; Vie extendido (shopping impulse)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "ropa_deportiva": {
        "tiktok": {
            0: [15, 18, 20],
            1: [15, 18, 20],
            2: [15, 18, 20],
            3: [15, 18, 20],       # Jueves ★
            4: [15, 18, 20],       # Viernes ★ compras fin de semana
            5: [15, 18],
            6: [15, 18],
        },
        "instagram": {
            0: [11, 17],
            1: [11, 14, 17],       # Martes  ★
            2: [11, 14, 17],       # Miércoles ★
            3: [11, 14, 17],       # Jueves  ★
            4: [11, 17],
            5: [11, 17],
            6: [11, 17],
        },
        "facebook": {
            0: [9, 12, 15],
            1: [9, 12, 15],
            2: [9, 12, 15],
            3: [9, 12, 15],
            4: [9, 12],
            5: [9, 12],
            6: [9, 12],
        },
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  💪 SUPLEMENTOS DEPORTIVOS  (Gymark)
    #  Fuente: Sprout Social 2025 – fitness evenings
    #  TikTok: Lun-Vie 17/19/21h post-entreno
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "sup_deportivos": {
        "tiktok": {
            0: [17, 19, 21],       # Lunes  ★
            1: [17, 19, 21],
            2: [17, 19, 21],
            3: [17, 19, 21],       # Jueves ★
            4: [17, 19, 21],       # Viernes ★
            5: [17, 19],
            6: [17, 19],
        },
        "instagram": {
            0: [11, 17],
            1: [11, 14, 17],       # Martes  ★
            2: [11, 14, 17],       # Miércoles ★
            3: [11, 14, 17],       # Jueves  ★
            4: [11, 17],
            5: [11, 17],
            6: [11, 17],
        },
        "facebook": {
            0: [9, 12, 15],
            1: [9, 12, 15],
            2: [9, 12, 15],
            3: [9, 12, 15],
            4: [9, 12],
            5: [9, 12],
            6: [9, 12],
        },
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  🏠 HOME GYM  (Gymark)
    #  Fuente: Sprout Social 2025 – fitness equipment evenings
    #  Igual que accesorios: Lun-Vie 17-21h inspiración setup
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "home_gym": {
        "tiktok": {
            0: [17, 19, 21],       # Lunes  ★ planear semana
            1: [17, 19, 21],
            2: [17, 19, 21],
            3: [17, 19, 21],       # Jueves ★
            4: [17, 19, 21],       # Viernes ★
            5: [17, 19],
            6: [17, 19],
        },
        "instagram": {
            0: [11, 17],
            1: [11, 14, 17],       # Martes  ★
            2: [11, 14, 17],       # Miércoles ★
            3: [11, 14, 17],       # Jueves  ★
            4: [11, 17],
            5: [11, 17],
            6: [11, 17],
        },
        "facebook": {
            0: [9, 12, 15],
            1: [9, 12, 15],
            2: [9, 12, 15],
            3: [9, 12, 15],
            4: [9, 12],
            5: [9, 12],
            6: [9, 12],
        },
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  💄 MILITA BEAUTY  (Milita – TikTok México UTC-6)
    #  Fuente: Tiendanube MX + Sprout Social 2025 + Influencer Marketing Hub 2026
    #  Nicho: Maquillaje + Fitness + Cuidado Personal + Amor Propio + Tips Belleza
    #
    #  Horarios en hora Colombia (UTC-5) = hora México (UTC-6) + 1 hora
    #    MX 09:00 → CO 10:00    MX 11:00 → CO 12:00
    #    MX 13:00 → CO 14:00    MX 15:00 → CO 16:00
    #    MX 19:00 → CO 20:00    MX 20:00 → CO 21:00
    #    MX 21:00 → CO 22:00    MX 22:00 → CO 23:00
    #
    #  Días estrella: Mar-Vie (midweek máximo engagement)
    #  Sábado: self-care/amor propio relajado 14:00/22:00 MX
    #  Lunes y Domingo: débiles – evitar al inicio para crecimiento explosivo
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    "milita_beauty": {
        "tiktok": {
            0: [],                          # Lunes  – débil (skip)
            1: [10, 12, 14, 16, 20, 22],   # Martes  ★ (mañana + tarde + noche)
            2: [10, 12, 14, 16, 20, 22],   # Miércoles ★
            3: [10, 12, 14, 16, 20, 21, 23],  # Jueves ★★ prime máximo
            4: [10, 16, 17, 20, 21],        # Viernes ★ pre-finde energizante
            5: [15, 20, 23],                # Sábado – self-care/amor propio relajado
            6: [],                          # Domingo – débil (skip)
        },
    },
}

# ─────────────────────────────────────────
#   HASHTAGS POR CATEGORÍA DE CONTENIDO
# ─────────────────────────────────────────
HASHTAGS = {
    # ── Gaming / Twitch ──────────────────────────────────────────
    "gaming": [
        "#twitch", "#twitchcolombia", "#tatuct", "#gaming", "#fyp",
        "#parati", "#streaminglatino", "#gaminglatino",
        "#videojuegos", "#gamer", "#stream", "#twitchclips",
        "#gameplay", "#colombia", "#clips", "#funny",
        "#videojuegosespanol", "#highlights", "#gaming2025", "#clipsgaming",
    ],
    # ── Accesorios de Gimnasio ────────────────────────────────────
    "acc_gimnasio": [
        "#gym", "#gimnasio", "#gymark", "#gymarkco", "#accesoriosgym",
        "#fitness", "#workout", "#entrenamiento", "#fitnesscolombia",
        "#gymlife", "#gymaccessories", "#parati", "#fyp",
        "#gymark🏋️", "#equipogym", "#gymequipment",
    ],
    # ── Pilates & Yoga ────────────────────────────────────────────
    "pilates_yoga": [
        "#pilates", "#yoga", "#wellness", "#bienestar", "#yogafitness",
        "#pilateslife", "#gymark", "#gymarkco", "#flexibilidad",
        "#mindandbody", "#saludmental", "#yogacolombia", "#fyp",
        "#pilateslovers", "#yogacolombiana", "#breathe",
    ],
    # ── Suplementos Naturales ─────────────────────────────────────
    "sup_naturales": [
        "#suplementosnaturales", "#nutricion", "#salud", "#natural",
        "#bienestar", "#gymark", "#gymarkco", "#vitaminas",
        "#saludable", "#nutricioncolombia", "#fyp", "#parati",
        "#suplementoscolombia", "#vidanatural", "#plantbased",
    ],
    # ── Ropa Deportiva ────────────────────────────────────────────
    "ropa_deportiva": [
        "#ropadeportiva", "#sportswear", "#fitnessfashion", "#activewear",
        "#gym", "#gymark", "#gymarkco", "#modadeportiva",
        "#outfitgym", "#fitgirl", "#fitboy", "#fyp", "#parati",
        "#gymoutfit", "#lookdeportivo", "#colombiafashion",
    ],
    # ── Suplementos Deportivos ────────────────────────────────────
    "sup_deportivos": [
        "#suplementosdeportivos", "#proteina", "#creatina", "#preworkout",
        "#gym", "#gymark", "#gymarkco", "#musculos",
        "#bodybuilding", "#fitness", "#nutriciondeportiva", "#fyp",
        "#massamuscular", "#ganarmusculos", "#suplementoscol",
    ],
    # ── Home Gym ──────────────────────────────────────────────────
    "home_gym": [
        "#homegym", "#gimnasioencasa", "#workout", "#gymark", "#gymarkco",
        "#fitnesscasa", "#entrenamiento", "#hometraining",
        "#gymsetup", "#fitness", "#colombia", "#fyp", "#parati",
        "#homegymsetup", "#setupgym", "#entrenarencasa",
    ],
    # ── Milita Beauty (Maquillaje + Fitness + Cuidado Personal + Amor Propio) ──
    "milita_beauty": [
        "#maquillaje", "#makeup", "#makeuptutorial", "#fitness",
        "#cuidadopersonal", "#amorpropio", "#selflove", "#belleza",
        "#tipsdebelleza", "#skincare", "#grwm", "#fyp",
        "#paratii", "#mexico", "#fypmx", "#makeupmx",
        "#vidafit", "#bienestar", "#rutinabelleza", "#empoderada",
    ],
}

# Número máximo de hashtags por plataforma
MAX_HASHTAGS = {
    "tiktok": 8,
    "instagram": 30,
    "facebook": 5,
}

# Categorías permitidas por marca
BRAND_CATEGORIES = {
    "gymark": ["acc_gimnasio", "pilates_yoga", "sup_naturales",
               "ropa_deportiva", "sup_deportivos", "home_gym"],
    "tatuct": ["gaming"],
    "milita": ["milita_beauty"],
}

# Login por cuenta/marca
BRAND_LOGIN_PASSWORDS = {
    "gymark":  "gymark",
    "tatuct": "123",
    "milita": "camilo",
}

# Tokens para feed ICS público por marca
# Si no están en el .env se derivan automáticamente del SECRET_KEY (estables entre reinicios)
import hashlib as _hashlib
def _cal_token(brand: str) -> str:
    raw = f"{SECRET_KEY}:calendar:{brand}"
    return _hashlib.sha256(raw.encode()).hexdigest()[:32]

BRAND_CALENDAR_TOKENS = {
    "gymark": os.environ.get("GYMARK_CALENDAR_TOKEN") or _cal_token("gymark"),
    "tatuct": os.environ.get("TATUCT_CALENDAR_TOKEN") or _cal_token("tatuct"),
    "milita": os.environ.get("MILITA_CALENDAR_TOKEN") or _cal_token("milita"),
}
