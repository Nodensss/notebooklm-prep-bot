# Конфигурация бота — загрузка переменных окружения из .env и окружения

import os
from dotenv import load_dotenv

# Поддерживаются локальный .env и любые секреты, переданные через переменные окружения.
load_dotenv()

# Токен Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Ключ API Groq (для транскрипции через Whisper)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Ключ API OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Модель OpenRouter для текстовых задач
OPENROUTER_TEXT_MODEL = os.getenv(
    "OPENROUTER_TEXT_MODEL",
    "google/gemini-2.5-flash",
)

# Модель OpenRouter для изображений
OPENROUTER_VISION_MODEL = os.getenv(
    "OPENROUTER_VISION_MODEL",
    OPENROUTER_TEXT_MODEL,
)
