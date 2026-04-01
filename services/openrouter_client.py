"""Общие helpers для работы с OpenRouter."""

import base64
from pathlib import Path

from openai import AsyncOpenAI

from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_TEXT_MODEL,
    OPENROUTER_VISION_MODEL,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/Nodensss/notebooklm-prep-bot",
    "X-OpenRouter-Title": "NotebookLM Prep Bot",
}

TEXT_MAX_TOKENS = 4000
PROMPT_MAX_TOKENS = 2000
VISION_MAX_TOKENS = 3000

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Возвращает ленивый экземпляр OpenAI-клиента для OpenRouter."""
    global _client

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY не задан. Проверьте файл .env")

    if _client is None:
        _client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )

    return _client


def _extract_content(message_content) -> str:
    """Преобразует ответ модели к строке."""
    if isinstance(message_content, str):
        return message_content.strip()

    if isinstance(message_content, list):
        parts: list[str] = []
        for item in message_content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts).strip()

    return ""


def _guess_mime_type(image_path: str) -> str:
    """Подбирает MIME-тип по расширению файла."""
    suffix = Path(image_path).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/jpeg"


def build_openrouter_error(error: Exception, context: str) -> RuntimeError:
    """Преобразует сырую ошибку OpenRouter в понятное сообщение."""
    error_text = str(error)
    normalized_text = error_text.lower()

    if (
        "401" in error_text
        or "403" in error_text
        or "invalid api key" in normalized_text
        or "unauthorized" in normalized_text
    ):
        return RuntimeError("Неверный OPENROUTER_API_KEY. Проверьте ключ в .env")

    if "402" in error_text or "insufficient credits" in normalized_text:
        return RuntimeError(
            "Недостаточно кредитов OpenRouter. Пополните баланс или выберите более дешёвую модель."
        )

    return RuntimeError(f"{context}: {error_text}")


async def chat_completion(
    messages: list[dict],
    *,
    model: str,
    max_tokens: int,
    temperature: float = 0.1,
) -> str:
    """Отправляет chat completion запрос через OpenRouter."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        extra_headers=OPENROUTER_HEADERS,
    )
    return _extract_content(response.choices[0].message.content)


async def generate_text(
    prompt: str,
    *,
    system_prompt: str | None = None,
    model: str = OPENROUTER_TEXT_MODEL,
    max_tokens: int = TEXT_MAX_TOKENS,
    temperature: float = 0.1,
) -> str:
    """Генерирует текст через OpenRouter."""
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return await chat_completion(
        messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def analyze_image(
    prompt: str,
    image_path: str,
    *,
    system_prompt: str | None = None,
    model: str = OPENROUTER_VISION_MODEL,
    max_tokens: int = VISION_MAX_TOKENS,
    temperature: float = 0.1,
) -> str:
    """Анализирует изображение через OpenRouter multimodal API."""
    image_bytes = Path(image_path).read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    mime_type = _guess_mime_type(image_path)

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}",
                    },
                },
            ],
        }
    )

    return await chat_completion(
        messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
