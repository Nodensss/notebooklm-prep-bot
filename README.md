# Упаковщик для NotebookLM

Telegram-бот, который принимает учебные материалы, подготавливает структурированные конспекты для NotebookLM и умеет генерировать специализированные промпты для презентаций, видео и инфографики.

## Возможности

- Приём видео, видеосообщений и видеодокументов
- Приём изображений: фото, скриншоты, слайды и альбомы
- Приём текстовых документов: PDF, DOCX, TXT
- Обработка длинных текстовых сообщений как учебного материала
- Генерация учебного пакета для NotebookLM:
  - суть за 30 секунд
  - ключевые тезисы
  - план материала
  - вопросы для самопроверки
  - карточки для запоминания
  - практическое задание
  - промпт для NotebookLM Audio Overview
- Генерация промптов для:
  - презентаций
  - NotebookLM Video Overview
  - инфографики
- Кнопки для OCR:
  - `🧾 Исходный текст / OCR`
  - `📋 Скопировать OCR`
  - `📄 Исходник .txt`
- Дневной лимит: 5 обработок на пользователя

## Провайдеры

- Текстовые задачи и OCR идут через `GitHub Models`
- Видео транскрибируется через `Groq Whisper`
- Если `Groq` недоступен с вашего VPS, текст и изображения будут работать, а видео — нет

## Локальный запуск

1. Клонируйте репозиторий:

```bash
git clone https://github.com/Nodensss/notebooklm-prep-bot.git
cd notebooklm-prep-bot
```

2. Создайте виртуальное окружение и установите зависимости:

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

4. Заполните переменные окружения:

- `BOT_TOKEN` — токен Telegram-бота от `@BotFather`
- `GITHUB_TOKEN` — токен GitHub Models для текста и OCR
- `GITHUB_TEXT_MODEL` — модель GitHub Models для текстовых задач
- `GITHUB_VISION_MODEL` — модель GitHub Models для OCR и описания изображений
- `GROQ_API_KEY` — необязательный ключ Groq для транскрибации видео

Пример:

```env
BOT_TOKEN=...
GITHUB_TOKEN=...
GITHUB_TEXT_MODEL=openai/gpt-4o
GITHUB_VISION_MODEL=openai/gpt-4o
GROQ_API_KEY=...
```

5. Убедитесь, что установлен `ffmpeg`:

```bash
sudo apt install ffmpeg   # Linux
brew install ffmpeg       # macOS
```

6. Запустите бота:

```bash
python bot.py
```

## Деплой на VPS

### Первый запуск

```bash
git clone https://github.com/Nodensss/notebooklm-prep-bot.git
cd notebooklm-prep-bot
chmod +x deploy/setup.sh deploy/update.sh
./deploy/setup.sh
```

Скрипт:

- установит `python3.11`, `venv`, `pip`, `ffmpeg`, `git`
- создаст виртуальное окружение
- установит зависимости
- создаст `.env`, если его ещё нет

### Настройка `.env`

```bash
nano /home/ubuntu/notebooklm-prep-bot/.env
```

Пример:

```env
BOT_TOKEN=...
GITHUB_TOKEN=...
GITHUB_TEXT_MODEL=openai/gpt-4o
GITHUB_VISION_MODEL=openai/gpt-4o
GROQ_API_KEY=...
```

### Установка сервиса

```bash
cd /home/ubuntu/notebooklm-prep-bot
sudo cp deploy/notebooklm-bot.service /etc/systemd/system/notebooklm-bot.service
sudo systemctl daemon-reload
sudo systemctl enable notebooklm-bot
sudo systemctl start notebooklm-bot
```

### Управление сервисом

```bash
sudo systemctl start notebooklm-bot
sudo systemctl stop notebooklm-bot
sudo systemctl restart notebooklm-bot
sudo systemctl status notebooklm-bot
```

### Логи

```bash
journalctl -u notebooklm-bot -f
```

### Обновление после коммитов

```bash
cd /home/ubuntu/notebooklm-prep-bot
./deploy/update.sh
```

Если нужно обновиться на конкретную ветку:

```bash
./deploy/update.sh имя-ветки
```

## Деплой на Replit

1. Зайдите на `replit.com`
2. Нажмите `Create Repl` → `Import from GitHub`
3. Вставьте URL репозитория:

```text
https://github.com/Nodensss/notebooklm-prep-bot
```

4. После импорта откройте `Tools` → `Secrets` и добавьте:

- `BOT_TOKEN`
- `GITHUB_TOKEN`
- `GITHUB_TEXT_MODEL`
- `GITHUB_VISION_MODEL`
- `GROQ_API_KEY` — только если нужна обработка видео

5. Нажмите `Run`
6. Для постоянной работы включите `Always On`

В проекте уже есть:

- `.replit` — команда запуска и настройки deployment
- `replit.nix` — зависимости `python311` и `ffmpeg`

## Структура проекта

```text
notebooklm-prep-bot/
├── bot.py                  # точка входа бота
├── config.py               # переменные окружения и настройки моделей
├── handlers/               # обработчики Telegram-сообщений и callback-кнопок
│   ├── start.py
│   └── content.py
├── services/               # интеграции с API и бизнес-логика
│   ├── transcribe.py       # видео -> аудио -> транскрипция
│   ├── vision.py           # OCR/описание изображений через GitHub Models
│   ├── formatter.py        # учебный пакет + prompt для NotebookLM
│   ├── prompt_generator.py # отдельные prompt-режимы
│   ├── llm_client.py       # общий клиент GitHub Models и ошибки
│   └── rate_limiter.py
└── deploy/                 # VPS/systemd скрипты деплоя
```

## Что важно знать про провайдеры

1. Для текста и OCR нужен `GITHUB_TOKEN`
2. Для OCR используйте multimodal-модель в `GITHUB_VISION_MODEL`, например `openai/gpt-4o`
3. Видео по-прежнему зависит от `Groq Whisper`
4. Если `Groq` отвечает `403` с вашего сервера, бот честно сообщит, что видео временно недоступно

## Технологии

- Python 3.11
- aiogram 3.x
- GitHub Models API
- Groq Whisper API
- ffmpeg
