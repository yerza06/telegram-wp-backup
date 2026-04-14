from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.core.config import settings
from bot.keyboards import user_actions_kb, user_list_kb
from bot.models.user import UserRole
from bot.repositories.user_repo import UserRepository

router = Router()


def _is_superadmin(is_superadmin: bool = False) -> bool:
    return is_superadmin


@router.message(Command("users"))
async def cmd_users(
    message: Message,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
) -> None:
    if not is_superadmin:
        await message.answer("Недостаточно прав.")
        return

    async with session_maker() as session:
        repo = UserRepository(session)
        users = await repo.list_all()

    if not users:
        await message.answer("Пользователей нет.")
        return

    await message.answer("Список пользователей:", reply_markup=user_list_kb(users))


@router.callback_query(F.data == "user_list")
async def cb_user_list(
    call: CallbackQuery,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
) -> None:
    if not is_superadmin:
        await call.answer("Недостаточно прав.", show_alert=True)
        return

    async with session_maker() as session:
        repo = UserRepository(session)
        users = await repo.list_all()

    await call.message.edit_text("Список пользователей:", reply_markup=user_list_kb(users))


@router.callback_query(F.data.startswith("user_view:"))
async def cb_user_view(
    call: CallbackQuery,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
) -> None:
    if not is_superadmin:
        await call.answer("Недостаточно прав.", show_alert=True)
        return

    telegram_id = int(call.data.split(":")[1])

    async with session_maker() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(telegram_id)

    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    status = "активен" if user.is_active else "неактивен"
    text = (
        f"Пользователь #{user.telegram_id}\n"
        f"Имя: {user.fullname or '—'}\n"
        f"Username: @{user.username or '—'}\n"
        f"Роль: {user.role.value}\n"
        f"Статус: {status}\n"
        f"Добавлен: {user.created_at.strftime('%Y-%m-%d %H:%M')}"
    )
    await call.message.edit_text(
        text,
        reply_markup=user_actions_kb(telegram_id, user.is_active, user.role.value),
    )


async def _refresh_user_view(call: CallbackQuery, session_maker: async_sessionmaker, telegram_id: int) -> None:
    async with session_maker() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(telegram_id)

    if not user:
        await call.message.edit_text("Пользователь не найден.")
        return

    status = "активен" if user.is_active else "неактивен"
    text = (
        f"Пользователь #{user.telegram_id}\n"
        f"Имя: {user.fullname or '—'}\n"
        f"Username: @{user.username or '—'}\n"
        f"Роль: {user.role.value}\n"
        f"Статус: {status}\n"
        f"Добавлен: {user.created_at.strftime('%Y-%m-%d %H:%M')}"
    )
    await call.message.edit_text(
        text,
        reply_markup=user_actions_kb(telegram_id, user.is_active, user.role.value),
    )


@router.callback_query(F.data.startswith("user_activate:"))
async def cb_user_activate(
    call: CallbackQuery,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
) -> None:
    if not is_superadmin:
        await call.answer("Недостаточно прав.", show_alert=True)
        return

    telegram_id = int(call.data.split(":")[1])
    async with session_maker() as session:
        repo = UserRepository(session)
        await repo.activate(telegram_id)

    await call.answer("Пользователь активирован.")
    await _refresh_user_view(call, session_maker, telegram_id)


@router.callback_query(F.data.startswith("user_deactivate:"))
async def cb_user_deactivate(
    call: CallbackQuery,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
) -> None:
    if not is_superadmin:
        await call.answer("Недостаточно прав.", show_alert=True)
        return

    telegram_id = int(call.data.split(":")[1])
    async with session_maker() as session:
        repo = UserRepository(session)
        await repo.deactivate(telegram_id)

    await call.answer("Пользователь деактивирован.")
    await _refresh_user_view(call, session_maker, telegram_id)


@router.callback_query(F.data.startswith("user_role:"))
async def cb_user_role(
    call: CallbackQuery,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
) -> None:
    if not is_superadmin:
        await call.answer("Недостаточно прав.", show_alert=True)
        return

    parts = call.data.split(":")
    telegram_id = int(parts[1])
    new_role = UserRole(parts[2])

    async with session_maker() as session:
        repo = UserRepository(session)
        await repo.set_role(telegram_id, new_role)

    await call.answer(f"Роль изменена на {new_role.value}.")
    await _refresh_user_view(call, session_maker, telegram_id)
