# handlers/driver_info.py
import os
import json
from aiogram import Bot, Router, types, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from states import DriverInfo
#from start import notify_admins_about_new_driver
from utils import save_driver, load_drivers, send_or_edit_text, USER_STATUS_PATH, DRIVER_PATH
from keyboards.start_kb import start_kb
#from config import TOKEN
TOKEN = os.getenv("TOKEN")
ADMINS = os.getenv("ADMINS")
if ADMINS:
    ADMINS = {int(i) for i in ADMINS.split(",")}
else:
    ADMINS = set()

import logging

bot = Bot(token=TOKEN)
router = Router()

@router.callback_query(F.data == "is_driver_approved_check")
async def check_driver_info_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    drivers = load_drivers()
    driver = drivers.get(user_id)

    # 🔎 Агар ҳайдовчи маълумот топширмаган бўлса
    if not driver or not driver.get("driver_data") and not driver.get("profile"):
        await callback.message.answer("❗️Сиз ҳали маълумот киритмадингиз. Илтимос, аввал исмингизни киритинг.")
        await state.set_state(DriverInfo.name)
        return

    # 🔄 Агар маълумот бор, лекин ҳали тасдиқланмаган бўлса
    await callback.message.answer("⏳ Ҳозирда сизнинг маълумотларингиз админ томонидан кўриб чиқиляпти. Илтимос кутиб туринг.")
    await state.clear()

@router.callback_query(F.data == "haydovchi")
async def start_driver_info_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Илтимос, исмингизни киритинг:")
    await state.set_state(DriverInfo.name)

@router.message(Command("haydovchi"))
async def start_driver_info(message: types.Message, state: FSMContext):
    await message.answer("Илтимос, исмингизни киритинг:")
    await state.set_state(DriverInfo.name)

