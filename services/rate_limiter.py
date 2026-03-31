# Универсальный rate limiter для Gemini API
#
# Gemini Free Tier: 5 запросов в минуту на модель.
# Ограничиваем до 4 req/min с запасом и автоматическим retry при 429.

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

# Максимум запросов в минуту (с запасом от лимита 5)
MAX_REQUESTS_PER_MINUTE = 4

# Максимум повторных попыток при ошибке 429
MAX_RETRIES = 3


class GeminiRateLimiter:
    """Ограничитель частоты запросов к Gemini API.

    Гарантирует не более MAX_REQUESTS_PER_MINUTE запросов в минуту.
    При ошибке 429 автоматически ждёт и повторяет запрос.
    """

    def __init__(self, max_per_minute: int = MAX_REQUESTS_PER_MINUTE) -> None:
        self._max_per_minute = max_per_minute
        self._semaphore = asyncio.Semaphore(1)  # один запрос за раз
        self._timestamps: list[float] = []

    async def _wait_for_slot(self) -> None:
        """Ждёт, пока не освободится слот в окне 60 секунд."""
        while True:
            now = time.monotonic()
            # Убираем метки старше 60 секунд
            self._timestamps = [t for t in self._timestamps if now - t < 60]

            if len(self._timestamps) < self._max_per_minute:
                self._timestamps.append(now)
                return

            # Ждём до истечения самой старой метки
            oldest = self._timestamps[0]
            wait_time = 60 - (now - oldest) + 0.5  # +0.5с запас
            logger.info("Rate limit: жду %.1f сек перед следующим запросом", wait_time)
            await asyncio.sleep(wait_time)

    async def execute(self, coro_factory):
        """Выполняет асинхронную функцию с учётом rate limit и retry.

        Args:
            coro_factory: функция без аргументов, возвращающая корутину.
                          Вызывается заново при каждом retry.

        Returns:
            Результат выполнения корутины.

        Raises:
            RuntimeError: если все попытки исчерпаны.
        """
        async with self._semaphore:
            last_error = None

            for attempt in range(1, MAX_RETRIES + 1):
                await self._wait_for_slot()

                try:
                    return await coro_factory()
                except Exception as e:
                    error_str = str(e)
                    last_error = e

                    # Проверяем, что это именно 429 (rate limit)
                    if "429" not in error_str:
                        raise

                    # Пытаемся извлечь retry_delay из ответа
                    wait = _extract_retry_delay(error_str)
                    if wait is None:
                        # Экспоненциальная задержка: 15, 30, 60 сек
                        wait = 15 * (2 ** (attempt - 1))

                    logger.warning(
                        "Gemini 429 (попытка %d/%d), жду %d сек...",
                        attempt, MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)

            raise RuntimeError(
                f"Gemini API недоступен после {MAX_RETRIES} попыток: {last_error}"
            )


def _extract_retry_delay(error_text: str) -> int | None:
    """Извлекает время ожидания из текста ошибки 429.

    Ищет паттерн 'retry_delay { seconds: N }' или 'retry in Ns'.
    """
    import re

    # Формат: retry_delay { seconds: 24 }
    match = re.search(r"seconds:\s*(\d+)", error_text)
    if match:
        return int(match.group(1)) + 2  # +2 сек запас

    # Формат: Please retry in 24.8s
    match = re.search(r"retry in (\d+)", error_text)
    if match:
        return int(match.group(1)) + 2

    return None


# Глобальный экземпляр — один на весь бот
gemini_limiter = GeminiRateLimiter()
