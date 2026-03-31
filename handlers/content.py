# Обработчик входящих видео, документов, изображений и текстовых сообщений

import asyncio
import html
import logging
import os
import uuid
from datetime import date
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from services.formatter import format_for_learning, generate_notebooklm_prompt
from services.prompt_generator import (
    generate_infographic_prompt,
    generate_presentation_prompt,
    generate_video_prompt,
)
from services.transcribe import process_video
from services.vision import describe_image, describe_images

logger = logging.getLogger(__name__)
router = Router()

# Допустимые MIME-типы для документов с видео
VIDEO_MIME_TYPES = {"video/mp4", "video/x-matroska", "video/webm"}

# Допустимые MIME-типы для текстовых документов
TEXT_MIME_TYPES = {
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Допустимые MIME-типы для изображений
IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

# Допустимые расширения файлов (запасной вариант, если MIME не определён)
TEXT_EXTENSIONS = {".txt", ".pdf", ".docx"}

# Директория для временных файлов
TMP_DIR = Path("tmp")

# Максимальная длина одного сообщения Telegram
MAX_MESSAGE_LENGTH = 4096

# Минимальная длина текстового сообщения для обработки как учебного материала
MIN_TEXT_LENGTH = 500

# Лимит обработок в день на пользователя
DAILY_LIMIT = 5

# Хранилище результатов по user_id
_user_results: dict[int, dict] = {}

# Хранилище счётчика обработок: {user_id: (дата, количество)}
_user_usage: dict[int, tuple[date, int]] = {}

# Временное хранилище альбомов изображений по media_group_id
_pending_media_groups: dict[str, list[Message]] = {}
_pending_media_group_tasks: dict[str, asyncio.Task[None]] = {}

# Маппинг callback-данных на ключи результатов и заголовки
_SECTION_INFO = {
    "key_points": ("key_points", "📋 Ключевые тезисы"),
    "plan": ("plan", "📝 План видео"),
    "quiz": ("quiz", "❓ Вопросы для самопроверки"),
    "cards": ("cards", "🃏 Карточки для запоминания"),
    "practice": ("practice", "💪 Практическое задание"),
    "notebooklm_prompt": ("notebooklm_prompt", "🎙 Промпт для NotebookLM"),
}

_PROMPT_ACTIONS = {
    "text_action_learning": "📚 Учебный пакет",
    "text_action_presentation": "🖼 Промпт для презентации",
    "text_action_video": "🎬 Промпт для видео",
    "text_action_infographic": "📊 Промпт для инфографики",
}

PROMPT_COPY_CALLBACK = "copy_generated_prompt"
CODE_BLOCK_CHUNK_SIZE = 2500


def _check_rate_limit(user_id: int) -> bool:
    """Проверяет, не превышен ли дневной лимит обработок.

    Returns:
        True если лимит НЕ превышен и можно продолжать.
    """
    today = date.today()
    usage_date, count = _user_usage.get(user_id, (today, 0))

    # Новый день — сбрасываем счётчик
    if usage_date != today:
        return True

    return count < DAILY_LIMIT


def _increment_usage(user_id: int) -> None:
    """Увеличивает счётчик обработок пользователя на 1."""
    today = date.today()
    usage_date, count = _user_usage.get(user_id, (today, 0))

    if usage_date != today:
        _user_usage[user_id] = (today, 1)
    else:
        _user_usage[user_id] = (today, count + 1)


def _get_remaining_limit(user_id: int) -> int:
    """Возвращает, сколько обработок осталось у пользователя на сегодня."""
    today = date.today()
    usage_date, count = _user_usage.get(user_id, (today, 0))

    if usage_date != today:
        return DAILY_LIMIT

    return max(DAILY_LIMIT - count, 0)


def _build_keyboard() -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру с разделами учебного пакета."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Тезисы", callback_data="key_points"),
            InlineKeyboardButton(text="📝 План", callback_data="plan"),
        ],
        [
            InlineKeyboardButton(text="❓ Самопроверка", callback_data="quiz"),
            InlineKeyboardButton(text="🃏 Карточки", callback_data="cards"),
        ],
        [
            InlineKeyboardButton(text="💪 Практика", callback_data="practice"),
            InlineKeyboardButton(
                text="🎙 Промпт NotebookLM", callback_data="notebooklm_prompt"
            ),
        ],
        [
            InlineKeyboardButton(text="📄 Скачать всё", callback_data="download_all"),
            InlineKeyboardButton(
                text="📥 Пакет для NotebookLM", callback_data="download_notebooklm"
            ),
        ],
    ])


