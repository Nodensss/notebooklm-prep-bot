# NotebookLM Prep Bot

## О проекте

Telegram-бот для подготовки учебных материалов и промптов на основе видео, изображений, документов и текста.

## Деплой

### Oracle Cloud Free Tier / Ubuntu VPS

- Первичная установка: `deploy/setup.sh`
- Обновление: `deploy/update.sh`
- Автозапуск: `deploy/notebooklm-bot.service`

### Replit

- Импортируйте репозиторий через `Create Repl` → `Import from GitHub`
- Добавьте секреты `BOT_TOKEN`, `GITHUB_TOKEN`, `GITHUB_TEXT_MODEL`, `GITHUB_VISION_MODEL`
- Если нужен транскрайб видео, отдельно добавьте `GROQ_API_KEY`
- Запускайте проект через кнопку `Run`
- Для постоянной работы включите `Always On`

## Соглашения

- Комментарии и пользовательские тексты — на русском языке
- Основная асинхронная логика построена на `async/await`
- Текстовые задачи и OCR идут через `GitHub Models`
- Транскрибация видео использует `Groq Whisper`, если он доступен с сервера
