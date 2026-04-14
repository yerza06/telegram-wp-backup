from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.filters import AdminFilter
from bot.keyboards import confirm_kb
from bot.services.cache_service import flush_cache

router = Router()


@router.message(Command("cache"), AdminFilter())
async def cmd_cache(message: Message) -> None:
    await message.answer(
        "Очистить кэш WordPress?",
        reply_markup=confirm_kb("do_cache_flush"),
    )


@router.callback_query(F.data == "confirm:do_cache_flush", AdminFilter())
async def cb_cache_flush(call: CallbackQuery) -> None:
    await call.message.edit_text("Очищаю кэш...")
    try:
        output = await flush_cache()
        await call.message.edit_text(f"✅ Кэш WordPress очищен.\n<pre>{output}</pre>", parse_mode="HTML")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка: {e}")
