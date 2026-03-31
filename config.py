# Конфигурация бота — загрузка переменных окружения из .env и Replit Secrets

import os
from dotenv import load_dotenv

# Поддерживаются и локальный .env, и Replit Secrets через переменные окружения.
load_dotenv()

# Токен Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Ключ API Groq (для транскрипции через Whisper)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Ключ API Google Gemini (для структурирования текста)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
