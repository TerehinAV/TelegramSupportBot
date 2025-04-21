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
    is_open = BooleanField(default=True)
    original_message_id = BigIntegerField()
    # forwarded_message_id = BigIntegerField()
    created_at = DateTimeField()


class MessageLog(BaseModel):
    ticket = ForeignKeyField(Ticket, backref='messages', on_delete='CASCADE')
    user_message_id = IntegerField(null=True)
    forwarded_message_id = IntegerField(null=True)
    sender = CharField()  # 'user' or 'staff'
    text = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