def _build_text_action_keyboard(include_learning_pack: bool) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру выбора действия для присланного текста."""
    rows: list[list[InlineKeyboardButton]] = []

    if include_learning_pack:
        rows.append([
            InlineKeyboardButton(
                text=_PROMPT_ACTIONS["text_action_learning"],
                callback_data="text_action_learning",
            )
        ])

    rows.extend([
        [
            InlineKeyboardButton(
                text=_PROMPT_ACTIONS["text_action_presentation"],
                callback_data="text_action_presentation",
            )
        ],
        [
            InlineKeyboardButton(
                text=_PROMPT_ACTIONS["text_action_video"],
                callback_data="text_action_video",
            )
        ],
        [
            InlineKeyboardButton(
                text=_PROMPT_ACTIONS["text_action_infographic"],
                callback_data="text_action_infographic",
            )
        ],
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_copy_prompt_keyboard() -> InlineKeyboardMarkup:
    """Создаёт кнопку для повторной отправки промпта в виде code block."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 Скопировать",
                callback_data=PROMPT_COPY_CALLBACK,
            )
        ]
    ])


async def _download_file(bot: Bot, file_id: str, default_ext: str = ".mp4") -> str:
    """Скачивает файл из Telegram и сохраняет во временную директорию.

    Args:
        bot: экземпляр бота.
        file_id: идентификатор файла в Telegram.
        default_ext: расширение по умолчанию, если не определено.

    Returns:
        Путь к скачанному файлу.
    """
    TMP_DIR.mkdir(exist_ok=True)
    tg_file = await bot.get_file(file_id)
    ext = Path(tg_file.file_path).suffix if tg_file.file_path else default_ext
    local_path = str(TMP_DIR / f"{uuid.uuid4().hex}{ext}")
    await bot.download_file(tg_file.file_path, local_path)
    logger.info("Файл скачан: %s (%.1f МБ)", local_path,
                Path(local_path).stat().st_size / 1024 / 1024)
    return local_path


def _extract_text_from_txt(file_path: str) -> str:
    """Читает текст из .txt файла (UTF-8)."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_text_from_pdf(file_path: str) -> str:
    """Извлекает текст из PDF через PyPDF2."""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()


def _extract_text_from_docx(file_path: str) -> str:
    """Извлекает текст из DOCX через python-docx."""
    from docx import Document

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs).strip()


def _extract_text_from_file(file_path: str) -> str:
    """Определяет формат файла и извлекает текст.

    Args:
        file_path: путь к скачанному файлу.

    Returns:
        Извлечённый текст.

    Raises:
        RuntimeError: неподдерживаемый формат или ошибка чтения.
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".txt":
        return _extract_text_from_txt(file_path)
    elif ext == ".pdf":
        return _extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return _extract_text_from_docx(file_path)
    else:
        raise RuntimeError(f"Неподдерживаемый формат файла: {ext}")


def _safe_remove(file_path: str) -> None:
    """Безопасно удаляет временный файл."""
    try:
        os.remove(file_path)
    except OSError:
        pass


