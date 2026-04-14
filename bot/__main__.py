import asyncio
import logging
import os
import shutil
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def validate_startup() -> None:
    from bot.core.config import settings

    # 1. WP_PATH exists and is readable
    if not os.path.isdir(settings.site.wp_path):
        sys.exit(f"[ERROR] SITE__WP_PATH не существует или не является директорией: {settings.site.wp_path}")

    # 2. BACKUP__DIR and TMP_DIR exist (create if needed) and are writable
    for path, name in [
        (settings.backup.dir, "BACKUP__DIR"),
        (settings.backup.tmp_dir, "BACKUP__TMP_DIR"),
    ]:
        os.makedirs(path, exist_ok=True)
        if not os.access(path, os.W_OK):
            sys.exit(f"[ERROR] {name} недоступен для записи: {path}")

    # 3. Check same filesystem (warning only)
    try:
        dev_wp = os.stat(settings.site.wp_path).st_dev
        dev_backup = os.stat(settings.backup.dir).st_dev
        dev_tmp = os.stat(settings.backup.tmp_dir).st_dev
        if not (dev_wp == dev_backup == dev_tmp):
            logger.warning(
                "WP_PATH, BACKUP__DIR, BACKUP__TMP_DIR находятся на разных файловых системах. "
                "mv во время restore будет деградировать в cp+rm (медленно, не атомарно)."
            )
    except Exception as e:
        logger.warning("Не удалось проверить файловые системы: %s", e)

    # 4. Check required binaries
    required_bins = ["mysql", "mysqldump", "tar", "zstd", "wp", "sudo", "chown", "df"]
    missing = [b for b in required_bins if not shutil.which(b)]
    if missing:
        sys.exit(f"[ERROR] Отсутствуют необходимые бинари: {', '.join(missing)}")

    # 5. Free space check (warning only)
    free_bytes = shutil.disk_usage(settings.backup.dir).free
    free_mb = free_bytes // (1024 * 1024)
    if free_mb < settings.backup.free_space_mb:
        logger.warning(
            "Мало свободного места: %d МБ (минимум %d МБ). Бэкап упадёт при запуске.",
            free_mb,
            settings.backup.free_space_mb,
        )

    logger.info("Валидация на старте пройдена.")


async def main() -> None:
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage

    from bot.core.config import settings
    from bot.core.database import get_engine, get_session_maker, Base
    from bot.middlewares import AuthMiddleware
    from bot.repositories.user_repo import UserRepository
    from bot.services.backup_service import orphan_recovery_backups
    from bot.services.restore_service import orphan_recovery_restores
    from bot.services.scheduler_service import load_schedules
    from bot.handlers import start, backups, disk, restore, schedules, users, cache

    validate_startup()

    # Init DB
    engine = get_engine(settings.tg.database_url)
    session_maker = get_session_maker(settings.tg.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Upsert superadmin virtual row
    async with session_maker() as session:
        repo = UserRepository(session)
        await repo.upsert_superadmin()
    logger.info("Superadmin upsert выполнен.")

    # Bot
    bot = Bot(
        token=settings.tg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Orphan recovery (before polling)
    await orphan_recovery_backups(session_maker)
    await orphan_recovery_restores(bot, session_maker)

    # Load schedules + start APScheduler
    await load_schedules(bot, session_maker)

    # Dispatcher
    dp = Dispatcher(storage=MemoryStorage())
    dp["session_maker"] = session_maker

    dp.update.middleware(AuthMiddleware(session_maker))

    dp.include_router(start.router)
    dp.include_router(backups.router)
    dp.include_router(disk.router)
    dp.include_router(restore.router)
    dp.include_router(schedules.router)
    dp.include_router(users.router)
    dp.include_router(cache.router)

    logger.info("Бот запущен.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
