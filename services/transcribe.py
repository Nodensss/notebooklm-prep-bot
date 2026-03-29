# Сервис транскрипции: извлечение аудио из видео и распознавание речи

from pathlib import Path


async def extract_audio(video_path: Path) -> Path:
    """Извлекает аудиодорожку из видеофайла с помощью ffmpeg.

    Args:
        video_path: путь к видеофайлу.

    Returns:
        Путь к извлечённому аудиофайлу (mp3).
    """
    # TODO: реализовать извлечение аудио через ffmpeg
    audio_path = video_path.with_suffix(".mp3")
    return audio_path


async def transcribe_audio(audio_path: Path) -> str:
    """Транскрибирует аудиофайл через Groq Whisper API.

    Args:
        audio_path: путь к аудиофайлу.

    Returns:
        Текст транскрипции.
    """
    # TODO: реализовать вызов Groq Whisper API через openai-совместимый клиент
    return ""