async def _send_long_text(message: Message, text: str) -> None:
    """Отправляет длинный текст, разбивая на части по 4096 символов.

    Разбивка идёт по границам строк, чтобы не резать слова.

    Args:
        message: сообщение для ответа.
        text: текст для отправки.
    """
    while text:
        if len(text) <= MAX_MESSAGE_LENGTH:
            await message.answer(text)
            break

        # Ищем последний перенос строки в пределах лимита
        split_pos = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        if split_pos == -1:
            split_pos = text.rfind(" ", 0, MAX_MESSAGE_LENGTH)
        if split_pos == -1:
            split_pos = MAX_MESSAGE_LENGTH

        await message.answer(text[:split_pos])
        text = text[split_pos:].lstrip()


async def _send_code_block(message: Message, text: str) -> None:
    """Отправляет текст в виде code block, при необходимости разбивая на части."""
    remaining_text = text

    while remaining_text:
        if len(remaining_text) <= CODE_BLOCK_CHUNK_SIZE:
            chunk = remaining_text
            remaining_text = ""
        else:
            split_pos = remaining_text.rfind("\n", 0, CODE_BLOCK_CHUNK_SIZE)
            if split_pos == -1:
                split_pos = remaining_text.rfind(" ", 0, CODE_BLOCK_CHUNK_SIZE)
            if split_pos == -1:
                split_pos = CODE_BLOCK_CHUNK_SIZE

            chunk = remaining_text[:split_pos]
            remaining_text = remaining_text[split_pos:].lstrip()

        escaped_chunk = html.escape(chunk)
        await message.answer(f"<pre>{escaped_chunk}</pre>", parse_mode="HTML")


async def _format_and_reply(
    message: Message,
    transcript: str,
    status_msg: Message,
    user_id: int | None = None,
) -> None:
    """Общая логика форматирования: Gemini → inline-кнопки.

    Вынесено отдельно, чтобы использовать и для видео, и для текста/документов.

    Args:
        message: входящее сообщение пользователя.
        transcript: исходный текст (транскрипция или текст документа).
        status_msg: сообщение-статус для обновления прогресса.
    """
    # Структурирование через Gemini
    await status_msg.edit_text("⏳ Структурирую материал...")
    learning_pack = await format_for_learning(transcript)

    await status_msg.edit_text("⏳ Генерирую промпт для NotebookLM...")
    notebooklm_prompt = await generate_notebooklm_prompt(
        transcript, learning_pack
    )

    # Сохраняем результаты для inline-кнопок
    target_user_id = user_id or message.from_user.id
    _user_results[target_user_id] = {
        "transcript": transcript,
        "learning_pack": learning_pack,
        "notebooklm_prompt": notebooklm_prompt,
    }

    # Засчитываем обработку
    _increment_usage(target_user_id)
    remaining_limit = _get_remaining_limit(target_user_id)

    # Отправляем «Суть за 30 секунд» с клавиатурой
    await status_msg.edit_text(
        f"✅ Готово!\nОсталось обработок сегодня: {remaining_limit} из {DAILY_LIMIT}"
    )

    summary = learning_pack.get("summary", "")
    summary_text = f"📌 *Суть за 30 секунд*\n\n{summary}" if summary else (
        "Материал обработан. Выберите раздел:"
    )

    await message.answer(
        summary_text,
        reply_markup=_build_keyboard(),
        parse_mode="Markdown",
    )


