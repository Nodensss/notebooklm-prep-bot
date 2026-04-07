# Конфигурация бота — загрузка переменных окружения из .env

import os
from dotenv import load_dotenv

load_dotenv()

# Токен Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Ключ API Groq (транскрипция Whisper + текстовые LLM-задачи)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Модель Groq для текстовых задач (учебные пакеты, промпты)
GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")

# Токен GitHub для GitHub Models (Vision / OCR)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Модель GitHub Models для изображений
GITHUB_VISION_MODEL = os.getenv("GITHUB_VISION_MODEL", "openai/gpt-4o")
