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
from bot.models.backup import RestoreStatus
from bot.repositories.backup_repo import BackupRepository, RestoreRepository
from bot.services import notification_service
from bot.services.backup_service import operation_lock, _get_running_info

logger = logging.getLogger(__name__)


async def run_restore(
    bot: Bot,
    session_maker: async_sessionmaker,
    backup_id: int,
    triggered_by: int | None,
) -> None:
    if operation_lock.locked():
        running_info = await _get_running_info(session_maker)
        msg = f"Уже выполняется операция: {running_info or 'неизвестная'}. Попробуйте позже."
        if triggered_by:
            await bot.send_message(triggered_by, msg)
        return

    async with operation_lock:
        running_info = await _get_running_info(session_maker)
        if running_info:
            msg = f"Уже выполняется операция: {running_info}. Попробуйте позже."
            if triggered_by:
                await bot.send_message(triggered_by, msg)
            return

        async with session_maker() as session:
            restore_repo = RestoreRepository(session)
            restore = await restore_repo.create(backup_id=backup_id, triggered_by=triggered_by)
            restore_id = restore.id

            backup_repo = BackupRepository(session)
            backup = await backup_repo.get_by_id(backup_id)
            backup_path = backup.backup_path if backup else None

        await _run_restore(bot, session_maker, restore_id, backup_path)


async def _run_restore(
    bot: Bot,
    session_maker: async_sessionmaker,
    restore_id: int,
    backup_path: str,
) -> None:
    site_name = settings.site.name
    wp_path = settings.site.wp_path
    wp_snapshot = f"{wp_path}.old-{restore_id}"

    safety_dir = None
    tmp_dir = None

    try:
        # Step 1: Snapshot DB
        safety_dir = tempfile.mkdtemp(
            prefix=f"wp-rollback-{site_name}-",
            dir=settings.backup.tmp_dir,
        )
        async with session_maker() as session:
            restore_repo = RestoreRepository(session)
            await restore_repo.update(restore_id, safety_dir=safety_dir)

        db_snapshot = os.path.join(safety_dir, "db_current.sql")
        dump_proc = await asyncio.create_subprocess_exec(
            "mysqldump",
            "--single-transaction",
            "--quick",
            f"-u{settings.site.db_user}",
            settings.site.db_name,
            stdout=open(db_snapshot, "wb"),
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "MYSQL_PWD": settings.site.db_pass},
        )
        _, dump_stderr = await dump_proc.communicate()
        if dump_proc.returncode != 0:
            raise RuntimeError(f"mysqldump (snapshot) failed: {dump_stderr.decode()}")

        # Step 2: Unpack archive to tmp
        tmp_dir = tempfile.mkdtemp(
            prefix=f"wp-restore-{site_name}-",
            dir=settings.backup.tmp_dir,
        )
        tar_proc = await asyncio.create_subprocess_exec(
            "tar", "--zstd", "-xf", backup_path, "-C", tmp_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, tar_stderr = await tar_proc.communicate()
        if tar_proc.returncode != 0:
            raise RuntimeError(f"tar extract failed: {tar_stderr.decode()}")

        # Step 3: Maintenance mode ON
        await _wp_maintenance(on=True)

        # Step 4: Atomic file swap
        wp_basename = os.path.basename(wp_path)
        new_wp = os.path.join(tmp_dir, wp_basename)

        if not os.path.exists(new_wp):
            # Try first subdirectory as wp dir
            subdirs = [d for d in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, d)) and d != "database"]
            if subdirs:
                new_wp = os.path.join(tmp_dir, subdirs[0])
            else:
                raise RuntimeError(f"Не найдена директория WordPress в архиве ({tmp_dir})")

        os.rename(wp_path, wp_snapshot)
        os.rename(new_wp, wp_path)

        # Step 5: chown
        chown_proc = await asyncio.create_subprocess_exec(
            "chown", "-R", "www-data:www-data", wp_path,
            stderr=asyncio.subprocess.PIPE,
        )
        _, chown_err = await chown_proc.communicate()
        if chown_proc.returncode != 0:
            raise RuntimeError(f"chown failed: {chown_err.decode()}")

        # Step 6: Restore DB
        db_dump = os.path.join(tmp_dir, "database", "db.sql")
        mysql_proc = await asyncio.create_subprocess_exec(
            "mysql",
            f"-u{settings.site.db_user}",
            settings.site.db_name,
            stdin=open(db_dump, "rb"),
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "MYSQL_PWD": settings.site.db_pass},
        )
        _, mysql_err = await mysql_proc.communicate()
        if mysql_proc.returncode != 0:
            raise RuntimeError(f"mysql restore failed: {mysql_err.decode()}")

        # Step 7: Maintenance mode OFF
        await _wp_maintenance(on=False)

        # Success cleanup
        if os.path.exists(wp_snapshot):
            shutil.rmtree(wp_snapshot, ignore_errors=True)
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        if safety_dir:
            shutil.rmtree(safety_dir, ignore_errors=True)

        async with session_maker() as session:
            restore_repo = RestoreRepository(session)
            await restore_repo.update(
                restore_id,
                status=RestoreStatus.success,
                safety_dir=None,
                completed_at=datetime.now(tz=timezone.utc),
            )

        await notification_service.notify_all(
            bot, session_maker,
            f"✅ Восстановление #{restore_id} успешно завершено."
        )

    except Exception as e:
        logger.error("Restore #%s failed: %s", restore_id, e)
        rolled_back = await _rollback(wp_path, wp_snapshot, safety_dir, tmp_dir)

        if rolled_back:
            status = RestoreStatus.rolled_back
            msg = (
                f"⚠️ Восстановление #{restore_id} не удалось — выполнен откат к предыдущему состоянию.\n"
                f"Причина: <code>{e}</code>"
            )
        else:
            status = RestoreStatus.failed
            msg = (
                f"❌ Критическая ошибка восстановления #{restore_id} — откат также не удался.\n"
                f"Причина: <code>{e}</code>\n\n"
                f"Требуется ручная проверка:\n"
                f"  Текущее состояние: <code>{wp_path}</code>\n"
                f"  Снапшот БД: <code>{safety_dir}/db_current.sql</code>\n"
                f"  Снапшот файлов: <code>{wp_snapshot}</code> (если существует)"
            )

        async with session_maker() as session:
            restore_repo = RestoreRepository(session)
            await restore_repo.update(
                restore_id,
                status=status,
                error_message=str(e),
                completed_at=datetime.now(tz=timezone.utc),
            )

        await notification_service.notify_all(bot, session_maker, msg)