async def _process_video_and_reply(message: Message, file_id: str) -> None:
    """Обработка видео: скачать → транскрибировать → форматировать → ответить.

    Args:
        message: входящее сообщение.
        file_id: идентификатор файла в Telegram.
    """
    user_id = message.from_user.id
    if not _check_rate_limit(user_id):
        await message.answer(
            "⛔ Лимит на сегодня исчерпан. Завтра можно снова!"
        )
        return

    status_msg = await message.answer("⏳ Скачиваю видео...")
    video_path = None

    try:
        video_path = await _download_file(message.bot, file_id)

        # Извлечение аудио и транскрипция
        await status_msg.edit_text("⏳ Извлекаю аудио...")
        transcript = await process_video(video_path)

        if not transcript:
            await status_msg.edit_text(
                "⚠️ Не удалось распознать речь. "
                "Возможно, в видео нет разговорной речи."
            )
            return

        await _format_and_reply(message, transcript, status_msg)

    except FileNotFoundError as e:
        logger.error("Файл не найден: %s", e)
        await status_msg.edit_text(
            "❌ Не удалось скачать видео. Попробуйте ещё раз."
        )

    except (ValueError, RuntimeError) as e:
        logger.error("Ошибка обработки: %s", e)
        await status_msg.edit_text(f"❌ {e}")

    except Exception:
        logger.exception("Неожиданная ошибка при обработке видео")
        await status_msg.edit_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте позже."
        )

    finally:
        if video_path:
            _safe_remove(video_path)


async def _process_document_and_reply(message: Message, file_id: str,
                                      file_name: str) -> None:
    """Обработка текстового документа: скачать → извлечь текст → форматировать.

    Args:
        message: входящее сообщение.
        file_id: идентификатор файла в Telegram.
        file_name: имя файла для определения расширения.
    """
    user_id = message.from_user.id
    if not _check_rate_limit(user_id):
        await message.answer(
            "⛔ Лимит на сегодня исчерпан. Завтра можно снова!"
        )
        return

    ext = Path(file_name).suffix.lower() if file_name else ""
    status_msg = await message.answer("📄 Обрабатываю документ...")
    file_path = None

    try:
        file_path = await _download_file(message.bot, file_id, default_ext=ext)

        # Извлекаем текст из документа
        text = _extract_text_from_file(file_path)

        if not text or len(text.strip()) < 50:
            await status_msg.edit_text(
                "⚠️ Не удалось извлечь текст из документа или он слишком короткий."
            )
            return

        await _format_and_reply(message, text, status_msg)

    except (ValueError, RuntimeError) as e:
        logger.error("Ошибка обработки документа: %s", e)
        await status_msg.edit_text(f"❌ {e}")

    except Exception:
        logger.exception("Неожиданная ошибка при обработке документа")
        await status_msg.edit_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте позже."
        )

    finally:
        if file_path:
            _safe_remove(file_path)


async def _process_image_and_reply(message: Message, file_id: str) -> None:
    """Обработка одного изображения: скачать → описать → структурировать."""
    user_id = message.from_user.id
    if not _check_rate_limit(user_id):
        await message.answer(
            "⛔ Лимит на сегодня исчерпан. Завтра можно снова!"
        )
        return

    status_msg = await message.answer("🖼 Обрабатываю изображение...")
    image_path = None

    try:
        image_path = await _download_file(message.bot, file_id, default_ext=".jpg")
        description = await describe_image(image_path)

        if not description:
            await status_msg.edit_text(
                "⚠️ Не удалось получить описание изображения."
            )
            return

        await _format_and_reply(message, description, status_msg)

    except FileNotFoundError as error:
        logger.error("Изображение не найдено: %s", error)
        await status_msg.edit_text(
            "❌ Не удалось скачать изображение. Попробуйте ещё раз."
        )

    except (ValueError, RuntimeError) as error:
        logger.error("Ошибка обработки изображения: %s", error)
        await status_msg.edit_text(f"❌ {error}")

    except Exception:
        logger.exception("Неожиданная ошибка при обработке изображения")
        await status_msg.edit_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте позже."
        )

    finally:
        if image_path:
            _safe_remove(image_path)


