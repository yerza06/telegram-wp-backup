import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.core.database import Base


class BackupStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class RestoreStatus(str, enum.Enum):
    running = "running"
    success = "success"
    rolled_back = "rolled_back"
    failed = "failed"


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[BackupStatus] = mapped_column(Enum(BackupStatus), nullable=False, default=BackupStatus.pending)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    backup_path: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    has_warnings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="SET NULL"),
        nullable=True,
    )
    is_scheduled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Restore(Base):
    __tablename__ = "restores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backup_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("backups.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[RestoreStatus] = mapped_column(Enum(RestoreStatus), nullable=False, default=RestoreStatus.running)
    triggered_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="SET NULL"),
        nullable=True,
    )
    safety_dir: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
