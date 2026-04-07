# Обработчик входящих документов, изображений и текстовых сообщений

import html
import logging
import os
import uuid
from dataclasses import dataclass, field
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
)
from services.vision import describe_images

logger = logging.getLogger(__name__)
router = Router()

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

@dataclass
class PendingImageBatch:
    """Буфер изображений пользователя до завершения загрузки серии."""

    anchor_message: Message
    file_ids: list[str] = field(default_factory=list)
    seen_message_ids: set[int] = field(default_factory=set)
    status_message: Message | None = None


# Временное хранилище изображений по связке чат + пользователь
_pending_image_batches: dict[tuple[int, int], PendingImageBatch] = {}

IMAGE_BATCH_DONE_CALLBACK = "image_batch_done"
IMAGE_BATCH_CLEAR_CALLBACK = "image_batch_clear"

# Маппинг callback-данных на ключи результатов и заголовки
_SECTION_INFO = {
    "source_text": ("transcript", "🧾 Исходный текст / OCR"),
    "key_points": ("key_points", "📋 Ключевые тезисы"),
    "plan": ("plan", "📝 План материала"),
    "quiz": ("quiz", "❓ Вопросы для самопроверки"),
    "cards": ("cards", "🃏 Карточки для запоминания"),
    "practice": ("practice", "💪 Практическое задание"),
    "notebooklm_prompt": ("notebooklm_prompt", "🎙 Промпт для NotebookLM"),
}

_PROMPT_ACTIONS = {
    "text_action_learning": "📚 Учебный пакет",
    "text_action_presentation": "🖼 Промпт для презентации",
    "text_action_infographic": "📊 Промпт для инфографики",
}

PROMPT_COPY_CALLBACK = "copy_generated_prompt"
SOURCE_TEXT_COPY_CALLBACK = "copy_source_text"
SOURCE_TEXT_EXPORT_CALLBACK = "export_source_text"
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
            InlineKeyboardButton(
                text="🧾 Исходный текст / OCR",
                callback_data="source_text",
            ),
            InlineKeyboardButton(
                text="📋 Скопировать OCR",
                callback_data=SOURCE_TEXT_COPY_CALLBACK,
            ),
        ],
        [
            InlineKeyboardButton(
                text="📄 Исходник .txt",
                callback_data=SOURCE_TEXT_EXPORT_CALLBACK,
            ),
        ],
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


def _build_image_batch_keyboard() -> InlineKeyboardMarkup:
    """Создаёт кнопки управления очередью изображений."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Готово",
                callback_data=IMAGE_BATCH_DONE_CALLBACK,
            ),
            InlineKeyboardButton(
                text="🗑 Очистить",
                callback_data=IMAGE_BATCH_CLEAR_CALLBACK,
            ),
        ]
    ])


def _build_image_batch_wait_text(count: int) -> str:
    """Формирует статус ручного ожидания серии изображений."""
    if count <= 1:
        return (
            "📥 Получил 1 изображение.\n"
            "Если хочешь отправить ещё фото, просто досылай их.\n"
            "Когда закончишь, нажми «Готово»."
        )

    return (
        f"📥 Получено изображений: {count}\n"
        "Можешь продолжать загрузку.\n"
        "Когда закончишь, нажми «Готово»."
    )


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


async def _send_text_as_document(
    message: Message,
    text: str,
    filename: str,
    caption: str,
) -> None:
    """Отправляет полный текст одним .txt файлом."""
    file_bytes = text.encode("utf-8")
    document = BufferedInputFile(file_bytes, filename=filename)
    await message.answer_document(document, caption=caption)


async def _format_and_reply(
    message: Message,
    transcript: str,
    status_msg: Message,
    user_id: int | None = None,
) -> None:
    """Общая логика форматирования: GitHub Models → inline-кнопки.

    Args:
        message: входящее сообщение пользователя.
        transcript: исходный текст (OCR или текст документа).
        status_msg: сообщение-статус для обновления прогресса.
    """
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
    """Добавляет изображение в очередь и ждёт явного подтверждения."""
    await _queue_image_for_batch(message, file_id)


async def _process_image_group_and_reply(
    message: Message,
    file_ids: list[str],
    status_msg: Message | None = None,
) -> None:
    """Обработка серии изображений как единого материала."""
    user_id = message.from_user.id
    if not _check_rate_limit(user_id):
        await message.answer(
            "⛔ Лимит на сегодня исчерпан. Завтра можно снова!"
        )
        return

    count = len(file_ids)
    image_label = "изображение" if count == 1 else "изображений"
    note = ""
    if count > 10:
        note = "\n⏳ Много изображений — обработка займёт пару минут."

    if status_msg is None:
        status_msg = await message.answer(
            f"🖼 Обрабатываю {count} {image_label}...{note}"
        )
    else:
        await status_msg.edit_text(
            f"🖼 Обрабатываю {count} {image_label}...{note}"
        )

    image_paths: list[str] = []

    try:
        for file_id in file_ids:
            image_path = await _download_file(
                message.bot,
                file_id,
                default_ext=".jpg",
            )
            image_paths.append(image_path)

        async def _progress(current: int, total: int) -> None:
            try:
                await status_msg.edit_text(
                    f"🖼 Обрабатываю изображение {current} из {total}..."
                )
            except Exception:
                pass  # edit_text может упасть если текст не изменился

        description = await describe_images(image_paths, progress_callback=_progress)

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


async def _queue_image_for_batch(message: Message, file_id: str) -> None:
    """Складывает изображения в общий буфер до нажатия кнопки."""
    session_key = (message.chat.id, message.from_user.id)
    batch = _pending_image_batches.get(session_key)
    if batch is None:
        batch = PendingImageBatch(anchor_message=message)
        _pending_image_batches[session_key] = batch

    if message.message_id not in batch.seen_message_ids:
        batch.seen_message_ids.add(message.message_id)
        batch.file_ids.append(file_id)

    status_text = _build_image_batch_wait_text(len(batch.file_ids))
    if batch.status_message is None:
        batch.status_message = await message.answer(
            status_text,
            reply_markup=_build_image_batch_keyboard(),
        )
    else:
        try:
            await batch.status_message.edit_text(
                status_text,
                reply_markup=_build_image_batch_keyboard(),
            )
        except Exception:
            pass

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

@router.callback_query(F.data == SOURCE_TEXT_COPY_CALLBACK)
async def handle_source_text_copy_callback(callback: CallbackQuery) -> None:
    """Отправляет исходный OCR в копируемом виде, даже если он длинный."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    source_text = (user_data or {}).get("transcript", "")
    if not source_text:
        await callback.message.answer(
            "⚠️ Исходный текст не найден. Отправьте материал заново."
        )
        return

    await callback.message.answer(
        "📋 Отправляю OCR в копируемом виде. "
        "Если текст длинный, он придёт несколькими блоками."
    )
    await _send_code_block(callback.message, source_text)


