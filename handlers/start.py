# Обработчики команд /start и /help

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router()

WELCOME_TEXT = (
    "Привет! Я — бот-упаковщик для NotebookLM.\n\n"
    "Отправь мне видео с лекцией или уроком, и я подготовлю "
    "интерактивные материалы для быстрого усвоения "
    "и пакет для NotebookLM. Ещё я умею генерировать промпты для "
    "презентаций, видео и инфографики.\n\n"
    "Поддерживаемые форматы: видео, изображения, PDF, DOCX, TXT и текст.\n"
    "Подробнее — /help"
)

HELP_TEXT = (
    "📚 *Упаковщик для NotebookLM — справка*\n\n"
    "*Что делает бот:*\n"
    "Принимает учебный материал и создаёт структурированный пакет:\n"
    "• Суть за 30 секунд\n"
    "• Ключевые тезисы\n"
    "• План видео/материала\n"
    "• Вопросы для самопроверки\n"
    "• Карточки для запоминания\n"
    "• Практическое задание\n"
    "• Готовый промпт для NotebookLM Audio Overview\n\n"
    "*Поддерживаемые форматы:*\n"
    "🎬 Видео — mp4, mkv, webm, видеосообщения (кружочки)\n"
    "🖼 Изображения — фото, скриншоты, слайды (можно отправлять альбомом)\n"
    "📄 Документы — PDF, DOCX, TXT\n"
    "💬 Текст — сообщение длиннее 500 символов\n\n"
    "*Как использовать результат в NotebookLM:*\n"
    "1. Нажмите «📥 Пакет для NotebookLM»\n"
    "2. Загрузите полученный .txt файл в NotebookLM как источник\n"
    "3. Откройте Audio Overview и вставьте инструкцию "
    "из файла в поле «Customize»\n"
    "4. Сгенерируйте подкаст — он будет фокусироваться "
    "на ключевых темах вашего урока\n\n"
    "*Генерация промптов:*\n"
    "Отправьте текст с описанием → выберите тип промпта:\n"
    "Презентация — промпт для Gamma, Google Slides AI\n"
    "Видео — инструкция для NotebookLM Video Overview\n"
    "Инфографика — промпт для Canva AI, Napkin AI\n\n"
    "*Лимиты:*\n"
    "До 5 обработок в день на пользователя.\n\n"
    "*Команды:*\n"
    "/start — начало работы\n"
    "/help — эта справка"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Приветственное сообщение с описанием возможностей бота."""
    await message.answer(WELCOME_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Подробная справка о возможностях бота."""
    await message.answer(HELP_TEXT, parse_mode="Markdown")
