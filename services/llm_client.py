# Общий клиент GitHub Models для текста и OCR.

import base64
from pathlib import Path

from openai import AsyncOpenAI

from config import GITHUB_TEXT_MODEL, GITHUB_TOKEN, GITHUB_VISION_MODEL

# Лимиты токенов для ответов
TEXT_MAX_TOKENS = 4000
PROMPT_MAX_TOKENS = 2000
VISION_MAX_TOKENS = 3000

_github_client: AsyncOpenAI | None = None


def _get_github_client() -> AsyncOpenAI:
    """Возвращает клиент для GitHub Models API."""
    global _github_client
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN не задан. Проверьте файл .env")
    if _github_client is None:
        _github_client = AsyncOpenAI(
            api_key=GITHUB_TOKEN,
            base_url="https://models.github.ai/inference",
        )
    return _github_client


def _guess_mime_type(image_path: str) -> str:
    """Подбирает MIME-тип по расширению файла."""
    suffix = Path(image_path).suffix.lower()
    return {
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")


def build_llm_error(
    error: Exception,
    context: str,
    *,
    model: str | None = None,
) -> RuntimeError:
    """Преобразует ошибку GitHub Models в понятное сообщение."""
    error_text = str(error)
    lower = error_text.lower()

    if "401" in error_text or "403" in error_text or "unauthorized" in lower:
        return RuntimeError(
            "Не удалось обратиться к GitHub Models. Проверьте GITHUB_TOKEN и доступ к выбранной модели в вашем GitHub-аккаунте."
        )

    if "429" in error_text or "rate limit" in lower:
        hint = f" Модель: {model}." if model else ""
        return RuntimeError(f"Превышен лимит запросов.{hint} Попробуйте позже.")

    if "402" in error_text or "payment" in lower:
        return RuntimeError(
            "GitHub Models отклонил запрос из-за ограничений аккаунта или тарифа. Проверьте доступ к выбранной модели."
        )

    return RuntimeError(f"{context}: {error_text}")


async def generate_text(
    prompt: str,
    *,
    system_prompt: str | None = None,
    max_tokens: int = TEXT_MAX_TOKENS,
    temperature: float = 0.1,
) -> str:
    """Генерирует текст через GitHub Models."""
    client = _get_github_client()

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = await client.chat.completions.create(
        model=GITHUB_TEXT_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = response.choices[0].message.content
    return (content or "").strip()


async def analyze_image(
    prompt: str,
    image_path: str,
    *,
    system_prompt: str | None = None,
    max_tokens: int = VISION_MAX_TOKENS,
    temperature: float = 0.1,
) -> str:
    """Анализирует изображение через GitHub Models."""
    client = _get_github_client()

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

    response = await client.chat.completions.create(
        model=GITHUB_VISION_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = response.choices[0].message.content
    return (content or "").strip()
