# handlers/driver_info.py
import json
from aiogram import Router, types, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from states import DriverInfo
from start import notify_admins_about_new_driver
from utils import save_driver, load_drivers, send_or_edit_text, USER_STATUS_PATH, DRIVER_PATH
import logging

router = Router()

@router.callback_query(F.data == "is_driver_approved_check")
async def check_driver_info_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Ҳозирча сизнинг маълумотларингиз админ томонидан кўриб чиқиляпти. Илтимос кутиб туринг.")
    await state.set_state(DriverInfo.name)

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
        "status": "driver",
        "profile": clean_profile,
        "rating": existing_data.get("rating", 0),
        "approved": existing_data.get("approved", False)
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
def approve_driver(user_id):
    users = load_drivers()
    user_id = str(user_id)

    if user_id in users and users[user_id].get("status") == "pending_approval":
        driver_data = users[user_id].get("driver_data", {})

        users[user_id]["status"] = "driver"
        users[user_id]["profile"] = driver_data  # ✅ 'profile' қўшилди
        users[user_id]["rating"] = 0
        users[user_id]["orders"] = []
        users[user_id]["approved"] = True

        # driver_data ни алоҳида driver.json га ҳам сақласак бўлади (ихтиёрий)
        drivers = load_drivers()
        drivers[user_id] = {
            "profile": driver_data,
            "rating": 0,
            "orders": []
        }

        save_driver(users)
        logging.info(f"Ҳайдовчи {user_id} тасдиқланди ва profile қўшилди.")
        return True

    logging.warning(f"Ҳайдовчи {user_id} топилмади ёки тасдиқлашга тайёр эмас.")
    return False
