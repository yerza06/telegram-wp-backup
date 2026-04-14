from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from bot.models.user import UserRole


class RoleFilter(BaseFilter):
    """Passes if user has one of the specified roles (or is superadmin)."""

    def __init__(self, *roles: UserRole) -> None:
        self.roles = set(roles)

    async def __call__(self, event: TelegramObject, is_superadmin: bool = False, db_user=None) -> bool:
        if is_superadmin:
            return True
        if db_user is None:
            return False
        return db_user.role in self.roles


class AdminFilter(RoleFilter):
    def __init__(self) -> None:
        super().__init__(UserRole.admin)


class AnyActiveFilter(BaseFilter):
    """Passes for any active user (viewer, admin) or superadmin."""

    async def __call__(self, event: TelegramObject, is_superadmin: bool = False, db_user=None) -> bool:
        if is_superadmin:
            return True
        return db_user is not None and db_user.is_active
