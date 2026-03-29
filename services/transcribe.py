# Сервис транскрипции: извлечение аудио из видео и распознавание речи

import asyncio
import logging
import os
import uuid
from pathlib import Path

from openai import AsyncOpenAI

from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

# Директория для временных файлов
TMP_DIR = Path("tmp")

# Максимальный размер файла для Groq Whisper API (25 МБ)
MAX_CHUNK_SIZE = 24 * 1024 * 1024  # 24 МБ с запасом


async def extract_audio(video_path: str) -> str:
    """Извлекает аудиодорожку из видеофайла с помощью ffmpeg.

    Args:
        video_path: путь к видеофайлу.

    Returns:
        Путь к извлечённому mp3-файлу.

    Raises:
        FileNotFoundError: видеофайл не найден.
        RuntimeError: ошибка при извлечении аудио.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Видеофайл не найден: {video_path}")

    TMP_DIR.mkdir(exist_ok=True)
    audio_path = str(TMP_DIR / f"{uuid.uuid4().hex}.mp3")

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn",                    # без видеодорожки
        "-acodec", "libmp3lame",  # кодек MP3
        "-q:a", "4",              # качество (4 — хороший баланс размер/качество)
        "-y",                     # перезаписывать без вопросов
        audio_path,
    ]

    logger.info("Извлекаю аудио: %s -> %s", video_path, audio_path)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode(errors="replace")
        # Определяем тип ошибки по выводу ffmpeg
        if "No such file or directory" in error_msg:
            raise RuntimeError(
                "ffmpeg не найден. Установите его: sudo apt install ffmpeg"
            )
        if "does not contain any stream" in error_msg or "Audio" not in error_msg:
            raise RuntimeError("В видеофайле отсутствует аудиодорожка")
        raise RuntimeError(f"Ошибка ffmpeg: {error_msg[-500:]}")

    if not Path(audio_path).exists() or Path(audio_path).stat().st_size == 0:
        raise RuntimeError("Не удалось извлечь аудио — файл пуст или повреждён")

    logger.info("Аудио извлечено: %s", audio_path)
    return audio_path


async def _split_audio(audio_path: str) -> list[str]:
    """Разбивает аудиофайл на части по ~24 МБ для Groq API.

    Разбиение выполняется по длительности: сначала вычисляется общая длительность,
    затем нарезаются сегменты пропорционально лимиту размера.

    Args:
        audio_path: путь к исходному mp3-файлу.

    Returns:
        Список путей к частям.
    """
    # Получаем длительность аудио через ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *probe_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    total_duration = float(stdout.decode().strip())
    file_size = Path(audio_path).stat().st_size

    # Вычисляем длительность одного сегмента пропорционально лимиту
    segment_duration = int(total_duration * MAX_CHUNK_SIZE / file_size)
    segment_duration = max(segment_duration, 30)  # минимум 30 секунд

    prefix = TMP_DIR / f"chunk_{uuid.uuid4().hex}"
    pattern = f"{prefix}_%03d.mp3"

    split_cmd = [
        "ffmpeg", "-i", audio_path,
        "-f", "segment",
        "-segment_time", str(segment_duration),
        "-acodec", "libmp3lame", "-q:a", "4",
        "-y", pattern,
    ]

    proc = await asyncio.create_subprocess_exec(
        *split_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Собираем пути к созданным частям
    chunks = sorted(TMP_DIR.glob(f"{prefix.name}_*.mp3"))
    logger.info("Аудио разбито на %d частей", len(chunks))
    return [str(c) for c in chunks]


async def _transcribe_single(client: AsyncOpenAI, audio_path: str) -> str:
    """Транскрибирует один аудиофайл через Groq Whisper API.

    Args:
        client: OpenAI-совместимый клиент.
        audio_path: путь к аудиофайлу.

    Returns:
        Текст транскрипции.
    """
    with open(audio_path, "rb") as audio_file:
        response = await client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_file,
            response_format="text",
        )
    return response


async def transcribe_audio(audio_path: str) -> str:
    """Транскрибирует аудиофайл через Groq Whisper API.

    Если файл превышает 25 МБ — разбивает на части и транскрибирует каждую.

    Args:
        audio_path: путь к аудиофайлу.

    Returns:
        Полный текст транскрипции.

    Raises:
        ValueError: API-ключ Groq не задан.
        RuntimeError: ошибка при транскрипции.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY не задан. Проверьте файл .env")

    client = AsyncOpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    file_size = Path(audio_path).stat().st_size
    logger.info("Размер аудио: %.1f МБ", file_size / 1024 / 1024)

    chunks: list[str] = []
    try:
        if file_size > MAX_CHUNK_SIZE:
            # Файл слишком большой — разбиваем на части
            logger.info("Файл превышает 24 МБ, разбиваю на части...")
            chunks = await _split_audio(audio_path)
            parts = []
            for i, chunk_path in enumerate(chunks):
                logger.info("Транскрибирую часть %d/%d...", i + 1, len(chunks))
                text = await _transcribe_single(client, chunk_path)
                parts.append(text.strip())
            transcript = " ".join(parts)
        else:
            # Файл в пределах лимита — транскрибируем целиком
            transcript = await _transcribe_single(client, audio_path)

    except Exception as e:
        error_str = str(e)
        if "401" in error_str or "auth" in error_str.lower():
            raise RuntimeError("Неверный GROQ_API_KEY. Проверьте ключ в .env") from e
        if "413" in error_str or "too large" in error_str.lower():
            raise RuntimeError("Файл слишком большой для API") from e
        raise RuntimeError(f"Ошибка транскрипции: {error_str}") from e
    finally:
        # Удаляем временные части, если были
        for chunk_path in chunks:
            _safe_remove(chunk_path)

    return transcript.strip()


async def process_video(video_path: str) -> str:
    """Полный цикл: извлечение аудио → транскрипция → очистка.

    Args:
        video_path: путь к видеофайлу.

    Returns:
        Текст транскрипции.
    """
    audio_path = await extract_audio(video_path)
    try:
        transcript = await transcribe_audio(audio_path)
    finally:
        # Удаляем временный mp3 в любом случае
        _safe_remove(audio_path)
    return transcript


def _safe_remove(path: str) -> None:
    """Безопасно удаляет файл, игнорируя ошибки."""
    try:
        os.remove(path)
    except OSError:
        pass
