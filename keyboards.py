from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def close_ticket_keyboard(ticket_msg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Закрыть тикет", callback_data=f"close:{ticket_msg_id}")]
    ])
