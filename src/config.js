import crypto from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");
export const FRONTEND_DIR = rootDir;

dotenv.config({ path: path.join(rootDir, ".env") });

export const BASE_DIR = rootDir;
export const UPLOAD_DIR = path.join(FRONTEND_DIR, "static", "uploads");
export const THUMBS_DIR = path.join(UPLOAD_DIR, "thumbs");
export const VIDEO_INTROS_DIR = path.join(UPLOAD_DIR, "brand-assets", "intro");
export const VIDEO_OUTROS_DIR = path.join(UPLOAD_DIR, "brand-assets", "outro");
export const DATABASE_PATH =
  process.env.DATABASE_PATH || path.join(rootDir, "socialmedia.db");
export const SECRET_KEY =
  process.env.SECRET_KEY || "gymark-subirvideos-secret-2025";
export const PUBLIC_BASE_URL =
  process.env.PUBLIC_BASE_URL ||
  (process.env.RAILWAY_PUBLIC_DOMAIN
    ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}`
    : "http://localhost:5000");
export const MAX_VIDEO_MB = 500;
export const ALLOWED_EXTENSIONS = new Set(["mp4", "mov", "avi", "mkv", "webm"]);

export const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
const defaultGeminiKeys = [
  "AIzaSyDXg0xtuOlLVcVzRNnmIdF4OoHvZDxZ_iQ",
  "AIzaSyCfw6kr_DeY6-DoQmEt5E9n9Lh-1vNjZi8",
  "AIzaSyCk28khT8N7mooOzfhVXos23K2tjVB_Ivc",
  "AIzaSyDhbs8I0Jp-5faV-h6I3vSQFKUu-1nFtyQ",
];
export const GEMINI_API_KEYS = (() => {
  const envKeys = (process.env.GEMINI_API_KEYS || "").trim();
  const keys = envKeys
    ? envKeys
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean)
    : [...defaultGeminiKeys];
  if (GEMINI_API_KEY && !keys.includes(GEMINI_API_KEY))
    keys.push(GEMINI_API_KEY);
  return keys;
})();

export const TIMEZONE = "America/Bogota";

export const BRANDS = {
  gymark: {
    label: "Gymark 🏋️",
    color: "#6c63ff",
    platforms: ["tiktok", "instagram", "facebook", "youtube_shorts"],
  },
  tatuct: {
    label: "TatuCT 🎮",
    color: "#ff0050",
    platforms: ["tiktok", "youtube_shorts"],
  },
  milita: {
    label: "Milita 💄",
    color: "#ff69b4",
    platforms: ["tiktok"],
  },
  escape: {
    label: "Escape 🚀",
    color: "#00bcd4",
    platforms: ["tiktok", "instagram"],
  },
};

export const BRAND_CATEGORIES = {
  gymark: [
    "acc_gimnasio",
    "pilates_yoga",
    "sup_naturales",
    "ropa_deportiva",
    "sup_deportivos",
    "home_gym",
  ],
  tatuct: ["gaming"],
  milita: ["milita_beauty"],
  escape: ["escape_proctoring"],
};

export const BRAND_LOGIN_PASSWORDS = {
  gymark: process.env.GYMARK_LOGIN_PASSWORD || "gymark",
  tatuct: process.env.TATUCT_LOGIN_PASSWORD || "123",
  milita: process.env.MILITA_LOGIN_PASSWORD || "camilo",
  escape: process.env.ESCAPE_LOGIN_PASSWORD || "escapetopuria",
};

const calToken = (brand) =>
  crypto
    .createHash("sha256")
    .update(`${SECRET_KEY}:calendar:${brand}`)
    .digest("hex")
    .slice(0, 32);

export const BRAND_CALENDAR_TOKENS = {
  gymark: process.env.GYMARK_CALENDAR_TOKEN || calToken("gymark"),
  tatuct: process.env.TATUCT_CALENDAR_TOKEN || calToken("tatuct"),
  milita: process.env.MILITA_CALENDAR_TOKEN || calToken("milita"),
  escape: process.env.ESCAPE_CALENDAR_TOKEN || calToken("escape"),
};

export const HASHTAGS = {
  gaming: [
    "#GamingColombia",
    "#GamersColombia",
    "#Colombiagamer",
    "#GamingEnEspañol",
    "#TwitchColombia",
    "#StreamersColombianos",
    "#VideojuegosColombia",
    "#Twitch",
    "#Gaming",
    "#Gamer",
    "#fyp",
    "#ForYou",
    "#TikTokGaming",
    "#BogotaGamer",
  ],
  acc_gimnasio: [
    "#GymAccessories",
    "#AccesoriosGym",
    "#FitnessGear",
    "#Gym",
    "#Fitness",
    "#Workout",
    "#GymLife",
    "#ColombiaFit",
    "#GymColombia",
    "#AccesoriosDeportivos",
  ],
  pilates_yoga: [
    "#Pilates",
    "#Yoga",
    "#AccesoriosYoga",
    "#PilatesReformer",
    "#YogaColombia",
    "#Fitness",
    "#PilatesLovers",
    "#PilatesColombia",
    "#ColombiaFit",
  ],
  sup_naturales: [
    "#SuplementosNaturales",
    "#Suplementos",
    "#Bienestar",
    "#NutricionNatural",
    "#ProductosNaturales",
    "#Salud",
    "#Fitness",
    "#SuplementosColombia",
    "#Natural",
    "#ColombiaFit",
  ],
  ropa_deportiva: [
    "#RopaDeportiva",
    "#GymWear",
    "#Activewear",
    "#RopaGym",
    "#FitnessFashion",
    "#GymClothes",
    "#ColombiaFit",
    "#RopaDeportivaColombia",
    "#Fit",
    "#GymLife",
  ],
  sup_deportivos: [
    "#SuplementosDeportivos",
    "#SuplementosColombia",
    "#Fitness",
    "#Gym",
    "#Proteina",
    "#Nutricion",
    "#GymMotivation",
    "#SuplementosBogota",
    "#ColombiaFit",
    "#Workout",
  ],
  home_gym: [
    "#GimnasioEnCasa",
    "#HomeGym",
    "#GymEnCasa",
    "#EquiposGym",
    "#Fitness",
    "#HomeWorkout",
    "#GymMotivation",
    "#ColombiaFit",
    "#GimnasioColombia",
  ],
  milita_beauty: [
    "#Maquillaje",
    "#Belleza",
    "#MaquillajeColombia",
    "#MaquillajeBogota",
    "#TipsDeBelleza",
    "#MakeupTutorial",
    "#CuidadoPersonal",
    "#Skincare",
    "#AmorPropio",
    "#CuidadodelaPiel",
    "#Fitness",
    "#GlowUp",
    "#fyp",
    "#ForYou",
    "#Viral",
  ],
  escape_proctoring: [
    "#EstudiantesLatinoamerica",
    "#UniversitariosLatinoamerica",
    "#EstudiantesUSA",
    "#HispanicStudents",
    "#ExamenesVirtuales",
    "#LockDownBrowser",
    "#SMOWL",
    "#Proctoring",
    "#ProctoringTips",
    "#OnlineExam",
    "#StudyHacks",
    "#TipsDeEstudio",
    "#AyudaUniversitaria",
    "#fyp",
    "#ForYou",
    "#Viral",
    "#ClasesVirtuales",
    "#HacksUniversitarios",
    "#ExamTips",
    "#StudyTok",
    "#Educational",
    "#TikTokUniversity",
    "#EstudiantesHispanos",
    "#ProctoringColombia",
    "#ProctoringMexico",
    "#LockDownBrowserTips",
    "#SMOWLTrucos",
  ],
};

export const GYMARK_VIRAL_HASHTAGS = [
  "#fyp",
  "#ForYou",
  "#Viral",
  "#GymTok",
  "#FitnessMotivation",
  "#ColombiaFit",
  "#GymColombia",
];

export const CONTENT_TYPES = [
  { key: "gaming", label: "Gaming / Twitch" },
  { key: "acc_gimnasio", label: "Acc. Gimnasio" },
  { key: "pilates_yoga", label: "Pilates & Yoga" },
  { key: "sup_naturales", label: "Sup. Naturales" },
  { key: "ropa_deportiva", label: "Ropa Deportiva" },
  { key: "sup_deportivos", label: "Sup. Deportivos" },
  { key: "home_gym", label: "Home Gym" },
  { key: "milita_beauty", label: "Beauty & Fitness" },
  { key: "escape_proctoring", label: "Proctoring & Exámenes" },
];

export const SCHEDULE_SLOTS = {
  gaming: {
    tiktok: {
      0: [19, 21],
      1: [19, 21],
      2: [19, 21],
      3: [19, 21, 23],
      4: [19, 21, 23],
      5: [19, 21, 23],
      6: [19, 21, 23],
    },
    instagram: {
      0: [17, 19],
      1: [17, 19, 21],
      2: [17, 19, 21],
      3: [17, 19, 21],
      4: [17, 19],
      5: [17, 19, 21],
      6: [17, 19],
    },
    facebook: {
      0: [9, 15, 18],
      1: [9, 15, 18],
      2: [9, 15, 18],
      3: [9, 15, 18],
      4: [9, 15, 18],
      5: [9, 15],
      6: [9, 15],
    },
  },
  acc_gimnasio: {
    tiktok: {
      0: [17, 19, 21],
      1: [17, 19, 21],
      2: [17, 19, 21],
      3: [17, 19, 21],
      4: [15, 19, 21],
      5: [17, 19],
      6: [17, 19],
    },
    instagram: {
      0: [11, 17],
      1: [11, 14, 17],
      2: [11, 14, 17],
      3: [11, 14, 17],
      4: [11, 17],
      5: [11, 17],
      6: [11, 17],
    },
    facebook: {
      0: [9, 12, 15],
      1: [9, 12, 15],
      2: [9, 12, 15],
      3: [9, 12, 15],
      4: [9, 12],
      5: [9, 12],
      6: [9, 12],
    },
  },
  pilates_yoga: {
    tiktok: {
      0: [17, 19, 20],
      1: [17, 19, 20],
      2: [17, 19, 20],
      3: [17, 19],
      4: [17, 19],
      5: [17, 19],
      6: [17, 19, 20],
    },
    instagram: {
      0: [11, 19],
      1: [11, 14, 19],
      2: [11, 14, 19],
      3: [11, 14, 19],
      4: [11, 19],
      5: [11, 19],
      6: [11, 19],
    },
    facebook: {
      0: [9, 11],
      1: [9, 11, 15],
      2: [9, 11, 15],
      3: [9, 11, 15],
      4: [9, 11],
      5: [9, 11],
      6: [9, 11],
    },
  },
  sup_naturales: {
    tiktok: {
      0: [14, 17],
      1: [14, 17, 19],
      2: [14, 17, 19],
      3: [14, 17, 19],
      4: [14, 17],
      5: [14, 17],
      6: [14, 17],
    },
    instagram: {
      0: [11, 14, 17],
      1: [11, 14, 17],
      2: [11, 14, 17],
      3: [11, 14, 17],
      4: [11, 17],
      5: [11, 17],
      6: [11, 17],
    },
    facebook: {
      0: [9, 14],
      1: [9, 10, 14],
      2: [9, 10, 14],
      3: [9, 10, 14],
      4: [9, 14],
      5: [9, 14],
      6: [9, 14],
    },
  },
  ropa_deportiva: {
    tiktok: {
      0: [15, 18, 20],
      1: [15, 18, 20],
      2: [15, 18, 20],
      3: [15, 18, 20],
      4: [15, 18, 20],
      5: [15, 18],
      6: [15, 18],
    },
    instagram: {
      0: [11, 17],
      1: [11, 14, 17],
      2: [11, 14, 17],
      3: [11, 14, 17],
      4: [11, 17],
      5: [11, 17],
      6: [11, 17],
    },
    facebook: {
      0: [9, 12, 15],
      1: [9, 12, 15],
      2: [9, 12, 15],
      3: [9, 12, 15],
      4: [9, 12],
      5: [9, 12],
      6: [9, 12],
    },
  },
  sup_deportivos: {
    tiktok: {
      0: [17, 19, 21],
      1: [17, 19, 21],
      2: [17, 19, 21],
      3: [17, 19, 21],
      4: [17, 19, 21],
      5: [17, 19],
      6: [17, 19],
    },
    instagram: {
      0: [11, 17],
      1: [11, 14, 17],
      2: [11, 14, 17],
      3: [11, 14, 17],
      4: [11, 17],
      5: [11, 17],
      6: [11, 17],
    },
    facebook: {
      0: [9, 12, 15],
      1: [9, 12, 15],
      2: [9, 12, 15],
      3: [9, 12, 15],
      4: [9, 12],
      5: [9, 12],
      6: [9, 12],
    },
  },
  home_gym: {
    tiktok: {
      0: [17, 19, 21],
      1: [17, 19, 21],
      2: [17, 19, 21],
      3: [17, 19, 21],
      4: [17, 19, 21],
      5: [17, 19],
      6: [17, 19],
    },
    instagram: {
      0: [11, 17],
      1: [11, 14, 17],
      2: [11, 14, 17],
      3: [11, 14, 17],
      4: [11, 17],
      5: [11, 17],
      6: [11, 17],
    },
    facebook: {
      0: [9, 12, 15],
      1: [9, 12, 15],
      2: [9, 12, 15],
      3: [9, 12, 15],
      4: [9, 12],
      5: [9, 12],
      6: [9, 12],
    },
  },
  milita_beauty: {
    tiktok: {
      0: [],
      1: [10, 12, 14, 16, 20, 22],
      2: [10, 12, 14, 16, 20, 22],
      3: [10, 12, 14, 16, 20, 21, 23],
      4: [10, 16, 17, 20, 21],
      5: [15, 20, 23],
      6: [],
    },
  },
  escape_proctoring: {
    tiktok: {
      1: [10, 19],
      2: [11, 20],
      3: [9, 19],
      4: [12, 20],
      5: [10],
    },
    instagram: {
      1: [11, 19],
      2: [11, 20],
      3: [11, 19],
      4: [12, 20],
      5: [10],
    },
  },
};

export const DAILY_PLATFORM_LIMITS = {
  tatuct: { tiktok: 2, youtube_shorts: 2 },
  milita: { tiktok: 2 },
  escape: { tiktok: 2, instagram: 1 },
  gymark: { tiktok: 2, instagram: 1, facebook: 1, youtube_shorts: 1 },
};

export const DAILY_TOTAL_LIMITS = {
  tatuct: 3,
  milita: 2,
  escape: 3,
  gymark: 5,
};

export const ACTIVE_POST_STATES = ["scheduled", "posting", "published"];

export function defaultContentTypeForBrand(brand) {
  const key = String(brand || "").toLowerCase();
  if (key === "tatuct") return "gaming";
  if (key === "milita") return "milita_beauty";
  if (key === "escape") return "escape_proctoring";
  return "acc_gimnasio";
}

export function brandTimezone() {
  return TIMEZONE;
}
