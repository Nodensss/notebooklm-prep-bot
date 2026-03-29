# Обработчик входящих видео, видеосообщений и документов

import logging
import os
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.types import Message

from services.transcribe import process_video

logger = logging.getLogger(__name__)
router = Router()

# Допустимые MIME-типы для документов с видео
VIDEO_MIME_TYPES = {"video/mp4", "video/x-matroska", "video/webm"}

# Директория для временных файлов
TMP_DIR = Path("tmp")

# Максимальная длина одного сообщения Telegram
MAX_MESSAGE_LENGTH = 4096


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
            # Нет переноса — ищем пробел
            split_pos = text.rfind(" ", 0, MAX_MESSAGE_LENGTH)
        if split_pos == -1:
            # Нет пробела — режем жёстко
            split_pos = MAX_MESSAGE_LENGTH

        await message.answer(text[:split_pos])
        text = text[split_pos:].lstrip()


async def _process_and_reply(message: Message, file_id: str) -> None:
    """Общая логика: скачать → транскрибировать → ответить.

    Args:
        message: входящее сообщение.
        file_id: идентификатор файла в Telegram.
    """
    status_msg = await message.answer("⏳ Скачиваю видео...")
    video_path = None

    try:
        video_path = await _download_file(message.bot, file_id)

        await status_msg.edit_text("⏳ Извлекаю аудио...")
        # process_video сам извлечёт аудио и транскрибирует
        transcript = await process_video(video_path)

        if not transcript:
            await status_msg.edit_text(
                "⚠️ Не удалось распознать речь. "
                "Возможно, в видео нет разговорной речи."
            )
            return

        await status_msg.edit_text("✅ Транскрипция готова!")
        await _send_long_text(message, transcript)

    except FileNotFoundError as e:
        logger.error("Файл не найден: %s", e)
        await status_msg.edit_text("❌ Не удалось скачать видео. Попробуйте ещё раз.")

    except RuntimeError as e:
        logger.error("Ошибка обработки: %s", e)
        await status_msg.edit_text(f"❌ {e}")

    except Exception as e:
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
