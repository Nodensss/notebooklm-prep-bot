# Обработчик входящих видео, видеосообщений и документов

import logging
import os
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from services.formatter import format_for_learning, generate_notebooklm_prompt
from services.transcribe import process_video

logger = logging.getLogger(__name__)
router = Router()

# Допустимые MIME-типы для документов с видео
VIDEO_MIME_TYPES = {"video/mp4", "video/x-matroska", "video/webm"}

# Директория для временных файлов
TMP_DIR = Path("tmp")

# Максимальная длина одного сообщения Telegram
MAX_MESSAGE_LENGTH = 4096

# Хранилище результатов по user_id
_user_results: dict[int, dict] = {}

# Маппинг callback-данных на ключи результатов и заголовки
_SECTION_INFO = {
    "key_points": ("key_points", "📋 Ключевые тезисы"),
    "plan": ("plan", "📝 План видео"),
    "quiz": ("quiz", "❓ Вопросы для самопроверки"),
    "cards": ("cards", "🃏 Карточки для запоминания"),
    "practice": ("practice", "💪 Практическое задание"),
    "notebooklm_prompt": ("notebooklm_prompt", "🎙 Промпт для NotebookLM"),
}


def _build_keyboard() -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру с разделами учебного пакета."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Тезисы", callback_data="key_points"),
            InlineKeyboardButton(text="📝 План", callback_data="plan"),
        ],
        [
            InlineKeyboardButton(text="❓ Самопроверка", callback_data="quiz"),
            InlineKeyboardButton(text="🃏 Карточки", callback_data="cards"),
        ],
        [
            InlineKeyboardButton(text="💪 Практика", callback_data="practice"),
            InlineKeyboardButton(
                text="🎙 Промпт NotebookLM", callback_data="notebooklm_prompt"
            ),
        ],
        [
            InlineKeyboardButton(text="📄 Скачать всё", callback_data="download_all"),
            InlineKeyboardButton(
                text="📥 Пакет для NotebookLM", callback_data="download_notebooklm"
            ),
        ],
    ])


async def _download_file(bot: Bot, file_id: str) -> str:
    """Скачивает файл из Telegram и сохраняет во временную директорию.

    Args:
        bot: экземпляр бота.
        file_id: идентификатор файла в Telegram.

    Returns:
        Путь к скачанному файлу.
    """
    TMP_DIR.mkdir(exist_ok=True)
    tg_file = await bot.get_file(file_id)
    ext = Path(tg_file.file_path).suffix if tg_file.file_path else ".mp4"
    local_path = str(TMP_DIR / f"{uuid.uuid4().hex}{ext}")
    await bot.download_file(tg_file.file_path, local_path)
    logger.info("Файл скачан: %s (%.1f МБ)", local_path,
                Path(local_path).stat().st_size / 1024 / 1024)
    return local_path


async def _send_long_text(message: Message, text: str) -> None:
    """Отправляет длинный текст, разбивая на части по 4096 символов.

    Разбивка идёт по границам строк, чтобы не резать слова.

    Args:
        message: сообщение для ответа.
        text: текст для отправки.
    """
    while text:
        if len(text) <= MAX_MESSAGE_LENGTH:
            await message.answer(text)
            break

        # Ищем последний перенос строки в пределах лимита
        split_pos = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        if split_pos == -1:
            split_pos = text.rfind(" ", 0, MAX_MESSAGE_LENGTH)
        if split_pos == -1:
            split_pos = MAX_MESSAGE_LENGTH

        await message.answer(text[:split_pos])
        text = text[split_pos:].lstrip()


