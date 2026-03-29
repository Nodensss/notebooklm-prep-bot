# Обработчик команды /start

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()

WELCOME_TEXT = (
    "Привет! Я — бот-упаковщик для NotebookLM.\n\n"
    "Отправь мне видео с лекцией или уроком, и я подготовлю "
    "интерактивные материалы для быстрого усвоения "
    "и пакет для NotebookLM.\n\n"
    "Поддерживаемые форматы: видео, видеосообщения (кружочки) "
    "и документы (mp4, mkv, webm)."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Приветственное сообщение с описанием возможностей бота."""
    await message.answer(WELCOME_TEXT)
