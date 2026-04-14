from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def confirm_kb(action: str, item_id: int | None = None) -> InlineKeyboardMarkup:
    payload = f"{action}:{item_id}" if item_id is not None else action
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{payload}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return builder.as_markup()


def backup_list_kb(backups, page: int = 0, page_size: int = 5, action: str = "backup_view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b in backups:
        label = f"#{b.id} {b.created_at.strftime('%Y-%m-%d %H:%M')} — {b.status.value}"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"{action}:{b.id}"))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"backup_page:{page - 1}"))
    if len(backups) == page_size:
        nav.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"backup_page:{page + 1}"))
    if nav:
        builder.row(*nav)

    return builder.as_markup()


def schedule_list_kb(schedules) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in schedules:
        status_icon = "✅" if s.is_active else "⏸"
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {s.name} ({s.cron_expression})",
                callback_data=f"schedule_view:{s.id}",
            )
        )
    return builder.as_markup()


def schedule_actions_kb(schedule_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "⏸ Выключить" if is_active else "▶️ Включить"
    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data=f"schedule_toggle:{schedule_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"schedule_delete:{schedule_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ К списку", callback_data="schedule_list"))
    return builder.as_markup()


CRON_PRESETS = [
    ("Ежедневно в 02:00", "0 2 * * *"),
    ("Еженедельно (вс 02:00)", "0 2 * * 0"),
    ("Ежемесячно (1-е 02:00)", "0 2 1 * *"),
    ("Своё выражение", "custom"),
]


def cron_presets_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in CRON_PRESETS:
        builder.row(InlineKeyboardButton(text=label, callback_data=f"cron_preset:{value}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


def user_list_kb(users) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for u in users:
        if u.telegram_id == 1:
            continue
        status = "✅" if u.is_active else "🚫"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {u.fullname or u.username or str(u.telegram_id)} [{u.role.value}]",
                callback_data=f"user_view:{u.telegram_id}",
            )
        )
    return builder.as_markup()


def user_actions_kb(telegram_id: int, is_active: bool, role: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.row(InlineKeyboardButton(text="🚫 Деактивировать", callback_data=f"user_deactivate:{telegram_id}"))
    else:
        builder.row(InlineKeyboardButton(text="✅ Активировать", callback_data=f"user_activate:{telegram_id}"))

    new_role = "viewer" if role == "admin" else "admin"
    role_label = "Сменить на viewer" if role == "admin" else "Сменить на admin"
    builder.row(InlineKeyboardButton(text=f"🔄 {role_label}", callback_data=f"user_role:{telegram_id}:{new_role}"))
    builder.row(InlineKeyboardButton(text="◀️ К списку", callback_data="user_list"))
    return builder.as_markup()
