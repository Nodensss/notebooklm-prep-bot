FROM python:3.11-slim

# Установка ffmpeg для извлечения аудио из видео
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание директории для временных файлов
RUN mkdir -p tmp

CMD ["python", "bot.py"]
