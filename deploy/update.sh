#!/bin/bash
# Обновление бота на Ubuntu VPS

set -euo pipefail

PROJECT_DIR="/home/$USER/notebooklm-prep-bot"

echo "=== Обновление репозитория ==="
cd "$PROJECT_DIR"
git pull --ff-only origin main

echo "=== Обновление зависимостей ==="
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "=== Перезапуск сервиса ==="
sudo systemctl restart notebooklm-bot
sudo systemctl status notebooklm-bot --no-pager

echo "Бот обновлён и перезапущен"
