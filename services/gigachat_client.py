"""Общие helpers для работы с GigaChat API."""

import asyncio
import base64
import logging
import mimetypes
from pathlib import Path

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from config import GIGACHAT_CREDENTIALS, GIGACHAT_SCOPE

logger = logging.getLogger(__name__)

TEXT_MODEL = "GigaChat-2"
VISION_MODEL = "GigaChat-2-Pro"


def _build_client(model: str | None = None) -> GigaChat:
    """Создаёт клиент GigaChat с общей конфигурацией проекта."""
    if not GIGACHAT_CREDENTIALS:
        raise ValueError("GIGACHAT_CREDENTIALS не задан. Проверьте файл .env")

    return GigaChat(
        credentials=GIGACHAT_CREDENTIALS,
        scope=GIGACHAT_SCOPE,
        model=model,
        verify_ssl_certs=False,
    )


def _extract_text(response) -> str:
    """Достаёт текст из ответа GigaChat."""
    if not response.choices:
        return ""

    return (response.choices[0].message.content or "").strip()


def _chat_sync(prompt: str, *, model: str) -> str:
    """Синхронный текстовый запрос к GigaChat."""
    with _build_client(model=model) as giga:
        response = giga.chat(prompt)
        return _extract_text(response)


async def chat_text(prompt: str, *, model: str = TEXT_MODEL) -> str:
    """Асинхронная обёртка над текстовым запросом к GigaChat."""
    return await asyncio.to_thread(_chat_sync, prompt, model=model)


def _encode_image_to_base64(image_path: str) -> tuple[str, bytes, str]:
    """Читает изображение и возвращает имя, бинарные данные и MIME-тип.

    Base64 создаётся явно, чтобы формат соответствовал требованиям интеграции.
    """
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    raw_bytes = path.read_bytes()
    encoded = base64.b64encode(raw_bytes).decode("ascii")
    decoded = base64.b64decode(encoded)
    return path.name, decoded, mime_type


def _chat_with_image_sync(prompt: str, image_path: str, *, model: str) -> str:
    """Синхронный запрос к GigaChat с прикреплённым изображением."""
    file_name, image_bytes, mime_type = _encode_image_to_base64(image_path)

    with _build_client(model=model) as giga:
        uploaded_file = giga.upload_file(
            (file_name, image_bytes, mime_type),
            purpose="general",
        )

        try:
            chat = Chat(
                messages=[
                    Messages(
                        role=MessagesRole.USER,
                        content=prompt,
                        attachments=[uploaded_file.id_],
                    )
                ]
            )
            response = giga.chat(chat)
            return _extract_text(response)
        finally:
            try:
                giga.delete_file(uploaded_file.id_)
            except Exception as error:
                logger.warning(
                    "Не удалось удалить временный файл GigaChat %s: %s",
                    uploaded_file.id_,
                    error,
                )


async def chat_with_image(
    prompt: str,
    image_path: str,
    *,
    model: str = VISION_MODEL,
) -> str:
    """Асинхронная обёртка над запросом к GigaChat с изображением."""
    return await asyncio.to_thread(
        _chat_with_image_sync,
        prompt,
        image_path,
        model=model,
    )
