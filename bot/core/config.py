from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramSettings(BaseModel):
    bot_token: str
    superadmin: int
    database_url: str = "sqlite+aiosqlite:///./backups.db"


class SiteSettings(BaseModel):
    name: str
    wp_path: str
    db_name: str
    db_user: str
    db_pass: str

    @field_validator("wp_path")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


class BackupSettings(BaseModel):
    dir: str
    tmp_dir: str
    free_space_mb: int = 40960


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
    )
    tg: TelegramSettings
    site: SiteSettings
    backup: BackupSettings


settings = Settings()
