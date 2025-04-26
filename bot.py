# bot.py
import json
import logging
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from config import TOKEN

try:
    # Барча керакли хандлерлар импорт қилинади
    from aiogram import Bot, Dispatcher
    from aiogram.types import Message
    from aiogram.fsm.context import FSMContext
    from handlers.start import router as start_router
    from handlers.admin import router as admin_router
    from handlers.common_order import router as common_order_router
    from handlers.edit_order import router as edit_order_router
    from handlers.driver_order import router as driver_order_router
    from handlers.driver_info import router as driver_info_router
    print("✅ Барча хандлерлар импорт қилинди")
except Exception as e:
    print(f"❌ Хандлер импорт қилишда хатолик: {e}")

# Логларни ёзиш 
logging.basicConfig(level=logging.INFO)
print("🔄 Бот ишга туширилмоқда...")

# Файлга маълумот ёзиш
def create_empty_user_status_file():
    users = {}
    file_path = os.path.join(os.path.dirname(__file__), "user_statuses.json")
    logging.info(f"Файл яратиш: {file_path}")
    try:
        with open(file_path, "w") as file:
            json.dump(users, file)
        logging.info(f"Файл яратилди: {file_path}")
    except Exception as e:
        logging.error(f"Файл яратишда хатолик: {str(e)}")

# Агар файл мавжуд бўлмаса, янгидан яратиш
file_path = os.path.join(os.path.dirname(__file__), "user_statuses.json")
try:
    with open(file_path, "r") as file:
        logging.info(f"Файл топилди: {file_path}")
except FileNotFoundError:
    logging.error(f"Файл топилмади, янгидан яратиш керак: {file_path}")
    create_empty_user_status_file()

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