@router.message(DriverInfo.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Телефон рақамингизни тўлиқ киритинг (масалан: +998901234567):")
    await state.set_state(DriverInfo.phone)

@router.message(DriverInfo.car_model)
async def get_car_model(message: types.Message, state: FSMContext):
    await state.update_data(car_model=message.text)
    await message.answer("Машина рақами (масалан: 01A123BC):")
    await state.set_state(DriverInfo.car_number)

    #@router.message(DriverInfo.car_number)
    #async def get_car_number(message: types.Message, state: FSMContext):
    #    await state.update_data(car_number=message.text)
    #    await message.answer("Йўловчилар учун неча ўрин бор?")
    #    await state.set_state(DriverInfo.seat_count)

    # @router.message(DriverInfo.seat_count)

@router.message(DriverInfo.car_number)
async def get_car_number(message: types.Message, state: FSMContext):
#    await state.update_data(seat_count=message.text)
    await state.update_data(car_number=message.text)
    data = await state.get_data()
    msg = (
        f"Исм: {data['name']}\n\n"
        f"Телефон: {data['phone']}\n\n"
        f"Машина: {data['car_model']} ({data['car_number']})\n\n"
        #f"Ўринлар сони: {data['seat_count']}\n\n"
        "✅ Тасдиқлайсизми?"
    )
    buttons = [
        [types.InlineKeyboardButton(text="✅ Ҳа", callback_data="confirm_yes"), 
         types.InlineKeyboardButton(text="❌ Йўқ", callback_data="confirm_no")]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(msg, reply_markup=keyboard)
    await state.set_state(DriverInfo.confirm)

@router.callback_query(lambda c: c.data in ["confirm_yes", "confirm_no"])
async def confirm_driver_info(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "confirm_yes":
        data = await state.get_data()
        user_id = callback_query.from_user.id
        save_driver_profile(user_id, data)
        msg = (
            f"Ҳайдовчи маълумотлари:\n\n"
            f"Исм: {data['name']}\n"
            f"Телефон: {data['phone']}\n"
            f"Машина: {data['car_model']} ({data['car_number']})\n\n"
            #f"Ўринлар сони: {data['seat_count']}\n\n"
            "✅ Маълумотларингиз сақланди!\nАдмин тасдиғини кутинг."
        )

        await send_or_edit_text(callback_query.message, msg, reply_markup=None)

        # ✅ Админларга хабар юбориш
        await notify_admins_about_new_driver(user_id, data)
    else:
        await send_or_edit_text(callback_query.message, "Маълумот киритиш бекор қилинди.", reply_markup=None)

    await state.clear()

def save_driver_profile(user_id, profile_data):
    drivers = load_drivers()
    user_id = str(user_id)

    # Фақат керакли маълумотларни оламиз
    clean_profile = {
        "name": profile_data.get("name"),
        "phone": profile_data.get("phone"),
        "car_model": profile_data.get("car_model"),
        "car_number": profile_data.get("car_number"),
        "seat_count": "4" #profile_data.get("seat_count")
    }

    existing_data = drivers.get(user_id, {})

    drivers[user_id] = {
        **existing_data,
        "id": user_id,
        "status": "pending_approval",
        "profile": clean_profile,
        "rating": existing_data.get("rating", 0),
        "approved": existing_data.get("approved", False),
        "balance": 0,  # Янги баланс
        "bonus": 0  # Янги бонус
    }

    save_driver(drivers)

# ✅ 1. Ҳайдовчи маълумот киритгач
def save_driver_pending(user_id, driver_data):
    users = load_drivers()
    user_id = str(user_id)

    users[user_id] = {
        "status": "pending_approval",
        "driver_data": driver_data
    }

    save_driver(users)
    logging.info(f"Ҳайдовчи {user_id} маълумотлари тасдиқ кутмоқда.")

# ✅ 2. Админ тасдиқлаганда (мисол учун админ менюда):
def approve_driver(user_id: str):
    users = load_drivers()

    if user_id not in users or users[user_id].get("status") != "pending_approval":
        logging.warning(f"Ҳайдовчи {user_id} топилмади ёки тасдиқлашга тайёр эмас.")
        return False

    # ✅ driver_data ёки profile ни текшириш
    driver_data = users[user_id].get("driver_data") or users[user_id].get("profile")
    if not driver_data:
        logging.error(f"Профиль маълумотлари топилмади: {user_id}")
        return False

    users[user_id]["status"] = "driver"
    users[user_id]["profile"] = driver_data
    users[user_id]["rating"] = 0
    users[user_id]["orders"] = []
    users[user_id]["approved"] = True
    users[user_id]["balance"] = 40000
    users[user_id]["bonus"] = 0

    save_driver(users)
    logging.info(f"Ҳайдовчи {user_id} тасдиқланди ва balance/bonus қўшилди.")
    return True

# ✅ 2. approval panel очиш
@router.callback_query(lambda c: c.data == "approve_panel")
async def open_admin_panel(callback_query: CallbackQuery):
    user_id = int(callback_query.from_user.id)
    logging.info(f"Callback data: {callback_query.data}")
    print(f"Callback: {callback_query.data}")
    #if str(user_id) not in ADMINS:
    if user_id not in ADMINS:
        await callback_query.message.answer("🚫 Сизда рухсат йўқ.")
        return

    drivers = load_drivers()
    pending_drivers = {
        k: v for k, v in drivers.items()
        if v.get("status") == "pending_approval" and not v.get("approved", False)
    }

    if not pending_drivers:
        await callback_query.message.answer("⏳ Тасдиқ кутaётган ҳайдовчилар йўқ.")
        return

    for driver_id, data in pending_drivers.items():
        profile = data.get("profile") or data.get("driver_data")
        if profile is None:
            logging.warning(f"Профиль топилмади: driver_id={driver_id}, data={data}")
            await callback_query.message.answer(f"⚠️ Хатолик: Ҳайдовчи {driver_id} профили топилмади.")
            continue
        text = (
            f"👤 Исм: {profile['name']}\n"
            f"📞 Телефон: {profile['phone']}\n"
            f"🚘 Машина: {profile['car_model']} ({profile['car_number']})\n"
            #f"💺 Жойлар сони: {profile['seat_count']}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"approve_driver:{driver_id}")],
            [InlineKeyboardButton(text="❌ Рад этиш", callback_data=f"reject_driver:{user_id}")]
        ])

        await callback_query.message.answer(text, reply_markup=keyboard)

# ✅ 3. Callback: Тасдиқлаш тугмаси
@router.callback_query(F.data.startswith("approve_driver:"))
async def approve_driver_callback(callback_query: CallbackQuery, state: FSMContext):
    driver_id = callback_query.data.split(":")[1]

    logging.info(f"TASDIQLASH BOSILDI: {driver_id}")  # 👈 Қўшимча лог
    print(f"TASDIQLANDI: {driver_id}")

    success = approve_driver(driver_id)  # 🔁 Марказий approve_driver() ишлатилади

    if success:
        await callback_query.message.answer(f"✅ Ҳайдовчи {driver_id} муваффақиятли тасдиқланди.")
        try:
            await bot.send_message(
                int(driver_id),
                text="✅ Сиз админ томонидан тасдиқландингиз!\nЭнди асосий менюдан фойдаланишингиз мумкин.",
                reply_markup=start_kb(int(driver_id))
            )
        except Exception as e:
            await callback_query.message.answer(f"⚠️ Хабар юбориб бўлмади: {e}")
    else:
        await callback_query.message.answer(f"❌ Ҳайдовчи {driver_id} топилмади ёки тасдиқлашга тайёр эмас.")

# админларга хабар юбориш
async def notify_admins_about_new_driver(driver_id: int, driver_data: dict):
    text = (
        f"🆕 Тасдиқ кутaётган янги ҳайдовчи:\n\n"
        f"👤 Исм: {driver_data['name']}\n"
        f"📞 Телефон: {driver_data['phone']}\n"
        f"🚘 Машина: {driver_data['car_model']} ({driver_data['car_number']})\n"
#        f"💺 Жойлар сони: {driver_data['seat_count']}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[ 
        [InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"approve_driver:{driver_id}")]
    ])

    for admin_id in ADMINS:
        try:
            # Админга хабар юбориш
            await bot.send_message(admin_id, text, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"⚠️ Админга хабар юбориб бўлмади ({admin_id}): {e}")
