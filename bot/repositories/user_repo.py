from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        username: str | None,
        fullname: str | None,
        role: UserRole = UserRole.viewer,
        is_active: bool = False,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            username=username,
            fullname=fullname,
            role=role,
            is_active=is_active,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def list_all(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.created_at))
        return list(result.scalars().all())

    async def list_active(self) -> list[User]:
        result = await self.session.execute(
            select(User).where(User.is_active == True).order_by(User.created_at)  # noqa: E712
        )
        return list(result.scalars().all())

    async def activate(self, telegram_id: int) -> None:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.is_active = True
            await self.session.commit()

    async def deactivate(self, telegram_id: int) -> None:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.is_active = False
            await self.session.commit()

    async def set_role(self, telegram_id: int, role: UserRole) -> None:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.role = role
            await self.session.commit()

    async def upsert_superadmin(self) -> None:
        stmt = (
            insert(User)
            .values(
                telegram_id=1,
                username="superadmin",
                fullname="superadmin",
                role=UserRole.admin,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=["telegram_id"],
                set_={
                    "username": "superadmin",
                    "fullname": "superadmin",
                    "role": UserRole.admin,
                    "is_active": True,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()
