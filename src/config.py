from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ANTHROPIC_API_KEY: str = "mock-key"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
