# Упаковщик для NotebookLM

Telegram-бот, который принимает учебные материалы (изображения, документы, текст), подготавливает структурированные конспекты для NotebookLM и умеет генерировать специализированные промпты для презентаций и инфографики.

## Возможности

- Приём изображений: фото, скриншоты, слайды и альбомы (OCR через GitHub Models)
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
- `GROQ_API_KEY` — ключ API Groq (текстовые задачи, Llama 3.3 70B)
- `GITHUB_TOKEN` — токен GitHub (Vision/OCR через GitHub Models, GPT-4o)

4. Запустите бота:

```bash
python bot.py
```

## Деплой на VPS

### 1. Подключитесь по SSH и клонируйте проект

```bash
ssh user@<IP_ВАШЕГО_СЕРВЕРА>
git clone https://github.com/Nodensss/notebooklm-prep-bot.git
cd notebooklm-prep-bot
chmod +x deploy/setup.sh deploy/update.sh
./deploy/setup.sh
```

### 2. Заполните `.env`

```bash
nano .env
```

Пример содержимого:

```env
BOT_TOKEN=...
GROQ_API_KEY=...
GITHUB_TOKEN=...
```

### 3. Установите systemd-сервис

```bash
sudo cp deploy/notebooklm-bot.service /etc/systemd/system/notebooklm-bot.service
sudo systemctl daemon-reload
sudo systemctl enable notebooklm-bot
sudo systemctl start notebooklm-bot
```

### 4. Управление и логи

```bash
sudo systemctl status notebooklm-bot
journalctl -u notebooklm-bot -f
```

### 5. Обновление после новых коммитов

```bash
./deploy/update.sh
```

## Структура проекта

```text
notebooklm-prep-bot/
├── bot.py                    # точка входа бота
├── config.py                 # переменные окружения и настройки моделей
├── handlers/                 # обработчики Telegram-сообщений и callback-кнопок
│   ├── start.py
│   └── content.py
├── services/                 # интеграции с API и бизнес-логика
│   ├── vision.py             # OCR/описание изображений через GitHub Models
│   ├── formatter.py          # учебный пакет + prompt для NotebookLM
│   ├── prompt_generator.py   # промпт-режимы (презентация/инфографика)
│   ├── openrouter_client.py  # Groq + GitHub Models клиенты
│   └── rate_limiter.py
└── deploy/                   # VPS/systemd скрипты деплоя
```

## Технологии

- Python 3.11
- aiogram 3.x
- Groq API (Llama 3.3 70B — текстовые задачи)
- GitHub Models API (GPT-4o — Vision/OCR)
