from pydantic import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "BYP Ops System"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