async def _process_and_reply(message: Message, file_id: str) -> None:
    """Общая логика: скачать → транскрибировать → форматировать → ответить.

    Args:
        message: входящее сообщение.
        file_id: идентификатор файла в Telegram.
    """
    status_msg = await message.answer("⏳ Скачиваю видео...")
    video_path = None

    try:
        video_path = await _download_file(message.bot, file_id)

        # Извлечение аудио и транскрипция
        await status_msg.edit_text("⏳ Извлекаю аудио...")
        transcript = await process_video(video_path)

        if not transcript:
            await status_msg.edit_text(
                "⚠️ Не удалось распознать речь. "
                "Возможно, в видео нет разговорной речи."
            )
            return

        # Структурирование через Gemini
        await status_msg.edit_text("⏳ Структурирую материал...")
        learning_pack = await format_for_learning(transcript)

        await status_msg.edit_text("⏳ Генерирую промпт для NotebookLM...")
        notebooklm_prompt = await generate_notebooklm_prompt(
            transcript, learning_pack
        )

        # Сохраняем результаты для inline-кнопок
        user_id = message.from_user.id
        _user_results[user_id] = {
            "transcript": transcript,
            "learning_pack": learning_pack,
            "notebooklm_prompt": notebooklm_prompt,
        }

        # Отправляем «Суть за 30 секунд» с клавиатурой
        await status_msg.edit_text("✅ Готово!")

        summary = learning_pack.get("summary", "")
        summary_text = f"📌 *Суть за 30 секунд*\n\n{summary}" if summary else (
            "Материал обработан. Выберите раздел:"
        )

        await message.answer(
            summary_text,
            reply_markup=_build_keyboard(),
            parse_mode="Markdown",
        )

    except FileNotFoundError as e:
        logger.error("Файл не найден: %s", e)
        await status_msg.edit_text(
            "❌ Не удалось скачать видео. Попробуйте ещё раз."
        )

    except (ValueError, RuntimeError) as e:
        logger.error("Ошибка обработки: %s", e)
        await status_msg.edit_text(f"❌ {e}")

    except Exception:
        logger.exception("Неожиданная ошибка при обработке видео")
        await status_msg.edit_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте позже."
        )

    finally:
        # Удаляем скачанное видео
        if video_path:
            try:
                os.remove(video_path)
            except OSError:
                pass


# --- Callback-обработчики для inline-кнопок ---


@router.callback_query(F.data.in_(set(_SECTION_INFO.keys())))
async def handle_section_callback(callback: CallbackQuery) -> None:
    """Отправляет выбранный раздел учебного пакета."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    if not user_data:
        await callback.message.answer("⚠️ Данные устарели. Отправьте видео заново.")
        return

    section_key, title = _SECTION_INFO[callback.data]

    # Для промпта NotebookLM берём из отдельного ключа
    if section_key == "notebooklm_prompt":
        text = user_data.get("notebooklm_prompt", "")
    else:
        text = user_data["learning_pack"].get(section_key, "")

    if not text:
        await callback.message.answer(f"{title}\n\nРаздел пуст.")
        return

    full_text = f"{title}\n\n{text}"
    await _send_long_text(callback.message, full_text)


@router.callback_query(F.data == "download_all")
async def handle_download_all(callback: CallbackQuery) -> None:
    """Отправляет полный учебный пакет как .txt файл."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    if not user_data:
        await callback.message.answer("⚠️ Данные устарели. Отправьте видео заново.")
        return

    full_text = user_data["learning_pack"].get("full_text", "")
    if not full_text:
        await callback.message.answer("⚠️ Нет данных для скачивания.")
        return

    file_bytes = full_text.encode("utf-8")
    document = BufferedInputFile(file_bytes, filename="учебный_пакет.txt")
    await callback.message.answer_document(
        document, caption="📄 Полный учебный пакет"
    )


@router.callback_query(F.data == "download_notebooklm")
async def handle_download_notebooklm(callback: CallbackQuery) -> None:
    """Отправляет пакет для NotebookLM: транскрипт + промпт-инструкция."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    if not user_data:
        await callback.message.answer("⚠️ Данные устарели. Отправьте видео заново.")
        return

    transcript = user_data.get("transcript", "")
    prompt = user_data.get("notebooklm_prompt", "")

    # Формируем единый файл: транскрипт + инструкция
    content = (
        "=" * 60 + "\n"
        "ТРАНСКРИПТ ВИДЕО\n"
        "=" * 60 + "\n\n"
        f"{transcript}\n\n"
        "=" * 60 + "\n"
        "ИНСТРУКЦИЯ ДЛЯ NOTEBOOKLM AUDIO OVERVIEW\n"
        "(скопируйте в поле Customize)\n"
        "=" * 60 + "\n\n"
        f"{prompt}\n"
    )

    file_bytes = content.encode("utf-8")
    document = BufferedInputFile(file_bytes, filename="notebooklm_пакет.txt")
    await callback.message.answer_document(
        document, caption="📥 Пакет для NotebookLM (транскрипт + инструкция)"
    )


# --- Обработчики входящих сообщений ---


@router.message(F.video)
async def handle_video(message: Message) -> None:
    """Обработка обычного видео."""
    await _process_and_reply(message, message.video.file_id)


@router.message(F.video_note)
async def handle_video_note(message: Message) -> None:
    """Обработка видеосообщения (кружочка)."""
    await _process_and_reply(message, message.video_note.file_id)


@router.message(F.document)
async def handle_document(message: Message) -> None:
    """Обработка документа — принимаем только видеофайлы."""
    if message.document and message.document.mime_type in VIDEO_MIME_TYPES:
        await _process_and_reply(message, message.document.file_id)
    else:
        await message.answer(
            "Пожалуйста, отправьте видеофайл (mp4, mkv или webm)."
        )
