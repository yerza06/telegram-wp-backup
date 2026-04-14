from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.backup import Backup, BackupStatus, Restore, RestoreStatus


class BackupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, triggered_by: int | None, is_scheduled: bool) -> Backup:
        backup = Backup(
            status=BackupStatus.pending,
            triggered_by=triggered_by,
            is_scheduled=is_scheduled,
        )
        self.session.add(backup)
        await self.session.commit()
        await self.session.refresh(backup)
        return backup

    async def update(self, backup_id: int, **fields) -> None:
        backup = await self.get_by_id(backup_id)
        if backup:
            for key, value in fields.items():
                setattr(backup, key, value)
            await self.session.commit()

    async def get_by_id(self, backup_id: int) -> Backup | None:
        result = await self.session.execute(
            select(Backup).where(Backup.id == backup_id)
        )
        return result.scalar_one_or_none()

    async def get_running(self) -> Backup | None:
        result = await self.session.execute(
            select(Backup).where(Backup.status == BackupStatus.running)
        )
        return result.scalar_one_or_none()

    async def list_running(self) -> list[Backup]:
        result = await self.session.execute(
            select(Backup).where(Backup.status == BackupStatus.running)
        )
        return list(result.scalars().all())

    async def list_all(self, limit: int = 20, offset: int = 0) -> list[Backup]:
        result = await self.session.execute(
            select(Backup).order_by(Backup.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_successful(self) -> list[Backup]:
        result = await self.session.execute(
            select(Backup)
            .where(Backup.status == BackupStatus.success)
            .order_by(Backup.created_at.desc())
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(select(func.count()).select_from(Backup))
        return result.scalar_one()

    async def delete(self, backup_id: int) -> None:
        backup = await self.get_by_id(backup_id)
        if backup:
            await self.session.delete(backup)
            await self.session.commit()


class RestoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, backup_id: int | None, triggered_by: int | None) -> Restore:
        restore = Restore(
            backup_id=backup_id,
            status=RestoreStatus.running,
            triggered_by=triggered_by,
        )
        self.session.add(restore)
        await self.session.commit()
        await self.session.refresh(restore)
        return restore

    async def update(self, restore_id: int, **fields) -> None:
        restore = await self.get_by_id(restore_id)
        if restore:
            for key, value in fields.items():
                setattr(restore, key, value)
            await self.session.commit()

    async def get_by_id(self, restore_id: int) -> Restore | None:
        result = await self.session.execute(
            select(Restore).where(Restore.id == restore_id)
        )
        return result.scalar_one_or_none()

    async def get_running(self) -> Restore | None:
        result = await self.session.execute(
            select(Restore).where(Restore.status == RestoreStatus.running)
        )
        return result.scalar_one_or_none()

    async def list_running(self) -> list[Restore]:
        result = await self.session.execute(
            select(Restore).where(Restore.status == RestoreStatus.running)
        )
        return list(result.scalars().all())

    async def list_all(self, limit: int = 20, offset: int = 0) -> list[Restore]:
        result = await self.session.execute(
            select(Restore).order_by(Restore.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_backup(self, backup_id: int) -> list[Restore]:
        result = await self.session.execute(
            select(Restore)
            .where(Restore.backup_id == backup_id)
            .order_by(Restore.created_at.desc())
        )
        return list(result.scalars().all())
