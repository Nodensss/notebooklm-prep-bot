"""Универсальный rate limiter для внешних LLM API."""

import asyncio
import logging
import re

from gigachat.exceptions import RateLimitError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class ApiRateLimiter:
    """Ограничивает одновременные запросы и повторяет их при 429."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(1)

    async def execute(self, coro_factory):
        """Выполняет асинхронную функцию с очередью и retry при 429."""
        async with self._semaphore:
            last_error = None

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    return await coro_factory()
                except RateLimitError as error:
                    last_error = error
                    wait_time = max(int(error.retry_after), 1)
                except Exception as error:
                    error_text = str(error)
                    if "429" not in error_text:
                        raise

                    last_error = error
                    wait_time = _extract_retry_delay(error_text) or (5 * attempt)

                logger.warning(
                    "LLM API вернул 429 (попытка %d/%d), жду %d сек...",
                    attempt,
                    MAX_RETRIES,
                    wait_time,
                )
                await asyncio.sleep(wait_time)

            raise RuntimeError(
                f"LLM API недоступен после {MAX_RETRIES} попыток: {last_error}"
            )


def _extract_retry_delay(error_text: str) -> int | None:
    """Извлекает время ожидания из текста ошибки 429."""
    match = re.search(r"retry[-_ ]after[=: ]+(\d+)", error_text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1)) + 1

    match = re.search(r"retry in (\d+)", error_text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1)) + 1

    return None


llm_limiter = ApiRateLimiter()