async def _process_image_group_and_reply(
    message: Message,
    file_ids: list[str],
) -> None:
    """Обработка альбома изображений как единого материала."""
    user_id = message.from_user.id
    if not _check_rate_limit(user_id):
        await message.answer(
            "⛔ Лимит на сегодня исчерпан. Завтра можно снова!"
        )
        return

    status_msg = await message.answer("🖼 Обрабатываю изображения...")
    image_paths: list[str] = []

    try:
        for file_id in file_ids:
            image_path = await _download_file(
                message.bot,
                file_id,
                default_ext=".jpg",
            )
            image_paths.append(image_path)

        description = await describe_images(image_paths)

        if not description:
            await status_msg.edit_text(
                "⚠️ Не удалось получить описание изображений."
            )
            return

        await _format_and_reply(message, description, status_msg)

    except FileNotFoundError as error:
        logger.error("Файл изображения не найден: %s", error)
        await status_msg.edit_text(
            "❌ Не удалось скачать одно из изображений. Попробуйте ещё раз."
        )

    except (ValueError, RuntimeError) as error:
        logger.error("Ошибка обработки альбома: %s", error)
        await status_msg.edit_text(f"❌ {error}")

    except Exception:
        logger.exception("Неожиданная ошибка при обработке альбома")
        await status_msg.edit_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте позже."
        )

    finally:
        for image_path in image_paths:
            _safe_remove(image_path)


async def _wait_and_process_media_group(media_group_id: str) -> None:
    """Ждёт завершения альбома и затем обрабатывает его одним запросом."""
    current_task = asyncio.current_task()
    try:
        await asyncio.sleep(1.5)
        messages = _pending_media_groups.pop(media_group_id, [])
        if not messages:
            return

        file_ids = [
            message.photo[-1].file_id
            for message in messages
            if message.photo
        ]
        if not file_ids:
            return

        await _process_image_group_and_reply(messages[0], file_ids)
    except asyncio.CancelledError:
        return
    finally:
        if _pending_media_group_tasks.get(media_group_id) is current_task:
            _pending_media_group_tasks.pop(media_group_id, None)


async def _process_text_and_reply(
    message: Message,
    text: str,
    user_id: int | None = None,
) -> None:
    """Обработка текстового сообщения: сразу форматировать.

    Args:
        message: входящее сообщение.
        text: текст сообщения.
    """
    target_user_id = user_id or message.from_user.id
    if not _check_rate_limit(target_user_id):
        await message.answer(
            "⛔ Лимит на сегодня исчерпан. Завтра можно снова!"
        )
        return

    status_msg = await message.answer("📄 Обрабатываю текст...")

    try:
        await _format_and_reply(
            message,
            text,
            status_msg,
            user_id=target_user_id,
        )

    except (ValueError, RuntimeError) as e:
        logger.error("Ошибка обработки текста: %s", e)
        await status_msg.edit_text(f"❌ {e}")

    except Exception:
        logger.exception("Неожиданная ошибка при обработке текста")
        await status_msg.edit_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте позже."
        )


def _get_prompt_generator(action: str):
    """Возвращает генератор промпта и человекочитаемый заголовок."""
    if action == "text_action_presentation":
        return generate_presentation_prompt, "Промпт для презентации"
    if action == "text_action_video":
        return generate_video_prompt, "Промпт для видео"
    if action == "text_action_infographic":
        return generate_infographic_prompt, "Промпт для инфографики"
    return None, ""


async def _process_prompt_and_reply(
    message: Message,
    user_id: int,
    pending_text: str,
    action: str,
) -> None:
    """Генерирует специализированный промпт и отправляет его пользователю."""
    if not _check_rate_limit(user_id):
        await message.answer(
            "⛔ Лимит на сегодня исчерпан. Завтра можно снова!"
        )
        return

    generator, prompt_title = _get_prompt_generator(action)
    if generator is None:
        await message.answer("⚠️ Неизвестный режим генерации.")
        return

    status_msg = await message.answer("⏳ Генерирую промпт...")

    try:
        prompt_text = await generator(pending_text)
        if not prompt_text:
            await status_msg.edit_text("⚠️ Не удалось сгенерировать промпт.")
            return

        state = _user_results.setdefault(user_id, {})
        state["pending_text"] = pending_text
        state["generated_prompt"] = prompt_text
        state["generated_prompt_title"] = prompt_title

        _increment_usage(user_id)
        remaining_limit = _get_remaining_limit(user_id)

        await status_msg.edit_text(
            f"✅ {prompt_title} готов!\n"
            f"Осталось обработок сегодня: {remaining_limit} из {DAILY_LIMIT}"
        )

        await _send_long_text(
            message,
            f"{prompt_title}\n\n{prompt_text}",
        )
        await message.answer(
            "Если нужно быстро скопировать текст целиком, нажмите кнопку ниже.",
            reply_markup=_build_copy_prompt_keyboard(),
        )

    except (ValueError, RuntimeError) as error:
        logger.error("Ошибка генерации промпта: %s", error)
        await status_msg.edit_text(f"❌ {error}")

    except Exception:
        logger.exception("Неожиданная ошибка при генерации промпта")
        await status_msg.edit_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте позже."
        )


