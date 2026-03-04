from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def edit_or_send(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
        return message
    except TelegramBadRequest:
        return await message.answer(text, reply_markup=reply_markup)