import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.repositories.schedule_repo import ScheduleRepository

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_bot: Bot | None = None
_session_maker: async_sessionmaker | None = None


def _make_job_id(schedule_id: int) -> str:
    return f"schedule_{schedule_id}"


async def _scheduled_backup(schedule_id: int) -> None:
    from bot.services import backup_service
    from bot.services import notification_service
    await notification_service.notify_all(_bot, _session_maker, "⏰ Запущен плановый бэкап.")
    await backup_service.create_backup(
        bot=_bot,
        session_maker=_session_maker,
        triggered_by=None,
        is_scheduled=True,
    )


def _add_job(schedule_id: int, cron_expression: str) -> None:
    scheduler.add_job(
        _scheduled_backup,
        CronTrigger.from_crontab(cron_expression),
        id=_make_job_id(schedule_id),
        kwargs={"schedule_id": schedule_id},
        replace_existing=True,
    )


async def load_schedules(bot: Bot, session_maker: async_sessionmaker) -> None:
    global _bot, _session_maker
    _bot = bot
    _session_maker = session_maker

    async with session_maker() as session:
        repo = ScheduleRepository(session)
        active = await repo.list_active()

    for sched in active:
        try:
            _add_job(sched.id, sched.cron_expression)
            logger.info("Loaded schedule #%s: %s (%s)", sched.id, sched.name, sched.cron_expression)
        except Exception as e:
            logger.error("Failed to load schedule #%s: %s", sched.id, e)

    scheduler.start()


async def add_schedule(
    session_maker: async_sessionmaker,
    name: str,
    cron_expression: str,
    description: str | None = None,
) -> int:
    async with session_maker() as session:
        repo = ScheduleRepository(session)
        sched = await repo.create(name=name, cron_expression=cron_expression, description=description)
        schedule_id = sched.id

    _add_job(schedule_id, cron_expression)
    return schedule_id


async def remove_schedule(session_maker: async_sessionmaker, schedule_id: int) -> None:
    async with session_maker() as session:
        repo = ScheduleRepository(session)
        await repo.delete(schedule_id)

    job_id = _make_job_id(schedule_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def toggle_schedule(
    session_maker: async_sessionmaker,
    schedule_id: int,
    is_active: bool,
) -> None:
    async with session_maker() as session:
        repo = ScheduleRepository(session)
        await repo.toggle(schedule_id, is_active)

    job_id = _make_job_id(schedule_id)
    job = scheduler.get_job(job_id)
    if is_active:
        async with session_maker() as session:
            repo = ScheduleRepository(session)
            sched = await repo.get_by_id(schedule_id)
        if sched:
            _add_job(schedule_id, sched.cron_expression)
    else:
        if job:
            scheduler.remove_job(job_id)
