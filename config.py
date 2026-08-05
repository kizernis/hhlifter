from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Данные для HH (берем из .env)
    hh_login: str = Field(alias="HH_LOGIN")
    hh_password: str = Field(alias="HH_PASSWORD")
    
    # Настройки базы (по умолчанию для локального запуска)
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "user"
    db_pass: str = "password"
    db_name: str = "tracker_db"

    # Настройки Redis
    redis_host: str = "localhost"

    @property
    def db_url(self):
        # Собираем строку подключения
        return f"postgresql://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redis_url(self):
        return f"redis://{self.redis_host}:6379/0"

    # Указываем, что нужно читать данные из файла .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Создаем один экземпляр настроек для всего проекта
settings = Settings() # type: ignore
