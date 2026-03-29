# Упаковщик для NotebookLM

## Описание проекта

Telegram-бот, который принимает учебные материалы (видео, PDF, DOCX, TXT, текст),
транскрибирует/извлекает текст и создаёт структурированный учебный пакет
с готовым промптом для Google NotebookLM Audio Overview.

## Архитектура

```
bot.py                  — точка входа, инициализация aiogram 3.x Dispatcher
config.py               — загрузка переменных окружения из .env
handlers/
  start.py              — команды /start и /help
  video.py              — обработка видео, документов, текста; inline-кнопки; rate limiting
services/
  transcribe.py         — извлечение аудио (ffmpeg), транскрипция (Groq Whisper API)
  formatter.py          — структурирование через Google Gemini API
```

## Стек технологий

- **Python 3.11**
- **aiogram 3.x** — Telegram Bot API (async, роутеры)
- **Groq API** — транскрипция через Whisper (OpenAI-совместимый клиент `openai`)
- **Google Gemini API** — генерация учебного пакета (`google-generativeai`)
- **ffmpeg** — извлечение и нарезка аудио из видео
- **PyPDF2** — извлечение текста из PDF
- **python-docx** — извлечение текста из DOCX

## Ключевые переменные окружения

- `BOT_TOKEN` — токен Telegram-бота
- `GROQ_API_KEY` — ключ Groq API
- `GEMINI_API_KEY` — ключ Google Gemini API

## Запуск

```bash
cp .env.example .env   # заполнить токены
pip install -r requirements.txt
python bot.py
```

Или через Docker:

```bash
docker build -t notebooklm-bot .
docker run --env-file .env notebooklm-bot
```

## Соглашения

- Комментарии и пользовательские сообщения на русском языке
- Async/await повсюду
- Результаты хранятся в памяти (dict по user_id), без БД
- Лимит: 5 обработок в день на пользователя
- Временные файлы — в `tmp/`, удаляются после обработки
