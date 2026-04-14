import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.filters import AdminFilter, AnyActiveFilter
from bot.keyboards import backup_list_kb, confirm_kb
from bot.repositories.backup_repo import BackupRepository, RestoreRepository
from bot.services import restore_service

router = Router()


@router.message(Command("restore"), AdminFilter())
async def cmd_restore_menu(message: Message, session_maker: async_sessionmaker) -> None:
    async with session_maker() as session:
        repo = BackupRepository(session)
        backups = await repo.list_successful()

    if not backups:
        await message.answer("Нет успешных бэкапов для восстановления.")
        return

    await message.answer(
        "Выберите бэкап для восстановления:",
        reply_markup=backup_list_kb(backups[:10], action="restore_select"),
    )


@router.callback_query(F.data.startswith("restore_select:"), AdminFilter())
async def cb_restore_select(call: CallbackQuery, session_maker: async_sessionmaker) -> None:
    backup_id = int(call.data.split(":")[1])

    async with session_maker() as session:
        repo = BackupRepository(session)
        b = await repo.get_by_id(backup_id)
        if not b:
            await call.answer("Бэкап не найден.", show_alert=True)
            return

    await call.message.edit_text(
        f"⚠️ Восстановить из бэкапа #{b.id}?\n"
        f"Файл: {b.file_name}\n\n"
        f"<b>Внимание:</b> текущие файлы и база данных WordPress будут перезаписаны!",
        parse_mode="HTML",
        reply_markup=confirm_kb("do_restore", backup_id),
    )


@router.callback_query(F.data.startswith("confirm:do_restore:"), AdminFilter())
async def cb_restore_confirm(
    call: CallbackQuery,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
    db_user=None,
) -> None:
    backup_id = int(call.data.split(":")[2])
    triggered_by = 1 if is_superadmin else db_user.telegram_id

    await call.message.edit_text("Восстановление запущено. Уведомление придёт по завершении.")

    asyncio.create_task(
        restore_service.run_restore(
            bot=call.bot,
            session_maker=session_maker,
            backup_id=backup_id,
            triggered_by=triggered_by,
        )
    )


@router.message(Command("restore_history"), AnyActiveFilter())
async def cmd_restore_history(message: Message, session_maker: async_sessionmaker) -> None:
    async with session_maker() as session:
        repo = RestoreRepository(session)
        restores = await repo.list_all(limit=20)

        backup_repo = BackupRepository(session)

    if not restores:
        await message.answer("История восстановлений пуста.")
        return

    lines = []
    for r in restores:
        backup_name = f"#{r.backup_id}" if r.backup_id else "удалён"
        triggered = f"пользователь {r.triggered_by}" if r.triggered_by and r.triggered_by != 1 else "superadmin"
        if r.triggered_by is None:
            triggered = "по расписанию"
        lines.append(
            f"#{r.id} | {r.created_at.strftime('%Y-%m-%d %H:%M')} | "
            f"из бэкапа {backup_name} | {triggered} | {r.status.value}"
        )

    await message.answer("История восстановлений:\n\n" + "\n".join(lines))
