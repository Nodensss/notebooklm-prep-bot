"""Сервис обработки изображений через GigaChat."""

import logging
from pathlib import Path

from services.gigachat_client import VISION_MODEL, chat_with_image
from services.rate_limiter import llm_limiter

logger = logging.getLogger(__name__)

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
    """Возвращает описание изображения через GigaChat Vision."""
    _validate_image(image_path)

    try:
        return await llm_limiter.execute(
            lambda: chat_with_image(
                VISION_PROMPT,
                image_path,
                model=VISION_MODEL,
            )
        )
    except Exception as error:
        error_text = str(error)
        if "401" in error_text:
            raise RuntimeError(
                "Неверный GIGACHAT_CREDENTIALS. Проверьте ключ в .env"
            ) from error

        logger.warning("Обработка изображения через GigaChat недоступна: %s", error)
        raise RuntimeError(
            "Обработка изображений недоступна на текущем тарифе GigaChat"
        ) from error


async def describe_images(
    image_paths: list[str],
    progress_callback=None,
) -> str:
    """Обрабатывает несколько изображений и объединяет описания в один текст."""
    descriptions: list[str] = []
    total = len(image_paths)

    for index, image_path in enumerate(image_paths, start=1):
        if progress_callback:
            await progress_callback(index, total)
        description = await describe_image(image_path)
        descriptions.append(f"Изображение {index}:\n{description}")

    return "\n\n".join(descriptions).strip()
