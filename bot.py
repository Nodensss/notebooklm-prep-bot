import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN, GEMINI_API_KEY, GROQ_API_KEY
from handlers import content, start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Инициализация и запуск Telegram-бота."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан. Проверьте файл .env")

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY не задан. Проверьте файл .env")

    if not GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY не задан. Обработка видео будет недоступна, но текстовые материалы продолжат работать."
        )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(content.router)

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