# --- Callback-обработчики для inline-кнопок ---


@router.callback_query(F.data.in_(set(_PROMPT_ACTIONS.keys())))
async def handle_text_action_callback(callback: CallbackQuery) -> None:
    """Обрабатывает выбор действия для присланного текста."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    pending_text = (user_data or {}).get("pending_text", "")
    if not pending_text:
        await callback.message.answer(
            "⚠️ Текст для обработки не найден. Отправьте описание заново."
        )
        return

    if callback.data == "text_action_learning":
        await _process_text_and_reply(
            callback.message,
            pending_text,
            user_id=callback.from_user.id,
        )
        return

    await _process_prompt_and_reply(
        callback.message,
        callback.from_user.id,
        pending_text,
        callback.data,
    )


@router.callback_query(F.data == PROMPT_COPY_CALLBACK)
async def handle_copy_prompt_callback(callback: CallbackQuery) -> None:
    """Отправляет сгенерированный промпт в виде code block."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    prompt_text = (user_data or {}).get("generated_prompt", "")
    if not prompt_text:
        await callback.message.answer(
            "⚠️ Сначала сгенерируйте промпт, а потом копируйте его."
        )
        return

    await _send_code_block(callback.message, prompt_text)


@router.callback_query(F.data.in_(set(_SECTION_INFO.keys())))
async def handle_section_callback(callback: CallbackQuery) -> None:
    """Отправляет выбранный раздел учебного пакета."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    if not user_data:
        await callback.message.answer(
            "⚠️ Данные устарели. Отправьте материал заново."
        )
        return

    section_key, title = _SECTION_INFO[callback.data]

    # Для промпта NotebookLM берём из отдельного ключа
    if section_key == "notebooklm_prompt":
        text = user_data.get("notebooklm_prompt", "")
    else:
        text = user_data["learning_pack"].get(section_key, "")

    if not text:
        await callback.message.answer(f"{title}\n\nРаздел пуст.")
        return

    full_text = f"{title}\n\n{text}"
    await _send_long_text(callback.message, full_text)


@router.callback_query(F.data == "download_all")
async def handle_download_all(callback: CallbackQuery) -> None:
    """Отправляет полный учебный пакет как .txt файл."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    if not user_data:
        await callback.message.answer(
            "⚠️ Данные устарели. Отправьте материал заново."
        )
        return

    full_text = user_data["learning_pack"].get("full_text", "")
    if not full_text:
        await callback.message.answer("⚠️ Нет данных для скачивания.")
        return

    file_bytes = full_text.encode("utf-8")
    document = BufferedInputFile(file_bytes, filename="учебный_пакет.txt")
    await callback.message.answer_document(
        document, caption="📄 Полный учебный пакет"
    )


