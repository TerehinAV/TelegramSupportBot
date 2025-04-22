from datetime import datetime

from peewee import Model, SqliteDatabase, BigIntegerField, CharField, DateTimeField, BooleanField, ForeignKeyField, \
    IntegerField, TextField

# Создание подключения к базе данных
db = SqliteDatabase("tickets.db")


class BaseModel(Model):
    class Meta:
        database = db


class Ticket(BaseModel):
    user_id = BigIntegerField()
    username = CharField(null=True)
    # is_open = BooleanField(default=True)
    original_message_id = BigIntegerField()
    created_at = DateTimeField()
    is_closed = BooleanField(default=False)
    active_by = IntegerField(null=True)  # Telegram ID сотрудника
    active_username = CharField(null=True)  # Ник сотрудника


class MessageLog(BaseModel):
    ticket = ForeignKeyField(Ticket, backref='messages', on_delete='CASCADE')
    user_message_id = IntegerField(null=True)
    forwarded_message_id = IntegerField(null=True)
    sender = CharField()  # 'user' or 'staff'
    staff_id = IntegerField(null=True)  # ID ответившего сотрудника
    staff_username = CharField(null=True)  # по желанию
    text = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
