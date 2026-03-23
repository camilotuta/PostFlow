import os
import uuid

from PIL import Image

# moviepy 1.x references Image.ANTIALIAS which was removed in Pillow 10+
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS  # type: ignore[attr-defined]

import config


class VideoProcessingService:
    """Assembles a processed video by prepending an intro and/or appending an outro clip."""

    def build_video(
        self,
        *,
        source_path: str,
        output_path: str,
        intro_path: str | None = None,
        outro_path: str | None = None,
    ) -> str:
        """
        Concatenate optional intro + source + optional outro.
        Writes the result to *output_path* and returns it.
        Raises FileNotFoundError if any of the input files is missing.
        """
        from moviepy.editor import VideoFileClip, concatenate_videoclips

        for label, path in [
            ("source", source_path),
            ("intro", intro_path),
            ("outro", outro_path),
        ]:
            if path and not os.path.exists(path):
                raise FileNotFoundError(f"Archivo de {label} no encontrado: {path}")

        clips_to_close = []
        try:
            base_clip = VideoFileClip(source_path)
            clips_to_close.append(base_clip)

            base_fps = int(round(getattr(base_clip, "fps", 30) or 30))
            # NO usar subclip en el clip principal - solo set_fps
            base_clip = base_clip.set_fps(base_fps)

            timeline = []

            if intro_path:
                intro_clip = VideoFileClip(intro_path)
                intro_clip = intro_clip.resize(newsize=base_clip.size).set_fps(base_fps)
                clips_to_close.append(intro_clip)
                timeline.append(intro_clip)

            timeline.append(base_clip)

            if outro_path:
                outro_clip = VideoFileClip(outro_path)
                outro_clip = outro_clip.resize(newsize=base_clip.size).set_fps(base_fps)
                clips_to_close.append(outro_clip)
                timeline.append(outro_clip)

            if len(timeline) == 1:
                import shutil

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(source_path, output_path)
                return output_path

            # Usar 'chain' para concatenación secuencial (intro → clip → outro)
            # Es más eficiente en memoria que 'compose'
            final_clip = concatenate_videoclips(timeline, method="chain")
            clips_to_close.append(final_clip)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            tmp_audio = os.path.join(
                "/tmp",
                f"tmp-audio-{uuid.uuid4().hex}.m4a",
            )
            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                fps=base_fps,
                preset="ultrafast",
                threads=1,
                temp_audiofile=tmp_audio,
                remove_temp=True,
                logger=None,
                bitrate="2000k",
                verbose=False,
                audio_bufsize=2000,
            )
            return output_path

        finally:
            for clip in reversed(clips_to_close):
                try:
                    clip.close()
                except Exception:
                    pass
