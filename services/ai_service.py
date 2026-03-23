import os
import json
import logging
import re
import time

import google.generativeai as genai
import config

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.gymark_categories = [
            "acc_gimnasio",
            "pilates_yoga",
            "sup_naturales",
            "ropa_deportiva",
            "sup_deportivos",
            "home_gym",
        ]
        self.model_names = [
            "models/gemini-2.5-pro",
            "models/gemini-2.5-flash",
        ]
        self.api_keys = list(getattr(config, "GEMINI_API_KEYS", []))
        self.generation_config = {
            "temperature": 0.85,
            "response_mime_type": "application/json",
        }

    @staticmethod
    def _friendly_model_name(model_name: str) -> str:
        txt = str(model_name or "").strip()
        mapping = {
            "models/gemini-2.5-pro": "Gemini 2.5 Pro",
            "models/gemini-2.5-flash": "Gemini 2.5 Flash",
        }
        return mapping.get(txt, txt.replace("models/", "").replace("-", " ").title())

    def _build_prompt(
        self, context: str, strict_audio: bool = True, category_detection: bool = False
    ) -> str:
        extra_audio_rules = ""
        if strict_audio:
            extra_audio_rules = """
                    6. PRIMERO debes escuchar y transcribir mentalmente el audio del clip antes de redactar.
                    7. El titulo y la descripcion deben reflejar una frase, palabra o intención real detectada en el audio y la acción visual principal.
                    8. Si NO hay voz clara, usa sonidos/música/efectos como contexto y coloca "sin_voz_clara" en frase_audio_literal.
                    9. Incluye 3 campos extra en el JSON: "audio_clave", "frase_audio_literal" y "visual_clave".
                    10. DA PRIORIDAD a audio + acciones visuales (qué pasa en escena). El texto en pantalla (subtítulos/OCR) es secundario.
                    11. SOLO usa texto en pantalla si coincide con lo que se oye o con la acción visual principal.
                    12. PROHIBIDO mencionar "IA", "AI", "inteligencia artificial", "chatgpt", "gemini" o similares en titulo/descripcion.
            """

        category_rules = ""
        category_field = ""
        if category_detection:
            category_rules = """
                    13. Debes clasificar el video en EXACTAMENTE una categoría de Gymark usando SOLO estas opciones:
                        - acc_gimnasio
                        - pilates_yoga
                        - sup_naturales
                        - ropa_deportiva
                        - sup_deportivos
                        - home_gym
                    14. Si dudas entre dos, elige la más específica según el producto/acción dominante del clip.
            """
            category_field = ',\n                      "category_id": "una de las 6 categorías de gymark"'

        return f"""
                    Analiza este video COMPLETO (imágenes + AUDIO: voz, diálogos, música, efectos de sonido, risas, tono, jingles, etc.).
                    Debes generar metadatos altamente optimizados para TikTok/Reels basados en lo que ves y ESCUCHAS.
                    Reglas estrictas:
                    1. Nada de títulos genéricos. El título debe tratar EXACTAMENTE de la frase más chistosa, el evento principal o el tema central del clip de audio/video.
                    2. La descripción debe ser CORTA. Nadie lee descripciones largas en TikTok/Reels. Máximo 2 oraciones.
                    3. Analiza el audio detalladamente para entender el contexto real de la situación.
                    4. Mantén el lenguaje coloquial real detectado en el contenido. Si hay groserías fuertes, inclúyelas porque se procesarán automáticamente.
                                        5. PUNTUACIÓN ESPAÑOLA OBLIGATORIA: Si la oración es exclamativa, usa '¡' al inicio y '!' al final. Si tiene pregunta, usa '¿' antes de la parte interrogativa y '?' al final. Siempre cierra cada oración con su signo correspondiente. Ej correcto: '¡Malparido! ¿Por qué me la matas?'
                                        6. Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura exacta:
                    {{
                      "titulo": "Título Gancho Corto Aquí",
                      "descripcion": "Descripción ultracorta (1 o 2 líneas). Incluye 1 o 2 emojis llamativos. Un pequeño gancho.",
                      "audio_clave": "resumen de lo escuchado en el audio",
                                            "frase_audio_literal": "frase exacta detectada en audio o sin_voz_clara",
                                                                                        "visual_clave": "acción visual principal del clip"{category_field}
                    }}
                    {extra_audio_rules}
                                        {category_rules}

                    Contexto del creador:
                    {context}
                    """

    # ── Profanity patterns (strong Spanish curse words) ──────────────
    _PROFANITY_PATTERNS: list[tuple[str, str]] = [
        # (regex_pattern, replacement_hint) – hint unused, handled by _censor_word
        # Each pattern uses word boundaries; inner letters replaced by *
        (r"maric[ao]s?", None),
        (r"marik[ao]s?", None),
        (r"hpt[ao]?s?", None),
        (r"hijuep(?:uta|uto|utas|utos)", None),
        (r"malparid[ao]s?", None),
        (r"hijueput[ao]s?", None),
        (r"gonorre[ao]s?", None),
        (r"gonorrea[s]?", None),
        (r"culicagad[ao]s?", None),
        (r"mamahuev[ao]s?", None),
        (r"putísim[ao]s?", None),
        (r"putas?", None),
        (r"putos?", None),
        (r"mierder[ao]s?", None),
        (r"est[uú]pid[ao]s?", None),
        (r"idiot[ao]s?", None),
        (r"vergas?", None),
        (r"pendej[ao]s?", None),
        (r"coñ[ao]s?", None),
        (r"mierda[s]?", None),
        (r"carajos?", None),
        (r"cabr[oó]n", None),
        (r"cabronas?", None),
        (r"candelamp?", None),
        (r"chingad[ao]s?", None),
        (r"chinga[s]?", None),
        (r"culos?", None),
        (r"hdp", None),
        (r"hp\b", None),
    ]

    @staticmethod
    def _censor_word(word: str) -> str:
        """Keep first + last letter, replace middle with *."""
        if len(word) <= 2:
            return word[0] + "*"
        if len(word) == 3:
            return word[0] + "*" + word[-1]
        return word[0] + "*" * (len(word) - 2) + word[-1]

    def _censor_profanity(self, text: str) -> str:
        """Censor strong profanity: keep first/last letter, replace middle with *."""
        if not text:
            return text
        for pattern, _ in self._PROFANITY_PATTERNS:

            def _replacer(m: re.Match) -> str:
                matched = m.group(0)
                # Preserve original casing of first/last char
                return self._censor_word(matched)

            text = re.sub(
                r"(?<![\w#])" + pattern + r"(?![\w])",
                _replacer,
                text,
                flags=re.IGNORECASE,
            )
        return text

    @staticmethod
    def _fix_spanish_punctuation(text: str) -> str:
        """Ensure correct Spanish opening/closing punctuation marks."""
        if not text:
            return text
        t = text.strip()
        # If exclamation is present but no opening ¡, prepend it
        if "!" in t and not t.startswith("¡"):
            t = "¡" + t
        # If interrogation ¿ is present but text doesn't end with ?
        if "¿" in t and not t.endswith("?"):
            t = t.rstrip(" .,;:") + "?"
        # If starts with ¡ but doesn't end with ! or ?
        if t.startswith("¡") and not re.search(r"[!?]\s*$", t):
            t = t.rstrip(" .,;:") + "!"
        return t

    def _normalize_result(self, result: dict) -> dict:
        title = str(result.get("titulo", "")).strip()
        desc = str(result.get("descripcion", "")).strip()
        tags = result.get("hashtags", []) or []
        if not isinstance(tags, list):
            tags = []

        normalized_tags = []
        seen = set()
        for tag in tags:
            txt = str(tag).strip()
            if not txt:
                continue
            if not txt.startswith("#"):
                txt = f"#{txt}"
            key = txt.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized_tags.append(txt)

        audio_key = str(result.get("audio_clave", "")).strip()
        audio_phrase = str(result.get("frase_audio_literal", "")).strip()
        visual_key = str(result.get("visual_clave", "")).strip()

        # Apply profanity censoring (punctuation fix applied later after all transforms)
        title = self._censor_profanity(title)
        desc = self._censor_profanity(desc)

        return {
            "titulo": title,
            "descripcion": desc,
            "hashtags": normalized_tags,
            "audio_clave": audio_key,
            "frase_audio_literal": audio_phrase,
            "visual_clave": visual_key,
        }

    def _remove_ai_mentions(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(
            r"\b(chatgpt|gemini|inteligencia\s+artificial|artificial\s+intelligence|ia|ai)\b",
            "",
            str(text),
            flags=re.IGNORECASE,
        )
        # Strip only neutral trailing junk, NOT Spanish punctuation (¡!¿?) which is meaningful
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .,-:;\"'")
        return cleaned

    def _smart_trim(self, text: str, limit: int) -> str:
        txt = str(text or "").strip()
        if len(txt) <= limit:
            return txt
        cut = txt[:limit].rstrip()
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        cut = cut.rstrip("\"'¡!¿?,;:.- ")
        return f"{cut}…"

    def _ensure_complete_description(self, text: str) -> str:
        desc = str(text or "").strip()
        if not desc:
            return desc

        # Si termina en puntos suspensivos, mantenerlos.
        if desc.endswith("…") or desc.endswith("..."):
            return desc

        # Si termina sin puntuación final, cerrarlo para que no se vea cortado.
        if not re.search(r"[.!?…]$", desc):
            desc = desc.rstrip("\"'¡!¿?,;:- ")
            desc = f"{desc}."

        return desc

    def _enforce_audio_alignment(self, result: dict) -> dict:
        title = self._remove_ai_mentions(str(result.get("titulo", "")).strip())
        desc = self._remove_ai_mentions(str(result.get("descripcion", "")).strip())
        audio_phrase = str(result.get("frase_audio_literal", "")).strip()
        audio_key = str(result.get("audio_clave", "")).strip()
        visual_key = str(result.get("visual_clave", "")).strip()

        if audio_phrase and audio_phrase.lower() != "sin_voz_clara":
            phrase_short = " ".join(audio_phrase.split()[:8]).strip()
            low_title = title.lower()
            low_desc = desc.lower()
            low_phrase = phrase_short.lower()

            if (
                low_phrase
                and low_phrase not in low_title
                and low_phrase not in low_desc
                and len(title) < 10
            ):
                title = phrase_short

            generic_title_tokens = {
                "video viral",
                "mira esto",
                "contenido viral",
                "no te lo pierdas",
                "imperdible",
            }
            if any(tok in low_title for tok in generic_title_tokens):
                title = phrase_short
        elif (audio_key or visual_key) and len(desc) < 12:
            desc = (audio_key or visual_key)[:200]

        if len(desc) < 18 and (audio_key or visual_key):
            desc = f"{audio_key}. {visual_key}".strip(" .")

        # Apply Spanish punctuation fix AFTER all text transforms
        result["titulo"] = self._fix_spanish_punctuation(self._smart_trim(title, 90))
        result["descripcion"] = self._ensure_complete_description(
            self._smart_trim(desc, 280)
        )
        return result

    def _looks_generic_or_audio_missing(self, result: dict) -> bool:
        title = str(result.get("titulo", "")).strip().lower()
        desc = str(result.get("descripcion", "")).strip().lower()
        audio_phrase = str(result.get("frase_audio_literal", "")).strip().lower()

        if len(title) < 8:
            return True

        generic_patterns = [
            r"video( viral)?",
            r"contenido( viral)?",
            r"mira esto",
            r"no te lo pierdas",
        ]
        if any(re.search(pattern, title) for pattern in generic_patterns):
            return True

        if not audio_phrase:
            return True
        if audio_phrase == "sin_voz_clara":
            # Permitir sin voz, pero exigir que description no sea vacía.
            return len(desc) < 8

        return False

    def _coerce_gymark_category(self, value: str) -> str:
        txt = str(value or "").strip().lower()
        return txt if txt in self.gymark_categories else ""

    def _upload_video_file(self, video_path: str):
        video_file = genai.upload_file(path=video_path)
        logger.info(f"Video subido con éxito a Gemini: URI={video_file.uri}")

        while video_file.state.name == "PROCESSING":
            logger.info("Esperando que Gemini procese el video...")
            time.sleep(3)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError("El archivo subido a Gemini falló en su procesamiento.")

        return video_file

    def _infer_gymark_category_from_text(self, result: dict) -> str:
        ai_category = self._coerce_gymark_category(result.get("category_id", ""))
        if ai_category:
            return ai_category

        text = " ".join(
            [
                str(result.get("titulo", "")),
                str(result.get("descripcion", "")),
                str(result.get("audio_clave", "")),
                str(result.get("visual_clave", "")),
            ]
        ).lower()

        keyword_map = {
            "pilates_yoga": [
                "pilates",
                "yoga",
                "mat",
                "colchoneta",
                "namaste",
                "stretch",
                "movilidad",
            ],
            "ropa_deportiva": [
                "legging",
                "licra",
                "short",
                "camiseta",
                "sudadera",
                "outfit",
                "ropa",
            ],
            "sup_naturales": [
                "natural",
                "herbal",
                "organico",
                "orgánico",
                "vitamina",
                "detox",
                "inmunidad",
            ],
            "sup_deportivos": [
                "proteina",
                "proteína",
                "creatina",
                "preworkout",
                "amino",
                "whey",
                "suplement",
            ],
            "home_gym": [
                "home gym",
                "casa",
                "entrenar en casa",
                "mancuerna",
                "rack",
                "banca",
                "setup",
            ],
            "acc_gimnasio": [
                "accesorio",
                "gimnasio",
                "guantes",
                "rodillera",
                "strap",
                "banda",
                "cinturon",
                "cinturón",
            ],
        }

        scores = {key: 0 for key in self.gymark_categories}
        for category, keywords in keyword_map.items():
            for kw in keywords:
                if kw in text:
                    scores[category] += 1

        best_category = max(scores, key=scores.get)
        if scores[best_category] > 0:
            return best_category
        return "acc_gimnasio"

    def generate_metadata(
        self,
        video_path: str,
        brand: str,
        category_id: str,
        extra_context: str = "",
        progress_callback=None,
    ) -> dict:
        """
        Sube el video a Gemini y genera título/descripcion basados
        en la marca (gymark/tatuct/milita) y la categoría.

        Args:
            extra_context: Contexto adicional o feedback del usuario para mejorar la generación.
        """
        try:
            logger.info(f"Subiendo video a Gemini IA: {video_path}")

            max_retries_per_key_model = 2
            last_error = None

            if not self.api_keys:
                raise ValueError("No hay API keys de Gemini configuradas.")

            for model_name in self.model_names:
                logger.info(
                    f"Intentando generación con modelo (prioridad): {model_name}"
                )
                friendly_model = self._friendly_model_name(model_name)
                if callable(progress_callback):
                    try:
                        progress_callback(model_name=friendly_model, phase="preparing")
                    except Exception:
                        pass

                for key_index, api_key in enumerate(self.api_keys, start=1):
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        generation_config=self.generation_config,
                    )
                    logger.info(
                        f"Usando key {key_index}/{len(self.api_keys)} con modelo {model_name}"
                    )

                    for attempt in range(max_retries_per_key_model):
                        video_file = None
                        try:
                            if callable(progress_callback):
                                try:
                                    progress_callback(
                                        model_name=friendly_model, phase="uploading"
                                    )
                                except Exception:
                                    pass
                            video_file = self._upload_video_file(video_path)
                            if callable(progress_callback):
                                try:
                                    progress_callback(
                                        model_name=friendly_model,
                                        phase="processing_video",
                                    )
                                except Exception:
                                    pass

                            context = (
                                "Marca de la cuenta: Gaming / Clips de stream (Tatuct)."
                                if brand == "tatuct"
                                else (
                                    "Marca de la cuenta: Gimnasio / Ropa deportiva (Gymark)."
                                    if brand == "gymark"
                                    else (
                                        "Cuenta personal de contenido femenino en México (@milita). "
                                        "Nicho combinado: maquillaje (tutoriales GRWM, looks diarios, transformaciones), "
                                        "fitness (rutinas, motivación, workouts), cuidado personal (skincare, hábitos), "
                                        "amor propio (self-love, mindset, empoderamiento) y tips de belleza (hacks, "
                                        "productos, técnicas). "
                                        "Audiencia objetivo: mujeres 18-34 años en México. "
                                        "Tono: cercano, empoderador, motivacional, femenino y auténtico. "
                                        "Plataforma única: TikTok México."
                                    )
                                )
                            )
                            if category_id:
                                context += f"\nCategoría de este video: {category_id}."
                            if extra_context:
                                context += f"\n{extra_context}"

                            should_detect_category = (
                                brand == "gymark"
                                and not self._coerce_gymark_category(category_id)
                            )
                            prompt = self._build_prompt(
                                context,
                                strict_audio=True,
                                category_detection=should_detect_category,
                            )

                            logger.info(
                                f"Generando contenido con {model_name} (key {key_index})..."
                            )
                            if callable(progress_callback):
                                try:
                                    progress_callback(
                                        model_name=friendly_model, phase="generating"
                                    )
                                except Exception:
                                    pass
                            response = model.generate_content([video_file, prompt])
                            raw_result = json.loads(response.text)
                            parsed_result = self._normalize_result(raw_result)
                            parsed_result = self._enforce_audio_alignment(parsed_result)
                            parsed_result["model_used"] = friendly_model

                            if brand == "gymark":
                                parsed_result["category_id"] = (
                                    self._coerce_gymark_category(category_id)
                                    or self._infer_gymark_category_from_text(raw_result)
                                    or "acc_gimnasio"
                                )
                            elif brand == "milita":
                                parsed_result["category_id"] = "milita_beauty"

                            if self._looks_generic_or_audio_missing(parsed_result):
                                last_error = ValueError(
                                    "Respuesta genérica o sin señal de audio"
                                )
                                logger.warning(
                                    f"Respuesta genérica/sin audio con {model_name} key {key_index}. Reintentando..."
                                )
                                continue

                            logger.info("Respuesta de IA parseada con éxito.")
                            time.sleep(2)
                            return parsed_result
                        except Exception as e:
                            last_error = e
                            err = str(e).lower()
                            is_quota = (
                                "429" in err or "quota" in err or "exhausted" in err
                            )
                            is_retryable = (
                                is_quota
                                or "timeout" in err
                                or "503" in err
                                or "500" in err
                            )

                            if is_quota:
                                logger.warning(
                                    f"Cuota agotada en key {key_index} con {model_name}. Pasando a la siguiente key/modelo."
                                )
                                break

                            if is_retryable and attempt < max_retries_per_key_model - 1:
                                logger.warning(
                                    f"Error temporal con {model_name} key {key_index} (Intento {attempt+1}/{max_retries_per_key_model}): {e}. Reintentando en 3s..."
                                )
                                time.sleep(3)
                                continue

                            logger.warning(
                                f"Fallo con {model_name} key {key_index}: {e}"
                            )
                            break
                        finally:
                            if video_file is not None:
                                try:
                                    genai.delete_file(video_file.name)
                                    logger.info(
                                        "Video eliminado de Gemini para liberar cuota."
                                    )
                                except Exception as cleanup_error:
                                    logger.error(
                                        f"Failed to delete video: {cleanup_error}"
                                    )

            if last_error:
                raise last_error
            raise ValueError(
                "No se pudo obtener un resultado de IA válido con enfoque en audio."
            )

        except Exception as e:
            logger.error(f"Error generando metadatos con IA: {e}")
            raise e