@router.callback_query(F.data == SOURCE_TEXT_EXPORT_CALLBACK)
async def handle_source_text_export_callback(callback: CallbackQuery) -> None:
    """Отдаёт исходный текст целиком одним файлом."""
    await callback.answer()

    user_data = _user_results.get(callback.from_user.id)
    source_text = (user_data or {}).get("transcript", "")
    if not source_text:
        await callback.message.answer(
            "⚠️ Исходный текст не найден. Отправьте материал заново."
        )
        return

    await _send_text_as_document(
        callback.message,
        source_text,
        filename="исходный_текст.txt",
        caption="📄 Полный исходный текст / OCR одним файлом",
    )

@router.callback_query(F.data == IMAGE_BATCH_DONE_CALLBACK)
async def handle_image_batch_done_callback(callback: CallbackQuery) -> None:
    """Запускает обработку накопленной серии изображений."""
    session_key = (callback.message.chat.id, callback.from_user.id)
    batch = _pending_image_batches.pop(session_key, None)

    if batch is None or not batch.file_ids:
        await callback.answer("Очередь изображений уже пуста.", show_alert=True)
        return

    await callback.answer("Запускаю обработку...")

    status_message = batch.status_message or callback.message
    try:
        await status_message.edit_text(
            f"🖼 Запускаю обработку {len(batch.file_ids)} изображений..."
        )
    except Exception:
        pass

    await _process_image_group_and_reply(
        batch.anchor_message,
        batch.file_ids,
        status_msg=status_message,
    )


@router.callback_query(F.data == IMAGE_BATCH_CLEAR_CALLBACK)
async def handle_image_batch_clear_callback(callback: CallbackQuery) -> None:
    """Очищает очередь накопленных изображений без обработки."""
    session_key = (callback.message.chat.id, callback.from_user.id)
    batch = _pending_image_batches.pop(session_key, None)

    if batch is None or not batch.file_ids:
        await callback.answer("Тут уже нечего очищать.", show_alert=True)
        return

    await callback.answer("Очередь очищена")

    status_message = batch.status_message or callback.message
    try:
        await status_message.edit_text(
            "🗑 Очередь изображений очищена.\n"
            "Можешь отправить новую серию заново."
        )
    except Exception:
        pass


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
    elif section_key == "transcript":
        text = user_data.get("transcript", "")
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


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    """Складывает фото в общую серию и ждёт окончания загрузки."""
    await _process_image_and_reply(message, message.photo[-1].file_id)


@router.message(F.document)
async def handle_document(message: Message) -> None:
    """Обработка документа — текстового файла или изображения."""
    if _is_image_document(message):
        await _queue_image_for_batch(message, message.document.file_id)
    elif _is_text_document(message):
        await _process_document_and_reply(
            message,
            message.document.file_id,
            message.document.file_name or "",
        )
    else:
        await message.answer(
            "Поддерживаемые форматы: "
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
