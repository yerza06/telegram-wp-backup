from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.schedule import Schedule


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        name: str,
        cron_expression: str,
        description: str | None = None,
        is_active: bool = True,
    ) -> Schedule:
        schedule = Schedule(
            name=name,
            description=description,
            cron_expression=cron_expression,
            is_active=is_active,
        )
        self.session.add(schedule)
        await self.session.commit()
        await self.session.refresh(schedule)
        return schedule

    async def get_by_id(self, schedule_id: int) -> Schedule | None:
        result = await self.session.execute(
            select(Schedule).where(Schedule.id == schedule_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Schedule]:
        result = await self.session.execute(select(Schedule).order_by(Schedule.created_at))
        return list(result.scalars().all())

    async def list_active(self) -> list[Schedule]:
        result = await self.session.execute(
            select(Schedule).where(Schedule.is_active == True).order_by(Schedule.created_at)  # noqa: E712
        )
        return list(result.scalars().all())

    async def toggle(self, schedule_id: int, is_active: bool) -> None:
        schedule = await self.get_by_id(schedule_id)
        if schedule:
            schedule.is_active = is_active
            await self.session.commit()

    async def delete(self, schedule_id: int) -> None:
        schedule = await self.get_by_id(schedule_id)
        if schedule:
            await self.session.delete(schedule)
            await self.session.commit()
