# bot.py
import json
import logging
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from config import TOKEN
from handlers.utils import ensure_json_files_exist

# Aiogram импортлари
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

# Хандлерлар
from handlers.start import router as start_router
from handlers.admin import router as admin_router
from handlers.common_order import router as common_order_router
from handlers.edit_order import router as edit_order_router
from handlers.driver_order import router as driver_order_router
from handlers.driver_info import router as driver_info_router

# Лог файлни ёзиш конфигурацияси
logging.basicConfig(level=logging.INFO)
print("🔄 Бот ишга туширилмоқда...")

# Керакли .json файллар мавжудлигини текшириш ёки яратиш
ensure_json_files_exist()

# Ботни ва диспетчерни яратиш
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хандлерни диспетчерга улаш
dp.include_router(start_router)
dp.include_router(admin_router)
dp.include_router(common_order_router)
dp.include_router(edit_order_router)
dp.include_router(driver_order_router)
dp.include_router(driver_info_router)

async def main():
    logging.info("🤖 Бот ишга тушди!")
    try:
        me = await bot.get_me()
        print(f"Бот маълумотлари: @{me.username}")
    except Exception as e:
        print(f"❌ Ботни текширишда хатолик: {e}")
    await dp.start_polling(bot)  # start_polling'ni ishlatish

if __name__ == "__main__":
    asyncio.run(main())  # asyncio yordamida main funksiyasini ishga tushurish
