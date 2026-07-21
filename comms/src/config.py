from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "CommsService"
    MINDOS_ENV: str = "development"

    # Event Bus (F3-T3): todo mensaje entrante, sin importar el canal, se publica aquí.
    REDIS_URL: str = "redis://localhost:6379/0"
    INBOUND_STREAM: str = "mindos.comms"

    # CLI (F3-T3): el comando `mindos capture` pasa por el Gateway como cualquier otro
    # cliente externo (único punto de entrada seguro, F3-T1) — no le da un atajo directo a comms.
    CLI_TARGET_URL: str = "http://localhost:8000"
    MINDOS_API_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
