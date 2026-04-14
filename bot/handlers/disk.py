from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.filters import AnyActiveFilter
from bot.services.disk_service import get_disk_usage

router = Router()


@router.message(Command("disk"), AnyActiveFilter())
async def cmd_disk(message: Message) -> None:
    try:
        output = await get_disk_usage()
        await message.answer(f"<pre>{output}</pre>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
