# NotebookLM Prep Bot

## О проекте

Telegram-бот для подготовки учебных материалов и промптов на основе изображений, документов и текста.

## Деплой

### Oracle Cloud Free Tier

- Первичная установка: `deploy/setup.sh`
- Обновление: `deploy/update.sh`
- Автозапуск: `deploy/notebooklm-bot.service`

### Replit

- Импортируйте репозиторий через `Create Repl` → `Import from GitHub`
- Добавьте секреты `BOT_TOKEN`, `GROQ_API_KEY`, `GITHUB_TOKEN`
- Запускайте проект через кнопку `Run`
- Для постоянной работы включите `Always On`

## Соглашения

- Комментарии и пользовательские тексты — на русском языке
- Основная асинхронная логика построена на `async/await`
