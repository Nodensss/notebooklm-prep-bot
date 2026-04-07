# Конфигурация бота — загрузка переменных окружения из .env

import os
from dotenv import load_dotenv

load_dotenv()

# Токен Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Токен GitHub для GitHub Models.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Модель GitHub Models для текстовых задач.
GITHUB_TEXT_MODEL = os.getenv("GITHUB_TEXT_MODEL", "openai/gpt-4o")

# Модель GitHub Models для изображений.
GITHUB_VISION_MODEL = os.getenv("GITHUB_VISION_MODEL", "openai/gpt-4o")
