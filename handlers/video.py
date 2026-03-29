# Обработчик входящих видео, видеосообщений и документов

from aiogram import F, Router
from aiogram.types import Message

router = Router()

# Допустимые MIME-типы для документов с видео
VIDEO_MIME_TYPES = {"video/mp4", "video/x-matroska", "video/webm"}


@router.message(F.video)
async def handle_video(message: Message) -> None:
    """Обработка обычного видео."""
    await message.answer("Видео получено, начинаю обработку...")


@router.message(F.video_note)
async def handle_video_note(message: Message) -> None:
    """Обработка видеосообщения (кружочка)."""
    await message.answer("Видео получено, начинаю обработку...")


@router.message(F.document)
async def handle_document(message: Message) -> None:
    """Обработка документа — принимаем только видеофайлы."""
    if message.document and message.document.mime_type in VIDEO_MIME_TYPES:
        await message.answer("Видео получено, начинаю обработку...")
    else:
        await message.answer(
            "Пожалуйста, отправьте видеофайл (mp4, mkv или webm)."
        )
