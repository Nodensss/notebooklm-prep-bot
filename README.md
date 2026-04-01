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
- Дневной лимит: 5 обработок на пользователя

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

3. Скопируйте `.env.example` в `.env` и заполните токены:

```bash
cp .env.example .env
```

- `BOT_TOKEN` — токен Telegram-бота от `@BotFather`
- `GROQ_API_KEY` — ключ API Groq
- `OPENROUTER_API_KEY` — ключ OpenRouter
- `OPENROUTER_TEXT_MODEL` — модель OpenRouter для текстовых задач
- `OPENROUTER_VISION_MODEL` — модель OpenRouter для изображений

4. Убедитесь, что установлен `ffmpeg`:

```bash
sudo apt install ffmpeg   # Linux
brew install ffmpeg       # macOS
```

5. Запустите бота:

```bash
python bot.py
```

## Деплой на VPS (Oracle Cloud Free Tier)

### 1. Создайте бесплатный инстанс

- Зарегистрируйте аккаунт в Oracle Cloud Free Tier
- Создайте Compute Instance с образом Ubuntu
- Для бесплатного ARM-варианта подойдёт `VM.Standard.A1.Flex` (Ampere)
- Сохраните публичный IP-адрес и SSH-ключ

### 2. Подключитесь по SSH

```bash
ssh ubuntu@<IP_ВАШЕГО_СЕРВЕРА>
```

### 3. Запустите автоматическую установку

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

### 4. Заполните `.env`

```bash
nano /home/ubuntu/notebooklm-prep-bot/.env
```

Пример содержимого:

```env
BOT_TOKEN=...
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
OPENROUTER_TEXT_MODEL=google/gemini-2.5-flash
OPENROUTER_VISION_MODEL=google/gemini-2.5-flash
```

### 5. Установите systemd-сервис

```bash
cd /home/ubuntu/notebooklm-prep-bot
sudo cp deploy/notebooklm-bot.service /etc/systemd/system/notebooklm-bot.service
sudo systemctl daemon-reload
sudo systemctl enable notebooklm-bot
sudo systemctl start notebooklm-bot
```

### 6. Управление сервисом

```bash
sudo systemctl start notebooklm-bot
sudo systemctl stop notebooklm-bot
sudo systemctl restart notebooklm-bot
sudo systemctl status notebooklm-bot
```

### 7. Просмотр логов

```bash
journalctl -u notebooklm-bot -f
```

### 8. Обновление после новых коммитов

```bash
cd /home/ubuntu/notebooklm-prep-bot
./deploy/update.sh
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
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_TEXT_MODEL`
- `OPENROUTER_VISION_MODEL`

5. Нажмите `Run`
6. Для постоянной работы откройте настройки Repl и включите `Always On`

В проекте уже есть:

- `.replit` — команда запуска и настройки deployment
- `replit.nix` — зависимости `python311` и `ffmpeg`

## Структура deploy

- `deploy/setup.sh` — первичная установка проекта на Ubuntu VPS
- `deploy/notebooklm-bot.service` — systemd unit для автозапуска
- `deploy/update.sh` — обновление проекта и перезапуск сервиса


## Новая структура проекта

```text
notebooklm-prep-bot/
├── bot.py                    # точка входа бота
├── config.py                 # переменные окружения и настройки моделей
├── handlers/                 # обработчики Telegram-сообщений и callback-кнопок
│   ├── start.py
│   └── content.py
├── services/                 # интеграции с API и бизнес-логика
│   ├── transcribe.py         # видео -> аудио -> транскрипция
│   ├── vision.py             # OCR/описание изображений через OpenRouter Vision
│   ├── formatter.py          # учебный пакет + prompt для NotebookLM
│   ├── prompt_generator.py   # отдельные prompt-режимы (презентация/видео/инфографика)
│   ├── openrouter_client.py  # общий OpenRouter клиент и ошибки
│   └── rate_limiter.py
└── deploy/                   # VPS/systemd скрипты деплоя
```

## Почему появляется ошибка «Недостаточно кредитов OpenRouter»

Эта ошибка приходит от OpenRouter (HTTP 402 / `insufficient credits`) и не связана с Telegram-лимитом бота.

Проверьте:

1. Баланс аккаунта OpenRouter и лимиты ключа.
2. Значения `OPENROUTER_TEXT_MODEL` и `OPENROUTER_VISION_MODEL` в `.env` — более дорогие модели быстрее расходуют баланс.
3. Что для OCR используется модель с поддержкой изображений (multimodal).

Бот теперь дополнительно показывает текущую модель в тексте ошибки, чтобы быстрее понять причину.

## Технологии

- Python 3.11
- aiogram 3.x
- Groq Whisper API
- OpenRouter API
- ffmpeg
