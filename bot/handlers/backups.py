import asyncio
import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.filters import AdminFilter, AnyActiveFilter
from bot.keyboards import backup_list_kb, confirm_kb
from bot.repositories.backup_repo import BackupRepository
from bot.services import backup_service, notification_service

router = Router()

PAGE_SIZE = 5


@router.message(Command("backup"), AnyActiveFilter())
async def cmd_backup_menu(message: Message) -> None:
    await message.answer(
        "Управление бэкапами:\n"
        "/backup_create — создать бэкап\n"
        "/backup_list — список бэкапов\n"
        "/backup_count — количество бэкапов"
    )


@router.message(Command("backup_create"), AdminFilter())
async def cmd_backup_create(message: Message) -> None:
    await message.answer(
        "⚠️ Создать полный бэкап WordPress (файлы + БД)?",
        reply_markup=confirm_kb("do_backup"),
    )


@router.callback_query(F.data == "confirm:do_backup", AdminFilter())
async def cb_backup_create(
    call: CallbackQuery,
    session_maker: async_sessionmaker,
    is_superadmin: bool = False,
    db_user=None,
) -> None:
    await call.message.edit_text("Бэкап запущен. Уведомление придёт по завершении.")

    triggered_by = 1 if is_superadmin else db_user.telegram_id
    asyncio.create_task(
        backup_service.create_backup(
            bot=call.bot,
            session_maker=session_maker,
            triggered_by=triggered_by,
            is_scheduled=False,
        )
    )


@router.message(Command("backup_list"), AnyActiveFilter())
async def cmd_backup_list(message: Message, session_maker: async_sessionmaker) -> None:
    await _send_backup_list(message, session_maker, page=0)


@router.callback_query(F.data.startswith("backup_page:"), AnyActiveFilter())
async def cb_backup_page(call: CallbackQuery, session_maker: async_sessionmaker) -> None:
    page = int(call.data.split(":")[1])
    await _send_backup_list(call.message, session_maker, page=page, edit=True)


async def _send_backup_list(message, session_maker, page: int, edit: bool = False) -> None:
    async with session_maker() as session:
        repo = BackupRepository(session)
        backups = await repo.list_all(limit=PAGE_SIZE + 1, offset=page * PAGE_SIZE)

    has_next = len(backups) > PAGE_SIZE
    page_backups = backups[:PAGE_SIZE]

    if not page_backups:
        text = "Бэкапов пока нет."
        kb = None
    else:
        lines = []
        for b in page_backups:
            size = notification_service.fmt_size(b.size_bytes) if b.size_bytes else "—"
            warn = " ⚠️" if b.has_warnings else ""
            lines.append(
                f"#{b.id} | {b.created_at.strftime('%Y-%m-%d %H:%M')} | {b.status.value}{warn} | {size}"
            )
        text = "Список бэкапов:\n\n" + "\n".join(lines)
        kb = backup_list_kb(page_backups, page=page, page_size=PAGE_SIZE)

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("backup_view:"), AnyActiveFilter())
async def cb_backup_view(call: CallbackQuery, session_maker: async_sessionmaker) -> None:
    backup_id = int(call.data.split(":")[1])
    async with session_maker() as session:
        repo = BackupRepository(session)
        b = await repo.get_by_id(backup_id)
        if not b:
            await call.answer("Бэкап не найден.", show_alert=True)
            return

        from bot.repositories.backup_repo import RestoreRepository
        restore_repo = RestoreRepository(session)
        restores = await restore_repo.list_by_backup(backup_id)

    size = notification_service.fmt_size(b.size_bytes) if b.size_bytes else "—"
    warn = "\n⚠️ Архив создан с предупреждениями (tar код 1)." if b.has_warnings else ""
    scheduled = "плановый" if b.is_scheduled else "ручной"
    text = (
        f"Бэкап #{b.id}\n"
        f"Статус: {b.status.value}{warn}\n"
        f"Файл: <code>{b.file_name}</code>\n"
        f"Путь: <code>{b.backup_path}</code>\n"
        f"Размер: {size}\n"
        f"Тип: {scheduled}\n"
        f"Создан: {b.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Завершён: {b.completed_at.strftime('%Y-%m-%d %H:%M:%S') if b.completed_at else '—'}\n"
    )

    if restores:
        text += f"\nВосстановлений из этого бэкапа: {len(restores)}\n"
        for r in restores[:5]:
            text += f"  #{r.id} {r.created_at.strftime('%Y-%m-%d %H:%M')} — {r.status.value}\n"

    from bot.keyboards import confirm_kb
    kb = confirm_kb("backup_delete", backup_id)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("backup_count"), AnyActiveFilter())
async def cmd_backup_count(message: Message, session_maker: async_sessionmaker) -> None:
    async with session_maker() as session:
        repo = BackupRepository(session)
        count = await repo.count()
    await message.answer(f"Всего бэкапов: {count}")


@router.callback_query(F.data.startswith("confirm:backup_delete:"), AdminFilter())
async def cb_backup_delete(
    call: CallbackQuery,
    session_maker: async_sessionmaker,
) -> None:
    backup_id = int(call.data.split(":")[2])

    async with session_maker() as session:
        repo = BackupRepository(session)
        backup = await repo.get_by_id(backup_id)

        if not backup:
            await call.answer("Бэкап не найден.", show_alert=True)
            return

        backup_path = backup.backup_path
        await repo.delete(backup_id)

    if backup_path and os.path.exists(backup_path):
        os.remove(backup_path)

    await call.message.edit_text(f"Бэкап #{backup_id} удалён.")


@router.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery) -> None:
    await call.message.edit_text("Отменено.")
