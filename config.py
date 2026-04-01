# Конфигурация бота — загрузка переменных окружения из .env и переменных окружения

import os
from dotenv import load_dotenv

# Поддерживаются локальный .env и любые секреты, переданные через переменные окружения.
load_dotenv()

# Токен Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Ключ API Groq (для транскрипции через Whisper)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Authorization key для GigaChat API
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")

# Scope для личного использования GigaChat API
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