async def _rollback(
    wp_path: str,
    wp_snapshot: str,
    safety_dir: str | None,
    tmp_dir: str | None,
) -> bool:
    """Returns True if rollback succeeded, False if it also failed."""
    try:
        # Try maintenance off first (best effort)
        try:
            await _wp_maintenance(on=False)
        except Exception:
            pass

        # Remove new (possibly partial) wp files
        if os.path.exists(wp_path):
            shutil.rmtree(wp_path, ignore_errors=True)

        # Restore old files
        if os.path.exists(wp_snapshot):
            os.rename(wp_snapshot, wp_path)

        # Restore DB from safety snapshot
        if safety_dir:
            db_snapshot = os.path.join(safety_dir, "db_current.sql")
            if os.path.exists(db_snapshot):
                mysql_proc = await asyncio.create_subprocess_exec(
                    "mysql",
                    f"-u{settings.site.db_user}",
                    settings.site.db_name,
                    stdin=open(db_snapshot, "rb"),
                    stderr=asyncio.subprocess.PIPE,
                    env={**os.environ, "MYSQL_PWD": settings.site.db_pass},
                )
                await mysql_proc.communicate()

        # Cleanup
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        if safety_dir and os.path.exists(safety_dir):
            shutil.rmtree(safety_dir, ignore_errors=True)

        return True

    except Exception as rb_err:
        logger.critical("Rollback also failed: %s", rb_err)
        return False


async def _wp_maintenance(on: bool) -> None:
    import shutil as _shutil
    if not _shutil.which("wp"):
        raise RuntimeError(
            "WP-CLI не найден. Установите по инструкции: https://wp-cli.org/\n"
            "Восстановление без WP-CLI невозможно."
        )

    action = "activate" if on else "deactivate"
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-u", "www-data",
        "wp", "maintenance-mode", action,
        f"--path={settings.site.wp_path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"wp maintenance-mode {action} failed: {stderr.decode()}")


async def orphan_recovery_restores(
    bot: Bot,
    session_maker: async_sessionmaker,
) -> None:
    """Called at startup. Handles interrupted restore operations."""
    async with session_maker() as session:
        restore_repo = RestoreRepository(session)
        running = await restore_repo.list_running()

    for restore in running:
        site_name = settings.site.name

        # Remove only tmp extract dir (safe to delete — archive is intact)
        pattern = os.path.join(
            settings.backup.tmp_dir,
            f"wp-restore-{site_name}-*",
        )
        for path in glob.glob(pattern):
            shutil.rmtree(path, ignore_errors=True)

        # DO NOT touch safety_dir or WP_PATH.old-<id>

        async with session_maker() as session:
            restore_repo = RestoreRepository(session)
            await restore_repo.update(
                restore.id,
                status=RestoreStatus.failed,
                error_message="process crashed or interrupted (recovered at startup). Manual inspection required.",
                completed_at=datetime.now(tz=timezone.utc),
            )

        wp_snapshot = f"{settings.site.wp_path}.old-{restore.id}"
        msg = (
            f"🚨 Бот пережил краш во время восстановления #{restore.id}.\n"
            f"Состояние сайта: непредсказуемо.\n\n"
            f"Проверьте вручную:\n"
            f"  Текущее состояние: <code>{settings.site.wp_path}</code>\n"
            f"  Снапшот БД: <code>{restore.safety_dir}/db_current.sql</code>\n"
            f"  Снапшот файлов: <code>{wp_snapshot}</code> (если существует)\n\n"
            f"Если сайт работает корректно — удалите оба артефакта вручную.\n"
            f"Если сайт сломан:\n"
            f"  <code>mysql {settings.site.db_name} &lt; {restore.safety_dir}/db_current.sql</code>\n"
            f"  <code>mv {wp_snapshot} {settings.site.wp_path}</code>"
        )
        await notification_service.notify_all(bot, session_maker, msg)
        logger.critical("Orphan restore #%s detected. Manual inspection required.", restore.id)
