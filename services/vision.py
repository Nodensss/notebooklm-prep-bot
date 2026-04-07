"""Сервис обработки изображений через GitHub Models Vision."""

import logging
from pathlib import Path

from services.llm_client import (
    VISION_MAX_TOKENS,
    analyze_image,
    build_llm_error,
)
from services.rate_limiter import llm_limiter

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 20 * 1024 * 1024
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

VISION_PROMPT = """\
Извлеки весь читаемый текст с этого изображения. Отвечай строго на русском языке.

Правила:
- Верни текст ДОСЛОВНО, как он написан на изображении.
- Сохраняй абзацы, переносы строк, списки и порядок фрагментов.
- Не пересказывай, не сокращай, не добавляй от себя.
- Игнорируй номера страниц, колонтитулы и артефакты сканирования (шум, случайные символы, точки, линии).
- Если на изображении есть иллюстрация, схема или рисунок — после текста добавь краткое описание в одном предложении в формате: [Иллюстрация: описание].
- Если текста на изображении нет — опиши содержимое изображения подробно.
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
    _validate_image(image_path)

    try:
        return await llm_limiter.execute(
            lambda: analyze_image(
                VISION_PROMPT,
                image_path,
                system_prompt=(
                    "Ты — OCR-система. Извлекай текст с изображений точно и дословно. "
                    "Отвечай строго на русском языке. Не добавляй переводов, "
                    "пояснений и лишних комментариев."
                ),
                max_tokens=VISION_MAX_TOKENS,
            )
        )
    except RuntimeError:
        raise
    except Exception as error:
        error_text = str(error).lower()
        if (
            "image" in error_text
            and (
                "unsupported" in error_text
                or "not support" in error_text
                or "multimodal" in error_text
            )
        ):
            raise RuntimeError(
                "Выбранная модель не поддерживает изображения. "
                "Укажите multimodal-модель в GITHUB_VISION_MODEL."
            ) from error
        raise build_llm_error(
            error,
            "Ошибка GitHub Models Vision",
        ) from error


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
