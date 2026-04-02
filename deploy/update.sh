#!/bin/bash
# Обновление бота на Ubuntu VPS.
# По умолчанию обновляет текущую ветку, но можно передать ветку первым аргументом.

set -euo pipefail

PROJECT_DIR="/home/$USER/notebooklm-prep-bot"
TARGET_BRANCH="${1:-$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || true)}"

if [ -z "$TARGET_BRANCH" ]; then
  TARGET_BRANCH="main"
fi

echo "=== Обновление репозитория ==="
cd "$PROJECT_DIR"
git fetch origin

if git show-ref --verify --quiet "refs/heads/$TARGET_BRANCH"; then
  git checkout "$TARGET_BRANCH"
else
  git checkout -B "$TARGET_BRANCH" "origin/$TARGET_BRANCH"
fi

git pull --ff-only origin "$TARGET_BRANCH"

echo "=== Обновление зависимостей ==="
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "=== Перезапуск сервиса ==="
sudo systemctl restart notebooklm-bot
sudo systemctl status notebooklm-bot --no-pager

echo "Бот обновлён и перезапущен"
