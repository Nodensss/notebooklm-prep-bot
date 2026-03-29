# Упаковщик для NotebookLM

Telegram-бот, который принимает видео с лекциями и уроками, транскрибирует речь и подготавливает структурированные учебные материалы для загрузки в Google NotebookLM.

## Возможности

- Приём видео, видеосообщений (кружочков) и видеодокументов
- Извлечение аудио из видео (ffmpeg)
- Транскрипция речи через Groq Whisper API
- Структурирование текста через Google Gemini API
- Формирование пакета материалов для NotebookLM

## Установка и запуск

1. Клонируйте репозиторий:

```bash
git clone https://github.com/nodensss/notebooklm-prep-bot.git
cd notebooklm-prep-bot
```

2. Создайте виртуальное окружение и установите зависимости:

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Скопируйте `.env.example` в `.env` и заполните токены:

```bash
cp .env.example .env
```

- `BOT_TOKEN` — токен Telegram-бота от @BotFather
- `GROQ_API_KEY` — ключ API Groq (https://console.groq.com)
- `GEMINI_API_KEY` — ключ API Google Gemini (https://aistudio.google.com)

4. Убедитесь, что установлен ffmpeg:

```bash
sudo apt install ffmpeg   # Linux
brew install ffmpeg        # macOS
```

5. Запустите бота:

```bash
python bot.py
```

## Технологии

- Python 3.11
- aiogram 3.x
- Groq Whisper API (через OpenAI-совместимый клиент)
- Google Gemini API
