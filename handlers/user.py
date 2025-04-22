from aiogram.filters import Command
from aiogram.types import Message
from aiogram import Router
from aiogram import F
from datetime import datetime
from config import SUPPORT_CHAT_ID
from models import Ticket, MessageLog
from database import db
from keyboards import close_ticket_keyboard


user_router = Router(name="user")


@user_router.message(Command("status"))
async def ticket_status(message: Message):
    db.connect(reuse_if_open=True)

    ticket = Ticket.select().where(
        (Ticket.user_id == message.from_user.id) & (Ticket.is_closed == False)
    ).first()

    if not ticket:
        await message.answer("У вас нет открытых обращений.")
    else:
        messages_count = MessageLog.select().where(MessageLog.ticket == ticket, Ticket.user_id == message.from_user.id).join(Ticket).count()
        await message.answer(
            f"📋 Статус обращения:\n"
            f"🆔 Тикет #{ticket.id}\n"
            f"✉️ Сообщений: {messages_count}\n"
            f"🟢 Статус: Открыт"
        )

    db.close()


@user_router.message(Command("cancel"))
async def cancel_ticket(message: Message):
    db.connect(reuse_if_open=True)

    ticket = Ticket.select().where(
        (Ticket.user_id == message.from_user.id) & (Ticket.is_closed == False)
    ).first()

    if not ticket:
        await message.answer("У вас нет открытых обращений.")
        db.close()
        return

    ticket.is_closed = True
    ticket.save()

    # уведомим пользователя
    await message.answer("Вы отменили обращение. Тикет закрыт ✅")

    # отправим в поддержку уведомление
    try:
        await message.bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            text=f"⚠️ Пользователь @{message.from_user.username or 'без ника'} отменил своё обращение (#ticket_{ticket.id})."
        )
    except Exception as e:
        print("Не удалось уведомить поддержку:", e)

    db.close()


@user_router.message(F.chat.type.in_({"private"}))
async def handle_user_message(message: Message):
    user_id = message.from_user.id

    db.connect(reuse_if_open=True)

    # Пытаемся найти открытый тикет
    ticket = Ticket.select().where(
        (Ticket.user_id == user_id) & (Ticket.is_closed == False)
    ).first()

    # Если тикета нет — создаём новый
    if not ticket:
        ticket = Ticket.create(
            user_id=user_id,
            username=message.from_user.username,
            original_message_id=message.message_id,
            forwarded_message_id=0,  # обновим позже
            created_at=datetime.now(),
        )

    # 🧼 Удаляем кнопку у предыдущего сообщения в чате поддержки
    last_log = (
        MessageLog
        .select()
        .where(MessageLog.ticket == ticket)
        .order_by(MessageLog.created_at.desc())
        .first()
    )

    if last_log:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=SUPPORT_CHAT_ID,
                message_id=last_log.forwarded_message_id,
                reply_markup=None
            )
        except Exception as e:
            print("⚠️ Не удалось удалить кнопку:", e)

    # Формируем текст
    text = (
        f"📩 Сообщение от @{message.from_user.username or 'без ника'}\n"
        f"#ticket_{ticket.id}\n\n"
        f"{message.text}\n\n"
        f"ℹ️ Чтобы ответить пользователю, отправьте сообщение в ответ на это сообщение."
    )

    sent = await message.bot.send_message(
        chat_id=SUPPORT_CHAT_ID,
        text=text,
        # 👇 кнопка теперь добавляется после создания
        reply_markup=None
    )

    # после отправки в поддержку
    MessageLog.create(
        ticket=ticket,
        user_message_id=message.message_id,
        forwarded_message_id=sent.message_id,
        sender='user',
        text=message.text
    )

    await sent.edit_reply_markup(reply_markup=close_ticket_keyboard(sent.message_id))

    await message.answer(
        "Сообщение отправлено в поддержку ✅\n"
        "ℹ️ Вы можете:\n"
        "• Отменить обращение — /cancel\n"
        "• Проверить статус обращения — /status"
    )
