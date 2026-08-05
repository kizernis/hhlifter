from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings

# Движок, который будет "разговаривать" с базой
engine = create_engine(settings.db_url)

# Наша фабрика сессий (соединений)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для всех будущих моделей
class Base(DeclarativeBase):
    pass