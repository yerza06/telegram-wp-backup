import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.core.config import settings
from bot.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


async def notify_all(bot: Bot, session_maker: async_sessionmaker, text: str) -> None:
    async with session_maker() as session:
        repo = UserRepository(session)
        active_users = await repo.list_active()

    recipients = {u.telegram_id for u in active_users}
    recipients.add(settings.tg.superadmin)

    for tg_id in recipients:
        try:
            await bot.send_message(tg_id, text, parse_mode="HTML")
        except Exception as e:
            logger.warning("Failed to notify user %s: %s", tg_id, e)


def fmt_size(size_bytes: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes} ТБ"
