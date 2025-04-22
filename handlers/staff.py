from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Router
from aiogram import F
from peewee import fn

from fsm import StaffStates
from models import Ticket, MessageLog
from database import db

staff_router = Router(name="staff")


@staff_router.message(Command("tickets"))
async def list_tickets(message: Message):
    open_tickets = Ticket.select().where(Ticket.is_closed == False)

    if not open_tickets:
        await message.reply("🎉 Открытых тикетов нет.")
        return

    for ticket in open_tickets:
        # Считаем количество сообщений
        user_msgs = MessageLog.select().where(
            (MessageLog.ticket == ticket.id) & (MessageLog.sender == "user")
        ).count()
        staff_msgs = MessageLog.select().where(
            (MessageLog.ticket == ticket.id) & (MessageLog.sender == "staff")
        ).count()

        # История поддержки по тикету
        participants = (
            MessageLog
            .select(
                MessageLog.staff_username,
                fn.COUNT(MessageLog.id).alias('count')
            )
            .where(
                (MessageLog.ticket == ticket.id) &
                (MessageLog.sender == "staff") &
                (MessageLog.staff_username.is_null(False))
            )
            .group_by(MessageLog.staff_username)
        )
        staff_list = [f"• @{p.staff_username} - {p.count} " for p in participants if p.staff_username]
        participants_text = '\n'.join(staff_list) if staff_list else ''

        # Основной текст
        text = (
            f"🆔 #ticket_{ticket.id} | @{ticket.username or 'unknown'}\n"
            f"👤 Пользователь: {user_msgs} / 💬 Поддержка: {staff_msgs}"
        )

        if ticket.active_username:
            text += f"\n⏳ Обрабатывает: @{ticket.active_username}"

        if participants_text:
            participants_text = f"\n\n 👥 Участвовали:\n{participants_text}"
            text += f"<blockquote expandable>{participants_text}</blockquote>"

        # Кнопки
        buttons = [
            [
                InlineKeyboardButton(
                    text="🔁 Ответить",
                    callback_data=f"reply_ticket:{ticket.id}"
                ),
                InlineKeyboardButton(
                    text="✅ Закрыть",
                    callback_data=f"close_ticket:{ticket.id}"
                )
            ]
        ]

        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )


@staff_router.callback_query(F.data.startswith("close_ticket:"))
async def handle_close_ticket(callback: CallbackQuery):
    _, ticket_id = callback.data.split(":")
    ticket = Ticket.get_or_none(Ticket.id == ticket_id)

    db.connect(reuse_if_open=True)

    if ticket.is_closed:
        await callback.answer("❌ Тикет уже закрыт или не найден.")
        db.close()
        return

    ticket.is_closed = True
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


@staff_router.callback_query(F.data.startswith("reply_ticket:"))
async def start_reply(callback: CallbackQuery, state: FSMContext):
    _, ticket_id = callback.data.split(":")
    ticket = Ticket.get_or_none(Ticket.id == ticket_id)

    ticket.active_by = callback.from_user.id
    ticket.active_username = callback.from_user.username or callback.from_user.full_name
    ticket.save()

    await state.set_state(StaffStates.replying)
    await state.update_data(
        ticket_id=int(ticket_id),
        staff_id=callback.from_user.id  # <--- вот это важно
    )
    user_caption = f"@{ticket.username}" if ticket.username else f"{ticket.user_id}"
    await callback.message.answer(
        f"✍️ @{callback.from_user.username or callback.from_user.first_name}, напишите сообщение — оно будет отправлено пользователю {user_caption}."
    )
    await callback.answer()


@staff_router.message(StaffStates.replying)
async def send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    expected_staff_id = data.get("staff_id")

    # Если не тот сотрудник — вежливо укажем, кто работает с тикетом
    if message.from_user.id != expected_staff_id:
        db.connect(reuse_if_open=True)
        staff_user = await message.bot.get_chat(expected_staff_id)
        name = staff_user.username or staff_user.full_name or f"user {expected_staff_id}"
        await message.reply(
            f"⚠️ Сейчас с тикетом работает @{name}.\n"
            "Пожалуйста, не отправляйте сообщение — оно не будет обработано."
        )
        db.close()
        return

    db.connect(reuse_if_open=True)
    ticket = Ticket.get_or_none(Ticket.id == ticket_id)

    if not ticket:
        await message.reply("❌ Тикет не найден.")
        await state.clear()
        db.close()
        return

    # Сохраняем ответ
    MessageLog.create(
        ticket=ticket,
        sender="staff",
        staff_id=message.from_user.id,
        staff_username=message.from_user.username,
        text=message.text,
    )

    # Отправляем пользователю
    try:
        await message.bot.send_message(
            chat_id=ticket.user_id,
            text=f"💬👤: {message.text}"
        )
        await message.reply("✅ Ответ отправлен.")
        ticket.active_by = None
        ticket.active_username = None
        ticket.save()
    except Exception as e:
        await message.reply("⚠️ Не удалось отправить сообщение.")
        print(e)

    await state.clear()
    db.close()


@staff_router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_staff_reply(message: Message):
    if not message.reply_to_message:
        return

    reply_to_id = message.reply_to_message.message_id

    db.connect(reuse_if_open=True)
    log_entry = MessageLog.select().where(
        MessageLog.forwarded_message_id == reply_to_id
    ).first()

    if log_entry and not log_entry.ticket.is_closed:
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
