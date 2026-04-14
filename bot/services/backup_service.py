import asyncio
import glob
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.core.config import settings
from bot.models.backup import BackupStatus
from bot.repositories.backup_repo import BackupRepository
from bot.services import notification_service
from bot.services.disk_service import check_free_space

logger = logging.getLogger(__name__)

# Global in-memory lock for concurrent backup/restore prevention
operation_lock = asyncio.Lock()


async def _get_running_info(session_maker: async_sessionmaker) -> str | None:
    """Return description of running operation if any, else None."""
    async with session_maker() as session:
        repo = BackupRepository(session)
        running_backup = await repo.get_running()
        if running_backup:
            return f"бэкап #{running_backup.id}, запущен {running_backup.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

        from bot.repositories.backup_repo import RestoreRepository
        restore_repo = RestoreRepository(session)
        running_restore = await restore_repo.get_running()
        if running_restore:
            return f"восстановление #{running_restore.id}, запущено {running_restore.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    return None


async def create_backup(
    bot: Bot,
    session_maker: async_sessionmaker,
    triggered_by: int | None,
    is_scheduled: bool = False,
) -> None:
    if operation_lock.locked():
        running_info = await _get_running_info(session_maker)
        msg = f"Уже выполняется операция: {running_info or 'неизвестная'}. Попробуйте позже."
        if triggered_by:
            await bot.send_message(triggered_by, msg)
        return

    async with operation_lock:
        # Double-check via DB
        running_info = await _get_running_info(session_maker)
        if running_info:
            msg = f"Уже выполняется операция: {running_info}. Попробуйте позже."
            if triggered_by:
                await bot.send_message(triggered_by, msg)
            return

        # Check free space
        if not check_free_space(settings.backup.dir, settings.backup.free_space_mb):
            from bot.services.disk_service import free_space_mb
            free = free_space_mb(settings.backup.dir)
            msg = (
                f"⚠️ Недостаточно свободного места для бэкапа.\n"
                f"Доступно: {free} МБ, требуется: {settings.backup.free_space_mb} МБ."
            )
            await notification_service.notify_all(bot, session_maker, msg)
            return

        # Create DB record
        async with session_maker() as session:
            repo = BackupRepository(session)
            backup = await repo.create(triggered_by=triggered_by, is_scheduled=is_scheduled)
            backup_id = backup.id

        await _run_backup(bot, session_maker, backup_id, triggered_by, is_scheduled)


async def _run_backup(
    bot: Bot,
    session_maker: async_sessionmaker,
    backup_id: int,
    triggered_by: int | None,
    is_scheduled: bool,
) -> None:
    async with session_maker() as session:
        repo = BackupRepository(session)
        await repo.update(backup_id, status=BackupStatus.running)

    tmp_dir = None
    backup_path = None

    try:
        site_name = settings.site.name
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        archive_name = f"wp-{site_name}-backup_{timestamp}.tar.zst"

        dest_dir = os.path.join(settings.backup.dir, site_name)
        os.makedirs(dest_dir, exist_ok=True)

        backup_path = os.path.join(dest_dir, archive_name)

        # Create temp dir for db dump
        tmp_dir = tempfile.mkdtemp(prefix=f"wp-backup-{site_name}-", dir=settings.backup.tmp_dir)
        db_dir = os.path.join(tmp_dir, "database")
        os.mkdir(db_dir)
        dump_path = os.path.join(db_dir, "db.sql")

        # Update record with backup_path + file_name
        async with session_maker() as session:
            repo = BackupRepository(session)
            await repo.update(backup_id, backup_path=backup_path, file_name=archive_name)

        # mysqldump
        dump_proc = await asyncio.create_subprocess_exec(
            "mysqldump",
            "--single-transaction",
            "--quick",
            f"-u{settings.site.db_user}",
            settings.site.db_name,
            stdout=open(dump_path, "wb"),
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "MYSQL_PWD": settings.site.db_pass},
        )
        _, dump_stderr = await dump_proc.communicate()
        if dump_proc.returncode != 0:
            raise RuntimeError(f"mysqldump failed: {dump_stderr.decode()}")

        # tar
        wp_parent = os.path.dirname(settings.site.wp_path)
        wp_basename = os.path.basename(settings.site.wp_path)

        tar_proc = await asyncio.create_subprocess_exec(
            "tar",
            "--zstd",
            "--ignore-failed-read",
            "-cf", backup_path,
            "-C", tmp_dir, "database",
            "-C", wp_parent, wp_basename,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, tar_stderr = await tar_proc.communicate()
        tar_rc = tar_proc.returncode

        if tar_rc == 0:
            has_warnings = False
            status = BackupStatus.success
        elif tar_rc == 1:
            has_warnings = True
            status = BackupStatus.success
            logger.warning("tar returned code 1 (warnings): %s", tar_stderr.decode())
        else:
            raise RuntimeError(f"tar failed (code {tar_rc}): {tar_stderr.decode()}")

        size_bytes = os.path.getsize(backup_path)

        async with session_maker() as session:
            repo = BackupRepository(session)
            await repo.update(
                backup_id,
                status=status,
                has_warnings=has_warnings,
                size_bytes=size_bytes,
                completed_at=datetime.now(tz=timezone.utc),
            )

        size_str = notification_service.fmt_size(size_bytes)
        msg = (
            f"{'⚠️' if has_warnings else '✅'} Бэкап {'завершён с предупреждениями' if has_warnings else 'успешно создан'}.\n"
            f"Размер: {size_str}\n"
            f"Путь: <code>{backup_path}</code>\n"
            f"Время: {timestamp}"
        )
        if has_warnings:
            msg += "\n\n<i>Часть файлов изменялась во время архивации (tar код 1). Архив валиден.</i>"

        await notification_service.notify_all(bot, session_maker, msg)

    except Exception as e:
        logger.error("Backup %s failed: %s", backup_id, e)
        if backup_path and os.path.exists(backup_path):
            os.remove(backup_path)
        async with session_maker() as session:
            repo = BackupRepository(session)
            await repo.update(
                backup_id,
                status=BackupStatus.failed,
                error_message=str(e),
                completed_at=datetime.now(tz=timezone.utc),
            )
        await notification_service.notify_all(
            bot, session_maker,
            f"❌ Ошибка бэкапа #{backup_id}:\n<code>{e}</code>"
        )

    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def orphan_recovery_backups(session_maker: async_sessionmaker) -> None:
    """Called at startup before polling. Cleans up interrupted backup operations."""
    async with session_maker() as session:
        repo = BackupRepository(session)
        running = await repo.list_running()

    for backup in running:
        # Remove tmp dirs
        pattern = os.path.join(
            settings.backup.tmp_dir,
            f"wp-backup-{settings.site.name}-*",
        )
        for path in glob.glob(pattern):
            shutil.rmtree(path, ignore_errors=True)

        # Remove partial archive
        if backup.backup_path and os.path.exists(backup.backup_path):
            os.remove(backup.backup_path)
            logger.info("Removed orphan backup archive: %s", backup.backup_path)

        async with session_maker() as session:
            repo = BackupRepository(session)
            await repo.update(
                backup.id,
                status=BackupStatus.failed,
                error_message="process crashed or interrupted (recovered at startup)",
                completed_at=datetime.now(tz=timezone.utc),
            )
        logger.info("Marked orphan backup #%s as failed", backup.id)
