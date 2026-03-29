# Сервис форматирования: структурирование транскрипции через Gemini API

import logging
import re

import google.generativeai as genai

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Модель Gemini для генерации
GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

# Промпт для создания учебного пакета
LEARNING_PACK_PROMPT = """\
Ты — эксперт по обучению и быстрому усвоению материала.
Проанализируй транскрипт видео-урока и создай структурированный учебный пакет.

Ответ СТРОГО в следующем формате с точными заголовками:

## СУТЬ ЗА 30 СЕКУНД
Главная мысль в 2-3 предложениях.

## КЛЮЧЕВЫЕ ТЕЗИСЫ
5-7 главных пунктов, каждый — 1-2 предложения.

## ПЛАН ВИДЕО
Разбивка по темам (примерные таймкоды на основе позиции в тексте).

## ВОПРОСЫ ДЛЯ САМОПРОВЕРКИ
5 вопросов с короткими ответами.

## КАРТОЧКИ ДЛЯ ЗАПОМИНАНИЯ
7-10 пар в формате:
❓ вопрос/термин
✅ ответ/определение

## ПРАКТИЧЕСКОЕ ЗАДАНИЕ
1-2 задания для закрепления.

Транскрипт:
{transcript}
"""

# Промпт для генерации инструкции NotebookLM
NOTEBOOKLM_PROMPT = """\
На основе транскрипта видео-урока и учебного пакета создай готовую инструкцию \
для NotebookLM Audio Overview (подкаст-режим).

Инструкция должна содержать:
1. НА ЧЁМ ФОКУСИРОВАТЬСЯ — главные темы и концепции из урока
2. КАКИЕ ВОПРОСЫ РАЗОБРАТЬ — ключевые вопросы для обсуждения ведущими подкаста
3. СТИЛЬ ПОДКАСТА — разговорный, дружелюбный, с примерами из жизни
4. ЧТО НЕ ВКЛЮЧАТЬ — второстепенные детали, отступления, технические подробности \
которые не помогут в понимании основ

Формат: готовый текст-инструкция, которую можно скопировать прямо в поле \
"Customize" Audio Overview в NotebookLM.

Транскрипт:
{transcript}

Учебный пакет:
{learning_pack}
"""

# Маппинг заголовков разделов на ключи dict
_SECTION_MAP = {
    "СУТЬ ЗА 30 СЕКУНД": "summary",
    "КЛЮЧЕВЫЕ ТЕЗИСЫ": "key_points",
    "ПЛАН ВИДЕО": "plan",
    "ВОПРОСЫ ДЛЯ САМОПРОВЕРКИ": "quiz",
    "КАРТОЧКИ ДЛЯ ЗАПОМИНАНИЯ": "cards",
    "ПРАКТИЧЕСКОЕ ЗАДАНИЕ": "practice",
}


def _parse_sections(text: str) -> dict:
    """Разбирает ответ Gemini на разделы по заголовкам '## НАЗВАНИЕ'.

    Args:
        text: полный текст ответа от Gemini.

    Returns:
        dict с ключами: summary, key_points, plan, quiz, cards, practice, full_text.
    """
    result = {key: "" for key in _SECTION_MAP.values()}
    result["full_text"] = text

    # Разбиваем по заголовкам второго уровня
    parts = re.split(r"^## ", text, flags=re.MULTILINE)

    for part in parts:
        if not part.strip():
            continue
        # Первая строка — заголовок
        first_line, _, body = part.partition("\n")
        title = first_line.strip().rstrip("#").strip()

        for section_title, key in _SECTION_MAP.items():
            if section_title in title.upper():
                result[key] = body.strip()
                break

    return result


async def format_for_learning(transcript: str) -> dict:
    """Структурирует транскрипцию в учебный пакет через Google Gemini API.

    Args:
        transcript: текст транскрипции.

    Returns:
        dict с ключами: summary, key_points, plan, quiz, cards, practice, full_text.

    Raises:
        ValueError: API-ключ Gemini не задан.
        RuntimeError: ошибка при обращении к Gemini API.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY не задан. Проверьте файл .env")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = LEARNING_PACK_PROMPT.format(transcript=transcript)

    try:
        logger.info("Отправляю транскрипт в Gemini для структурирования...")
        response = await model.generate_content_async(prompt)
        full_text = response.text
    except Exception as e:
        error_str = str(e)
        if "API_KEY" in error_str or "401" in error_str:
            raise RuntimeError(
                "Неверный GEMINI_API_KEY. Проверьте ключ в .env"
            ) from e
        raise RuntimeError(f"Ошибка Gemini API: {error_str}") from e

    logger.info("Учебный пакет сгенерирован (%d символов)", len(full_text))
    return _parse_sections(full_text)


async def generate_notebooklm_prompt(
    transcript: str, learning_pack: dict
) -> str:
    """Генерирует инструкцию для NotebookLM Audio Overview через Gemini API.

    Args:
        transcript: текст транскрипции.
        learning_pack: dict с учебным пакетом (результат format_for_learning).

    Returns:
        Готовый текст инструкции для NotebookLM.

    Raises:
        RuntimeError: ошибка при обращении к Gemini API.
    """
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = NOTEBOOKLM_PROMPT.format(
        transcript=transcript,
        learning_pack=learning_pack.get("full_text", ""),
    )

    try:
        logger.info("Генерирую инструкцию для NotebookLM...")
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(
            f"Ошибка генерации промпта NotebookLM: {e}"
        ) from e
