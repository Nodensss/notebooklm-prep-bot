import asyncio
import logging
import re

logger = logging.getLogger(__name__)

# Максимум повторных попыток при ошибке 429
MAX_RETRIES = 3


class ApiRateLimiter:
    """Универсальный ограничитель для внешнего LLM API."""

    def __init__(self, max_concurrent: int = 1) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

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
                try:
                    return await coro_factory()
                except Exception as error:
                    error_text = str(error)
                    last_error = error

                    if not _is_retryable_rate_limit(error_text):
                        raise

                    wait = _extract_retry_delay(error_text)
                    if wait is None:
                        wait = 5 * attempt

                    logger.warning(
                        "LLM API вернул 429 (попытка %d/%d), жду %d сек...",
                        attempt,
                        MAX_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)

            raise RuntimeError(
                f"LLM API недоступен после {MAX_RETRIES} попыток: {last_error}"
            )


def _is_retryable_rate_limit(error_text: str) -> bool:
    """Определяет, что ошибку можно повторить после ожидания."""
    normalized_text = error_text.lower()
    return (
        "429" in normalized_text
        or "rate limit" in normalized_text
        or "too many requests" in normalized_text
    )


def _extract_retry_delay(error_text: str) -> int | None:
    """Извлекает время ожидания из текста ошибки 429."""

    match = re.search(r"seconds:\s*(\d+)", error_text)
    if match:
        return int(match.group(1)) + 2

    match = re.search(r"retry in (\d+)", error_text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1)) + 2

    match = re.search(r"retry after[:\s]+(\d+)", error_text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1)) + 2

    return None


# Глобальный экземпляр — один на весь бот
llm_limiter = ApiRateLimiter()
