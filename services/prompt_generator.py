"""Сервис генерации специализированных промптов через OpenRouter."""

import logging

from services.openrouter_client import (
    PROMPT_MAX_TOKENS,
    build_openrouter_error,
    generate_text,
)
from services.rate_limiter import llm_limiter

logger = logging.getLogger(__name__)

PRESENTATION_PROMPT = """\
Ты — эксперт по созданию презентаций. На основе описания пользователя создай детальный промпт для генерации презентации.

Промпт должен включать:
- Тему и цель презентации
- Целевую аудиторию
- Структуру слайдов (заголовок, тезисы, заметки для спикера)
- Стиль оформления
- Количество слайдов

Формат: готовый промпт, который можно скопировать в Gamma, Google Slides AI или ChatGPT.

Описание пользователя:
{user_text}
"""

VIDEO_PROMPT = """\
Ты — эксперт по созданию контента для NotebookLM Video и видео-подкастов.
На основе описания пользователя создай инструкцию для NotebookLM Video Overview.

Инструкция должна содержать:
- На чём фокусироваться
- Какие вопросы разобрать
- Стиль подачи (формальный/разговорный)
- Что НЕ включать
- Целевая длительность

Формат: готовый текст для поля Customize в NotebookLM.

Описание пользователя:
{user_text}
"""

INFOGRAPHIC_PROMPT = """\
Ты — эксперт по визуализации данных и инфографике.
На основе описания пользователя создай детальный промпт для генерации инфографики.

Промпт должен включать:
- Главный тезис / заголовок
- Ключевые данные и факты для визуализации
- Тип инфографики (timeline, сравнение, процесс, статистика)
- Цветовую схему и стиль
- Формат и размер

Формат: готовый промпт для Canva AI, Napkin AI или Piktochart.

Описание пользователя:
{user_text}
"""


async def _generate_prompt(prompt: str, log_label: str) -> str:
    """Отправляет промпт в OpenRouter и возвращает сгенерированный текст."""
    try:
        logger.info("Генерирую %s через OpenRouter...", log_label)
        response_text = await llm_limiter.execute(
            lambda: generate_text(
                prompt,
                system_prompt=(
                    "Отвечай строго на русском языке. "
                    "Верни только готовый промпт без служебных комментариев."
                ),
                max_tokens=PROMPT_MAX_TOKENS,
            )
        )
    except RuntimeError:
        raise
    except Exception as error:
        raise build_openrouter_error(
            error,
            "Ошибка генерации промпта через OpenRouter",
        ) from error

    return response_text.strip()


async def generate_presentation_prompt(user_text: str) -> str:
    """Генерирует промпт для создания презентации."""
    prompt = PRESENTATION_PROMPT.format(user_text=user_text)
    return await _generate_prompt(prompt, "промпт для презентации")


async def generate_video_prompt(user_text: str) -> str:
    """Генерирует промпт для NotebookLM Video Overview."""
    prompt = VIDEO_PROMPT.format(user_text=user_text)
    return await _generate_prompt(prompt, "промпт для видео")


async def generate_infographic_prompt(user_text: str) -> str:
    """Генерирует промпт для инфографики."""
    prompt = INFOGRAPHIC_PROMPT.format(user_text=user_text)
    return await _generate_prompt(prompt, "промпт для инфографики")
