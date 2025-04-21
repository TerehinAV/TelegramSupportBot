from aiogram.types import Message, CallbackQuery
from aiogram import Router
from aiogram import F
from models import Ticket, MessageLog
from database import db

staff_router = Router(name="staff")


@staff_router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_staff_reply(message: Message):
    if not message.reply_to_message:
        return

    reply_to_id = message.reply_to_message.message_id

    db.connect(reuse_if_open=True)
    log_entry = MessageLog.select().where(
        MessageLog.forwarded_message_id == reply_to_id
    ).first()

    if log_entry and log_entry.ticket.is_open:
        ticket = log_entry.ticket
        MessageLog.create(
            ticket=ticket,
            forwarded_message_id=message.message_id,
            sender='staff',
            text=message.text
        )

        try:
            await message.bot.send_message(
                chat_id=ticket.user_id,
                text=f"💬 Поддержка: {message.text}"
            )
        except Exception as e:
            print("Ошибка при отправке пользователю:", e)
    else:
        print("Сообщение не связано с тикетом или тикет закрыт")
    db.close()


@staff_router.callback_query(F.data.startswith("close:"))
async def handle_close_ticket(callback: CallbackQuery):
    _, forwarded_msg_id = callback.data.split(":")
    forwarded_msg_id = int(forwarded_msg_id)

    db.connect(reuse_if_open=True)

    log_entry = MessageLog.select().where(
        MessageLog.forwarded_message_id == forwarded_msg_id
    ).first()

    if not log_entry or not log_entry.ticket.is_open:
        await callback.answer("❌ Тикет уже закрыт или не найден.")
        db.close()
        return

    ticket = log_entry.ticket
    ticket.is_open = False
    ticket.save()

    # 🟢 Добавим пометку о закрытии
    try:
        original_msg = callback.message
        updated_text = original_msg.text + "\n\n🟢 Тикет закрыт сотрудником поддержки."
        await callback.message.edit_text(
            updated_text,
            reply_markup=None
        )
    except Exception as e:
        print("❗ Не удалось обновить сообщение:", e)

    await callback.answer("✅ Тикет закрыт")

    # Уведомим пользователя
    try:
        await callback.bot.send_message(
            chat_id=ticket.user_id,
            text="✅ Ваше обращение было закрыто сотрудником поддержки."
        )
    except Exception as e:
        print("Ошибка отправки пользователю:", e)

    db.close()
