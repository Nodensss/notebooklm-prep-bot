"""Сервис генерации специализированных промптов через Gemini API."""

import logging

import google.generativeai as genai

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

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
    """Отправляет промпт в Gemini и возвращает сгенерированный текст."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY не задан. Проверьте файл .env")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    try:
        logger.info("Генерирую %s через Gemini...", log_label)
        response = await model.generate_content_async(prompt)
    except Exception as error:
        error_text = str(error)
        if "API_KEY" in error_text or "401" in error_text:
            raise RuntimeError(
                "Неверный GEMINI_API_KEY. Проверьте ключ в .env"
            ) from error
        raise RuntimeError(
            f"Ошибка генерации промпта через Gemini: {error_text}"
        ) from error

    return (response.text or "").strip()


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
