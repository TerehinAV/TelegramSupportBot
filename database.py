from models import db, Ticket, MessageLog


def initialize_db():
    db.connect(reuse_if_open=True)
    db.create_tables([Ticket, MessageLog])  # Создаём таблицу Ticket, если она ещё не создана
    db.close()


# Инициализация базы данных
initialize_db()
