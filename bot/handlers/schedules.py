from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.filters import AdminFilter, AnyActiveFilter
from bot.keyboards import cron_presets_kb, schedule_actions_kb, schedule_list_kb
from bot.repositories.schedule_repo import ScheduleRepository
from bot.services import scheduler_service

router = Router()


class AddScheduleStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_cron = State()
    waiting_for_description = State()


@router.message(Command("schedule"), AnyActiveFilter())
async def cmd_schedule_list(message: Message, session_maker: async_sessionmaker) -> None:
    async with session_maker() as session:
        repo = ScheduleRepository(session)
        schedules = await repo.list_all()

    if not schedules:
        await message.answer("Расписаний нет. /schedule_add — добавить.")
        return

    await message.answer("Расписания:", reply_markup=schedule_list_kb(schedules))


@router.callback_query(F.data == "schedule_list", AnyActiveFilter())
async def cb_schedule_list(call: CallbackQuery, session_maker: async_sessionmaker) -> None:
    async with session_maker() as session:
        repo = ScheduleRepository(session)
        schedules = await repo.list_all()

    await call.message.edit_text("Расписания:", reply_markup=schedule_list_kb(schedules))


@router.callback_query(F.data.startswith("schedule_view:"), AnyActiveFilter())
async def cb_schedule_view(call: CallbackQuery, session_maker: async_sessionmaker) -> None:
    schedule_id = int(call.data.split(":")[1])
    async with session_maker() as session:
        repo = ScheduleRepository(session)
        s = await repo.get_by_id(schedule_id)

    if not s:
        await call.answer("Расписание не найдено.", show_alert=True)
        return

    status = "активно" if s.is_active else "выключено"
    text = (
        f"Расписание #{s.id}: {s.name}\n"
        f"Cron: <code>{s.cron_expression}</code>\n"
        f"Статус: {status}\n"
    )
    if s.description:
        text += f"Описание: {s.description}\n"

    await call.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=schedule_actions_kb(schedule_id, s.is_active),
    )


@router.message(Command("schedule_add"), AdminFilter())
async def cmd_schedule_add(message: Message, state: FSMContext) -> None:
    await message.answer("Введите название расписания:")
    await state.set_state(AddScheduleStates.waiting_for_name)


@router.message(AddScheduleStates.waiting_for_name)
async def fsm_schedule_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await message.answer("Выберите интервал:", reply_markup=cron_presets_kb())
    await state.set_state(AddScheduleStates.waiting_for_cron)


@router.callback_query(F.data.startswith("cron_preset:"), AddScheduleStates.waiting_for_cron)
async def cb_cron_preset(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "custom":
        await call.message.edit_text("Введите cron-выражение (например: <code>0 3 * * *</code>):", parse_mode="HTML")
    else:
        await state.update_data(cron_expression=value)
        await call.message.edit_text("Добавьте описание (или отправьте /skip):")
        await state.set_state(AddScheduleStates.waiting_for_description)


@router.message(AddScheduleStates.waiting_for_cron)
async def fsm_schedule_cron(message: Message, state: FSMContext) -> None:
    cron = message.text.strip()
    # Basic validation
    parts = cron.split()
    if len(parts) != 5:
        await message.answer("Неверный формат. Введите 5-компонентное cron-выражение (например: 0 2 * * *):")
        return
    await state.update_data(cron_expression=cron)
    await message.answer("Добавьте описание (или отправьте /skip):")
    await state.set_state(AddScheduleStates.waiting_for_description)


@router.message(AddScheduleStates.waiting_for_description)
async def fsm_schedule_description(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker,
) -> None:
    data = await state.get_data()
    description = None if message.text.strip() in ("/skip", "-") else message.text.strip()

    schedule_id = await scheduler_service.add_schedule(
        session_maker=session_maker,
        name=data["name"],
        cron_expression=data["cron_expression"],
        description=description,
    )
    await state.clear()
    await message.answer(
        f"Расписание #{schedule_id} добавлено: {data['name']} ({data['cron_expression']})"
    )


@router.callback_query(F.data.startswith("schedule_toggle:"), AdminFilter())
async def cb_schedule_toggle(call: CallbackQuery, session_maker: async_sessionmaker) -> None:
    schedule_id = int(call.data.split(":")[1])

    async with session_maker() as session:
        repo = ScheduleRepository(session)
        s = await repo.get_by_id(schedule_id)

    if not s:
        await call.answer("Расписание не найдено.", show_alert=True)
        return

    new_state = not s.is_active
    await scheduler_service.toggle_schedule(session_maker, schedule_id, new_state)
    status = "включено" if new_state else "выключено"
    await call.answer(f"Расписание {status}.")
    await cb_schedule_view(call, session_maker)


@router.callback_query(F.data.startswith("schedule_delete:"), AdminFilter())
async def cb_schedule_delete(call: CallbackQuery, session_maker: async_sessionmaker) -> None:
    schedule_id = int(call.data.split(":")[1])
    await scheduler_service.remove_schedule(session_maker, schedule_id)
    await call.answer("Расписание удалено.")
    await cb_schedule_list(call, session_maker)
