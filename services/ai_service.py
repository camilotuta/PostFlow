import os
import json
import logging
import re
import google.generativeai as genai
import config

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.model_names = [
            "models/gemini-2.5-pro",
            "models/gemini-2.5-flash",
        ]
        self.api_keys = list(getattr(config, "GEMINI_API_KEYS", []))
        self.generation_config = {
            "temperature": 0.85,
            "response_mime_type": "application/json"
        }

    def _build_prompt(self, context: str, strict_audio: bool = True) -> str:
        extra_audio_rules = ""
        if strict_audio:
            extra_audio_rules = """
                    9. PRIMERO debes escuchar y transcribir mentalmente el audio del clip antes de redactar.
                    10. El titulo y la descripcion deben reflejar una frase, palabra o intención real detectada en el audio y la acción visual principal.
                    11. Si NO hay voz clara, usa sonidos/música/efectos como contexto y coloca "sin_voz_clara" en frase_audio_literal.
                    12. Incluye 3 campos extra en el JSON: "audio_clave", "frase_audio_literal" y "visual_clave".
                    13. DA PRIORIDAD a audio + acciones visuales (qué pasa en escena). El texto en pantalla (subtítulos/OCR) es secundario.
                    14. SOLO usa texto en pantalla si coincide con lo que se oye o con la acción visual principal.
                    15. PROHIBIDO mencionar "IA", "AI", "inteligencia artificial", "chatgpt", "gemini" o similares en titulo/descripcion.
            """

        return f"""
                    Analiza este video COMPLETO (imágenes + AUDIO: voz, diálogos, música, efectos de sonido, risas, tono, jingles, etc.).
                    Debes generar metadatos altamente optimizados para TikTok/Reels basados en lo que ves y ESCUCHAS.
                    Reglas estrictas:
                    1. Nada de títulos genéricos. El título debe tratar EXACTAMENTE de la frase más chistosa, el evento principal o el tema central del clip de audio/video.
                    2. La descripción debe ser CORTA. Nadie lee descripciones largas en TikTok/Reels. Máximo 2 oraciones.
                    3. Analiza el audio detalladamente para entender el contexto real de la situación.
                    4. NO censures ni reemplaces letras de palabras del clip. Mantén el lenguaje original detectado en el contenido.
                    5. Los hashtags DEBEN ser específicos del contenido real de ESTE video: palabras clave de la escena, juego/producto, acción, chiste, frase o tema exacto del audio.
                    6. Evita hashtags genéricos repetidos entre videos (ej: #viral, #fyp, #parati) salvo máximo 1 de ese tipo.
                    7. Genera entre 8 y 12 hashtags únicos, en minúsculas y empezando por #.
                    8. Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura exacta:
                    {{
                      "titulo": "Título Gancho Corto Aquí",
                      "descripcion": "Descripción ultracorta (1 o 2 líneas). Incluye 1 o 2 emojis llamativos. Un pequeño gancho.",
                      "hashtags": ["#nicho1", "#viral2"],
                      "audio_clave": "resumen de lo escuchado en el audio",
                                            "frase_audio_literal": "frase exacta detectada en audio o sin_voz_clara",
                                            "visual_clave": "acción visual principal del clip"
                    }}
                    {extra_audio_rules}

                    Contexto del creador:
                    {context}
                    """

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
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .,-:;\"'¡!¿?")
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

            if low_phrase and low_phrase not in low_title and low_phrase not in low_desc and len(title) < 10:
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

        result["titulo"] = self._smart_trim(title, 90)
        result["descripcion"] = self._ensure_complete_description(self._smart_trim(desc, 280))
        return result

    def _looks_generic_or_audio_missing(self, result: dict) -> bool:
        title = str(result.get("titulo", "")).strip().lower()
        desc = str(result.get("descripcion", "")).strip().lower()
        tags = [str(t).lower() for t in (result.get("hashtags", []) or [])]
        audio_phrase = str(result.get("frase_audio_literal", "")).strip().lower()

        if len(title) < 8:
            return True
        if len(tags) < 5:
            return True

        generic_patterns = [
            r"video( viral)?",
            r"contenido( viral)?",
            r"mira esto",
            r"no te lo pierdas",
        ]
        if any(re.search(pattern, title) for pattern in generic_patterns):
            return True

        generic_count = sum(1 for t in tags if t in {"#viral", "#fyp", "#parati", "#trending"})
        if generic_count >= 3:
            return True

        if not audio_phrase:
            return True
        if audio_phrase == "sin_voz_clara":
            # Permitir sin voz, pero exigir que description no sea vacía.
            return len(desc) < 8

        return False
    
    def generate_metadata(self, video_path: str, brand: str, category_id: str) -> dict:
        """
        Sube el video a Gemini y genera título, descripción y hashtags basados
        en la marca (gymark/tatuct) y el tipo de contenido/categoría.
        """
        try:
            logger.info(f"Subiendo video a Gemini IA: {video_path}")
            
            import time
            max_retries_per_key_model = 2
            last_error = None

            if not self.api_keys:
                raise ValueError("No hay API keys de Gemini configuradas.")

            for model_name in self.model_names:
                logger.info(f"Intentando generación con modelo (prioridad): {model_name}")

                for key_index, api_key in enumerate(self.api_keys, start=1):
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        generation_config=self.generation_config,
                    )
                    logger.info(f"Usando key {key_index}/{len(self.api_keys)} con modelo {model_name}")

                    for attempt in range(max_retries_per_key_model):
                        video_file = None
                        try:
                            video_file = genai.upload_file(path=video_path)
                            logger.info(f"Video subido con éxito: URI={video_file.uri}")

                            while video_file.state.name == "PROCESSING":
                                logger.info("Esperando que Gemini procese el video...")
                                time.sleep(3)
                                video_file = genai.get_file(video_file.name)

                            if video_file.state.name == "FAILED":
                                raise ValueError("El archivo subido a Gemini falló en su procesamiento.")

                            context = (
                                "Marca de la cuenta: Gaming / Clips de stream (Tatuct)."
                                if brand == "tatuct"
                                else "Marca de la cuenta: Gimnasio / Ropa deportiva (Gymark)."
                            )
                            if category_id:
                                context += f"\nCategoría de este video: {category_id}."

                            prompt = self._build_prompt(context, strict_audio=True)

                            logger.info(f"Generando contenido con {model_name} (key {key_index})...")
                            response = model.generate_content([video_file, prompt])
                            parsed_result = self._normalize_result(json.loads(response.text))
                            parsed_result = self._enforce_audio_alignment(parsed_result)

                            if self._looks_generic_or_audio_missing(parsed_result):
                                last_error = ValueError("Respuesta genérica o sin señal de audio")
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
                            is_quota = "429" in err or "quota" in err or "exhausted" in err
                            is_retryable = is_quota or "timeout" in err or "503" in err or "500" in err

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

                            logger.warning(f"Fallo con {model_name} key {key_index}: {e}")
                            break
                        finally:
                            if video_file is not None:
                                try:
                                    genai.delete_file(video_file.name)
                                    logger.info("Video eliminado de Gemini para liberar cuota.")
                                except Exception as cleanup_error:
                                    logger.error(f"Failed to delete video: {cleanup_error}")

            if last_error:
                raise last_error
            raise ValueError("No se pudo obtener un resultado de IA válido con enfoque en audio.")


        except Exception as e:
            logger.error(f"Error generando metadatos con IA: {e}")
            raise e
