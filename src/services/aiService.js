import path from "node:path";
import { GoogleGenAI, FileState } from "@google/genai";
import { GEMINI_API_KEYS, defaultContentTypeForBrand } from "../config.js";

const FALLBACK_TITLES = {
  acc_gimnasio: "Accesorio clave para tu rutina",
  pilates_yoga: "Fluye mejor en cada sesión",
  sup_naturales: "Bienestar real en cada toma",
  ropa_deportiva: "Rinde más con este outfit",
  sup_deportivos: "Potencia tu entrenamiento hoy",
  home_gym: "Tu gym completo en casa",
  gaming: "Momento épico del stream",
  milita_beauty: "Glow y energía en segundos",
  escape_proctoring: "Lo que debes saber antes del examen",
};

function fromFilename(filePath) {
  const base = path.basename(filePath).replace(path.extname(filePath), "").replace(/[_-]+/g, " ").trim();
  return base || "Video";
}

const MODEL_PRIORITY = ["gemini-2.5-pro", "gemini-2.5-flash"];
const JSON_FENCE_RE = /^```(?:json)?\s*|\s*```$/gi;

function friendlyModelName(model) {
  if (model === "gemini-2.5-pro") return "Gemini 2.5 Pro";
  if (model === "gemini-2.5-flash") return "Gemini 2.5 Flash";
  return String(model || "Gemini");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function inferMimeType(videoPath) {
  const ext = path.extname(videoPath).toLowerCase();
  if (ext === ".mp4") return "video/mp4";
  if (ext === ".mov") return "video/quicktime";
  if (ext === ".avi") return "video/x-msvideo";
  if (ext === ".mkv") return "video/x-matroska";
  if (ext === ".webm") return "video/webm";
  return "video/mp4";
}

function cleanJsonText(text) {
  return String(text || "{}").trim().replace(JSON_FENCE_RE, "").trim();
}

function buildBrandContext(brand) {
  if (brand === "tatuct") {
    return "Marca de la cuenta: Gaming / Clips de stream (Tatuct).";
  }
  if (brand === "gymark") {
    return "Marca de la cuenta: Gimnasio / Ropa deportiva (Gymark).";
  }
  if (brand === "escape") {
    return "Cuenta de apoyo estudiantil hispano (@escape). Nicho: proctoring, exámenes virtuales, LockDown Browser, SMOWL, hacks de estudio, tips universitarios y ayuda para estudiantes de LatAm y USA. Audiencia objetivo: estudiantes hispanos universitarios y de college en todo el continente. Tono: directo, útil, rápido y educativo con gancho desde los primeros segundos. Plataformas: TikTok e Instagram Reels.";
  }
  return "Cuenta personal de contenido femenino en México (@milita). Nicho combinado: maquillaje (tutoriales GRWM, looks diarios, transformaciones), fitness (rutinas, motivación, workouts), cuidado personal (skincare, hábitos), amor propio (self-love, mindset, empoderamiento) y tips de belleza (hacks, productos, técnicas). Audiencia objetivo: mujeres 18-34 años en México. Tono: cercano, empoderador, motivacional, femenino y auténtico. Plataforma única: TikTok México.";
}

function buildPrompt({ context, categoryId, enforceGymarkCategory }) {
  const categoryField = enforceGymarkCategory
    ? ',\n  "category_id": "una de las 6 categorías de gymark"'
    : ',\n  "category_id": "' + String(categoryId || "") + '"';

  const categoryRules = enforceGymarkCategory
    ? `
13. Debes clasificar el video en EXACTAMENTE una categoría de Gymark usando SOLO estas opciones:
    - acc_gimnasio
    - pilates_yoga
    - sup_naturales
    - ropa_deportiva
    - sup_deportivos
    - home_gym
14. Si dudas entre dos, elige la más específica según el producto/acción dominante del clip.
`
    : "";

  return `
Analiza este video COMPLETO (imágenes + AUDIO: voz, diálogos, música, efectos de sonido, risas, tono, jingles, etc.).
Debes generar metadatos altamente optimizados para TikTok/Reels basados en lo que ves y ESCUCHAS.
Reglas estrictas:
1. Nada de títulos genéricos. El título debe tratar EXACTAMENTE de la frase más chistosa, el evento principal o el tema central del clip de audio/video.
2. La descripción debe ser CORTA. Nadie lee descripciones largas en TikTok/Reels. Máximo 2 oraciones.
3. Analiza el audio detalladamente para entender el contexto real de la situación.
4. Mantén el lenguaje coloquial real detectado en el contenido.
5. PUNTUACIÓN ESPAÑOLA OBLIGATORIA: si es exclamativa usa ¡!, si es pregunta usa ¿?.
6. PRIMERO debes escuchar y transcribir mentalmente el audio del clip antes de redactar.
7. El título y descripción deben reflejar frase o intención detectada en el audio y la acción visual principal.
8. Si NO hay voz clara, usa sonidos/música/efectos como contexto y coloca "sin_voz_clara" en frase_audio_literal.
9. Incluye 3 campos extra en el JSON: audio_clave, frase_audio_literal y visual_clave.
10. DA PRIORIDAD a audio + acciones visuales. OCR/texto en pantalla es secundario.
11. PROHIBIDO mencionar "IA", "AI", "inteligencia artificial", "chatgpt", "gemini" en título/descripcion.
12. Devuelve EXCLUSIVAMENTE JSON válido con esta estructura exacta:
{
  "titulo": "Título Gancho Corto Aquí",
  "descripcion": "Descripción ultracorta (1 o 2 líneas). Incluye 1 o 2 emojis.",
  "audio_clave": "resumen de lo escuchado en el audio",
  "frase_audio_literal": "frase exacta detectada en audio o sin_voz_clara",
  "visual_clave": "acción visual principal del clip"${categoryField}
}
${categoryRules}
Contexto del creador:
${context}
`;
}

function sanitizeText(value, maxLen) {
  const txt = String(value || "").replace(/\s+/g, " ").trim();
  if (txt.length <= maxLen) return txt;
  return txt.slice(0, maxLen).trim();
}

export class AIService {
  constructor() {
    this.keys = GEMINI_API_KEYS;
  }

  async generateMetadata({ videoPath, brand, categoryId, extraContext = "", progressCallback }) {
    const effectiveCategory = categoryId || defaultContentTypeForBrand(brand);
    const fileHint = fromFilename(videoPath);

    if (this.keys.length === 0) {
      return {
        titulo: `${FALLBACK_TITLES[effectiveCategory] || "Nuevo video"}: ${fileHint}`.slice(0, 90),
        descripcion: `Contenido sobre ${effectiveCategory.replace(/_/g, " ")} listo para publicar. 💥`,
        audio_clave: "",
        frase_audio_literal: "sin_voz_clara",
        visual_clave: fileHint,
        category_id: effectiveCategory,
        model_used: "Fallback",
      };
    }

    let lastError;

    for (const modelName of MODEL_PRIORITY) {
      for (const key of this.keys) {
        const ai = new GoogleGenAI({ apiKey: key });
        let uploadedFile = null;
        try {
          if (progressCallback)
            progressCallback(friendlyModelName(modelName), "uploading");

          uploadedFile = await ai.files.upload({
            file: videoPath,
            config: { mimeType: inferMimeType(videoPath) },
          });

          let state = uploadedFile?.state;
          while (state === FileState.PROCESSING) {
            await sleep(3000);
            uploadedFile = await ai.files.get({ name: uploadedFile.name });
            state = uploadedFile?.state;
          }

          if (state === FileState.FAILED) {
            throw new Error("El archivo falló durante procesamiento en Gemini");
          }

          const context = [
            buildBrandContext(brand),
            `Categoría sugerida: ${effectiveCategory}.`,
            extraContext ? String(extraContext).trim() : "",
          ]
            .filter(Boolean)
            .join("\n");

          const prompt = buildPrompt({
            context,
            categoryId: effectiveCategory,
            enforceGymarkCategory:
              brand === "gymark" && !String(categoryId || "").trim(),
          });

          if (progressCallback)
            progressCallback(friendlyModelName(modelName), "generating");

          const result = await ai.models.generateContent({
            model: modelName,
            contents: [
              {
                role: "user",
                parts: [
                  {
                    fileData: {
                      fileUri: uploadedFile?.uri,
                      mimeType: uploadedFile?.mimeType || inferMimeType(videoPath),
                    },
                  },
                  { text: prompt },
                ],
              },
            ],
            config: { responseMimeType: "application/json", temperature: 0.85 },
          });

          const parsed = JSON.parse(cleanJsonText(result.text));

          return {
            titulo: sanitizeText(parsed.titulo || FALLBACK_TITLES[effectiveCategory] || fileHint, 90),
            descripcion: sanitizeText(parsed.descripcion || `Contenido sobre ${effectiveCategory.replace(/_/g, " ")}.`, 280),
            audio_clave: sanitizeText(parsed.audio_clave || "", 280),
            frase_audio_literal: sanitizeText(parsed.frase_audio_literal || "sin_voz_clara", 280),
            visual_clave: sanitizeText(parsed.visual_clave || "", 280),
            category_id: sanitizeText(parsed.category_id || effectiveCategory, 60) || effectiveCategory,
            model_used: friendlyModelName(modelName),
          };
        } catch (error) {
          lastError = error;
        } finally {
          if (uploadedFile?.name) {
            try {
              await ai.files.delete({ name: uploadedFile.name });
            } catch {}
          }
        }
      }
    }

    throw new Error(lastError?.message || "No se pudo generar metadata con IA");
  }
}
