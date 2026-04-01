"""Сервис генерации специализированных промптов через GigaChat API."""

import logging

from services.gigachat_client import TEXT_MODEL, chat_text
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
    """Отправляет промпт в GigaChat и возвращает сгенерированный текст."""
    try:
        logger.info("Генерирую %s через GigaChat...", log_label)
        return await llm_limiter.execute(
            lambda: chat_text(prompt, model=TEXT_MODEL)
        )
    except Exception as error:
        error_text = str(error)
        if "401" in error_text:
            raise RuntimeError(
                "Неверный GIGACHAT_CREDENTIALS. Проверьте ключ в .env"
            ) from error
        raise RuntimeError(
            f"Ошибка генерации промпта через GigaChat: {error_text}"
        ) from error


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
