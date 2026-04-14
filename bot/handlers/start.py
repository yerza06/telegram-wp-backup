from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.models.user import UserRole
from bot.repositories.user_repo import UserRepository

router = Router()


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
    db_user=None,
) -> None:
    if is_superadmin:
        await message.answer(
            "Добро пожаловать, superadmin!\n\n"
            "Доступные команды:\n"
            "/backup — управление бэкапами\n"
            "/restore — восстановление\n"
            "/schedule — расписание\n"
            "/users — пользователи\n"
            "/disk — дисковое пространство\n"
            "/cache — очистить кэш WP"
        )
        return

    user_id = message.from_user.id
    username = message.from_user.username
    fullname = message.from_user.full_name

    async with session_maker() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(user_id)

        if user is None:
            user = await repo.create(
                telegram_id=user_id,
                username=username,
                fullname=fullname,
                role=UserRole.viewer,
                is_active=False,
            )
            await message.answer(
                "Добро пожаловать! Ваш запрос на доступ отправлен администратору.\n"
                "Ожидайте активации вашей учётной записи."
            )
            return

    if not user.is_active:
        await message.answer("Ваша учётная запись ожидает активации администратором.")
        return

    role_label = "администратор" if user.role == UserRole.admin else "наблюдатель"
    commands = [
        "/backup — бэкапы",
        "/disk — дисковое пространство",
    ]
    if user.role == UserRole.admin:
        commands += [
            "/restore — восстановление",
            "/schedule — расписание",
            "/cache — очистить кэш WP",
        ]

    await message.answer(
        f"Добро пожаловать, {user.fullname or user.username}! Ваша роль: {role_label}.\n\n"
        "Доступные команды:\n" + "\n".join(commands)
    )