@router.callback_query(F.data == "download_notebooklm")
async def handle_download_notebooklm(callback: CallbackQuery) -> None:
    """Отправляет пакет для NotebookLM: транскрипт + промпт-инструкция."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    if not user_data:
        await callback.message.answer(
            "⚠️ Данные устарели. Отправьте материал заново."
        )
        return

    transcript = user_data.get("transcript", "")
    prompt = user_data.get("notebooklm_prompt", "")

    # Формируем единый файл: транскрипт + инструкция
    content = (
        "=" * 60 + "\n"
        "ИСХОДНЫЙ ТЕКСТ / ТРАНСКРИПТ\n"
        "=" * 60 + "\n\n"
        f"{transcript}\n\n"
        "=" * 60 + "\n"
        "ИНСТРУКЦИЯ ДЛЯ NOTEBOOKLM AUDIO OVERVIEW\n"
        "(скопируйте в поле Customize)\n"
        "=" * 60 + "\n\n"
        f"{prompt}\n"
    )

    file_bytes = content.encode("utf-8")
    document = BufferedInputFile(file_bytes, filename="notebooklm_пакет.txt")
    await callback.message.answer_document(
        document, caption="📥 Пакет для NotebookLM (текст + инструкция)"
    )


# --- Обработчики входящих сообщений ---


def _is_text_document(message: Message) -> bool:
    """Проверяет, является ли документ текстовым (txt/pdf/docx)."""
    if not message.document:
        return False
    mime = message.document.mime_type or ""
    name = message.document.file_name or ""
    ext = Path(name).suffix.lower()
    return mime in TEXT_MIME_TYPES or ext in TEXT_EXTENSIONS


def _is_image_document(message: Message) -> bool:
    """Проверяет, является ли документ изображением."""
    if not message.document:
        return False
    mime = message.document.mime_type or ""
    return mime in IMAGE_MIME_TYPES


@router.message(F.video)
async def handle_video(message: Message) -> None:
    """Обработка обычного видео."""
    await _process_video_and_reply(message, message.video.file_id)


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    """Обработка одного изображения или альбома изображений."""
    if message.media_group_id:
        media_group_id = message.media_group_id
        _pending_media_groups.setdefault(media_group_id, []).append(message)

        pending_task = _pending_media_group_tasks.get(media_group_id)
        if pending_task is not None and not pending_task.done():
            pending_task.cancel()

        _pending_media_group_tasks[media_group_id] = asyncio.create_task(
            _wait_and_process_media_group(media_group_id)
        )
        return

    await _process_image_and_reply(message, message.photo[-1].file_id)


@router.message(F.video_note)
async def handle_video_note(message: Message) -> None:
    """Обработка видеосообщения (кружочка)."""
    await _process_video_and_reply(message, message.video_note.file_id)


@router.message(F.document)
async def handle_document(message: Message) -> None:
    """Обработка документа — видео или текстового файла."""
    if message.document and message.document.mime_type in VIDEO_MIME_TYPES:
        await _process_video_and_reply(message, message.document.file_id)
    elif _is_image_document(message):
        await _process_image_and_reply(message, message.document.file_id)
    elif _is_text_document(message):
        await _process_document_and_reply(
            message,
            message.document.file_id,
            message.document.file_name or "",
        )
    else:
        await message.answer(
            "Поддерживаемые форматы: видео (mp4, mkv, webm), "
            "изображения (JPEG, PNG, WebP, GIF), документы (PDF, DOCX, TXT)."
        )


@router.message(F.text)
async def handle_text(message: Message) -> None:
    """Показывает меню действий для текстового сообщения."""
    text = message.text or ""

    # Не обрабатываем команды
    if text.startswith("/"):
        return

    user_state = _user_results.setdefault(message.from_user.id, {})
    user_state["pending_text"] = text

    include_learning_pack = len(text) >= MIN_TEXT_LENGTH
    menu_text = "Что сделать с этим текстом?"
    if not include_learning_pack:
        menu_text += (
            f"\n\nТекст короче {MIN_TEXT_LENGTH} символов, поэтому доступна "
            "только генерация промптов."
        )

    await message.answer(
        menu_text,
        reply_markup=_build_text_action_keyboard(include_learning_pack),
    )
