import logging
import re

import google.generativeai as genai

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

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

NOTEBOOKLM_PROMPT = """\
На основе транскрипта видео-урока и учебного пакета создай готовую инструкцию для NotebookLM Audio Overview (подкаст-режим).

Инструкция должна содержать:
1. НА ЧЁМ ФОКУСИРОВАТЬСЯ — главные темы и концепции из урока
2. КАКИЕ ВОПРОСЫ РАЗОБРАТЬ — ключевые вопросы для обсуждения ведущими подкаста
3. СТИЛЬ ПОДКАСТА — разговорный, дружелюбный, с примерами из жизни
4. ЧТО НЕ ВКЛЮЧАТЬ — второстепенные детали, отступления, технические подробности которые не помогут в понимании основ

Формат: готовый текст-инструкция, которую можно скопировать прямо в поле "Customize" Audio Overview в NotebookLM.

Транскрипт:
{transcript}

Учебный пакет:
{learning_pack}
"""

_SECTION_KEYWORDS = {
    "summary": ("СУТЬ", "SUMMARY", "30 СЕКУНД"),
    "key_points": ("ТЕЗИС", "KEY POINT", "КЛЮЧ"),
    "plan": ("ПЛАН", "PLAN", "СТРУКТУР"),
    "quiz": ("ВОПРОС", "QUIZ", "ПРОВЕРК"),
    "cards": ("КАРТОЧ", "FLASHCARD", "CARD"),
    "practice": ("ПРАКТИ", "ЗАДАН", "PRACTICE"),
}


def _resolve_section_key(title: str) -> str | None:
    normalized_title = title.upper().replace("Ё", "Е")
    for key, keywords in _SECTION_KEYWORDS.items():
        if any(keyword in normalized_title for keyword in keywords):
            return key
    return None


def _parse_sections(text: str) -> dict:
    """Разбирает ответ Gemini по секциям и устойчиво сопоставляет заголовки."""
    result = {key: "" for key in _SECTION_KEYWORDS}
    result["full_text"] = text

    matched_any_section = False
    parts = re.split(r"^##\s+", text, flags=re.MULTILINE)

    for part in parts:
        if not part.strip():
            continue

        first_line, _, body = part.partition("\n")
        section_key = _resolve_section_key(first_line.strip().rstrip("#").strip())
        if section_key is None:
            continue

        result[section_key] = body.strip()
        matched_any_section = True

    if not matched_any_section:
        result["summary"] = text.strip()

    return result


async def format_for_learning(transcript: str) -> dict:
    """Структурирует транскрипцию в учебный пакет через Gemini API."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY не задан. Проверьте файл .env")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = LEARNING_PACK_PROMPT.format(transcript=transcript)

    try:
        logger.info("Отправляю транскрипт в Gemini для структурирования...")
        response = await model.generate_content_async(prompt)
        full_text = response.text
    except Exception as error:
        error_str = str(error)
        if "API_KEY" in error_str or "401" in error_str:
            raise RuntimeError(
                "Неверный GEMINI_API_KEY. Проверьте ключ в .env"
            ) from error
        raise RuntimeError(f"Ошибка Gemini API: {error_str}") from error

    logger.info("Учебный пакет сгенерирован (%d символов)", len(full_text))
    return _parse_sections(full_text)


async def generate_notebooklm_prompt(transcript: str, learning_pack: dict) -> str:
    """Генерирует инструкцию для NotebookLM Audio Overview через Gemini API."""
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
    except Exception as error:
        raise RuntimeError(
            f"Ошибка генерации промпта NotebookLM: {error}"
        ) from error
