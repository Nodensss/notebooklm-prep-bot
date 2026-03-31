"""Сервис обработки изображений через Gemini Vision."""

import asyncio
import logging
from pathlib import Path

import google.generativeai as genai

from config import GEMINI_API_KEY
from services.rate_limiter import gemini_limiter

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
MAX_IMAGE_SIZE = 20 * 1024 * 1024
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

VISION_PROMPT = """\
Проанализируй изображение и ответь строго на русском языке в двух блоках.

1. ТЕКСТ С ИЗОБРАЖЕНИЯ
- Если на изображении есть читаемый текст, извлеки его максимально дословно.
- Не пересказывай, не сокращай и не упрощай формулировки.
- Сохраняй абзацы, списки и порядок фрагментов настолько близко к оригиналу, насколько это возможно.

2. ОПИСАНИЕ ИЛЛЮСТРАЦИЙ
- Кратко опиши все значимые картинки, предметы, схемы или декоративные элементы.
- Если кроме текста на изображении нет важных иллюстраций, так и напиши.

Если текст на изображении отсутствует, в первом блоке напиши: "Текст не обнаружен."
"""


def _validate_image(image_path: str) -> None:
    """Проверяет существование, размер и расширение изображения."""
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"Изображение не найдено: {image_path}")

    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(
            "Неподдерживаемый формат изображения. Поддерживаются JPEG, PNG, WebP и GIF."
        )

    if path.stat().st_size > MAX_IMAGE_SIZE:
        raise ValueError("Размер изображения превышает 20 МБ.")


async def describe_image(image_path: str) -> str:
    """Возвращает подробное описание изображения на русском языке."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY не задан. Проверьте файл .env")

    _validate_image(image_path)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    uploaded_file = None
    try:
        uploaded_file = await asyncio.to_thread(genai.upload_file, path=image_path)

        async def _call():
            return await model.generate_content_async([VISION_PROMPT, uploaded_file])

        response = await gemini_limiter.execute(_call)
    except RuntimeError:
        raise
    except Exception as error:
        error_text = str(error)
        if "API_KEY" in error_text or "401" in error_text:
            raise RuntimeError(
                "Неверный GEMINI_API_KEY. Проверьте ключ в .env"
            ) from error
        raise RuntimeError(f"Ошибка Gemini Vision: {error_text}") from error
    finally:
        if uploaded_file is not None:
            try:
                await asyncio.to_thread(genai.delete_file, uploaded_file.name)
            except Exception:
                logger.warning(
                    "Не удалось удалить временный файл Gemini: %s",
                    uploaded_file.name,
                )

    return (response.text or "").strip()


async def describe_images(
    image_paths: list[str],
    progress_callback=None,
) -> str:
    """Обрабатывает несколько изображений и объединяет описания в один текст.

    Args:
        image_paths: список путей к изображениям.
        progress_callback: опциональная async-функция(current, total) для отчёта о прогрессе.
    """
    descriptions: list[str] = []
    total = len(image_paths)

    for index, image_path in enumerate(image_paths, start=1):
        if progress_callback:
            await progress_callback(index, total)
        description = await describe_image(image_path)
        descriptions.append(f"Изображение {index}:\n{description}")

    return "\n\n".join(descriptions).strip()
