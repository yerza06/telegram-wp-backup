from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.core.config import settings
from bot.repositories.user_repo import UserRepository


class AuthMiddleware(BaseMiddleware):
    def __init__(self, session_maker: async_sessionmaker) -> None:
        self.session_maker = session_maker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = data.get("event_from_user")

        if from_user is None:
            return await handler(event, data)

        user_id = from_user.id
        is_superadmin = user_id == settings.tg.superadmin
        data["is_superadmin"] = is_superadmin

        if is_superadmin:
            data["db_user"] = None
            return await handler(event, data)

        async with self.session_maker() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(user_id)

        data["db_user"] = user

        # Allow /start through for registration
        if isinstance(event, Message) and event.text == "/start":
            return await handler(event, data)

        if user is None or not user.is_active:
            if isinstance(event, Message):
                await event.answer("Доступ не разрешён. Отправьте /start для регистрации.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Доступ не разрешён.", show_alert=True)
            return

        return await handler(event, data)
