#!/bin/bash
# Автоматическая установка бота на Ubuntu VPS

set -euo pipefail

PROJECT_DIR="/home/$USER/notebooklm-prep-bot"
REPO_URL="https://github.com/Nodensss/notebooklm-prep-bot.git"

echo "=== Установка зависимостей ==="
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git

echo "=== Клонирование репозитория ==="
cd "/home/$USER"
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "Репозиторий уже существует, пропускаю клонирование"
else
    git clone "$REPO_URL"
fi

cd "$PROJECT_DIR"

echo "=== Создание виртуального окружения ==="
python3.11 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "=== Настройка переменных окружения ==="
if [ ! -f .env ]; then
    cp .env.example .env
fi

echo "Установка завершена."
echo "Следующие шаги:"
echo "1. Отредактируйте файл окружения: nano $PROJECT_DIR/.env"
echo "2. Скопируйте systemd unit:"
echo "   sudo cp deploy/notebooklm-bot.service /etc/systemd/system/notebooklm-bot.service"
echo "3. Активируйте сервис:"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable notebooklm-bot"
echo "   sudo systemctl start notebooklm-bot"
