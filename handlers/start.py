# handlers/start.py
import logging
import json
from aiogram import Bot, Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from datetime import datetime
import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import ADMINS, TOKEN
from states import DriverInfo, AdminStates
from keyboards.start_kb import start_kb
from utils import (
    load_json, save_json, load_users, save_user_status, recommend_multiple_drivers_to_passenger,
    get_passenger_order, send_or_edit_last, load_passenger, get_driver_order, save_passenger_order, send_or_edit_text,
    load_drivers, save_driver, is_driver_approved, create_departure_confirmation_keyboard,
    USER_STATUS_PATH, PASSENGER_PATH, DRIVER_PATH
)

bot = Bot(token=TOKEN)

router = Router()

@router.message(F.contact)
async def handle_contact(message: Message):
    user_id = str(message.from_user.id)

    with open(PASSENGER_PATH, 'r', encoding='utf-8') as file:
        passengers = json.load(file)

    user_data = passengers.get(user_id)
    if not user_data or not user_data.get("waiting_for_phone"):
        return

    phone = message.contact.phone_number
    user_data["phone"] = phone
    user_data["waiting_for_phone"] = False

    with open(PASSENGER_PATH, 'w', encoding='utf-8') as file:
        json.dump(passengers, file, ensure_ascii=False, indent=4)

    await message.answer("✅ Рақам сақланди. Мос ҳайдовчилар юбориляпти...", reply_markup=ReplyKeyboardRemove())

    order = user_data.get("order")
    if order:
        await recommend_multiple_drivers_to_passenger(user_id, order, message.bot)


@router.callback_query(F.data.startswith("contact:"))
async def handle_contact_callback(callback: CallbackQuery):
    _, role, target_user_id = callback.data.split(":")
    user = await bot.get_chat(target_user_id)
    username = user.username or "Фойдаланувчи номаълум"
    
    text = f"📱 Боғланиш учун сизнинг мос инсон:\n@{username}"
    await callback.message.answer(text)

@router.message(lambda m: m.contact is not None)
async def handle_contact(message: Message):
    user_id = str(message.from_user.id)
    phone_number = message.contact.phone_number

    # JSON'ни очиб, маълумотни янгилаймиз
    data = load_json(PASSENGER_PATH)

    if user_id in data:
        data[user_id]["phone"] = phone_number
        print(f"✅ Телефон сақланяпти: {phone_number}")

        # JSON'ни қайта ёзиш
        save_json(PASSENGER_PATH, data)

        await message.answer("✅ Телефон рақамингиз сақланди. Мос ҳайдовчилар юбориляпти...",
                             reply_markup=ReplyKeyboardRemove())

        # Агарда буйрутма мавжуд бўлса, қайта мос ҳайдовчиларни тавсия қиламиз
        user_data = data[user_id]
        order = user_data.get("order")
        if order:
            await recommend_multiple_drivers_to_passenger(
                passenger_id=user_id,
                user_order=order,
                bot=message.bot
            )
    else:
        print(f"❌ Йўловчи PASSENGER_PATH'да топилмади: {user_id}")
        await message.answer("❌ Йўловчи маълумоти топилмади.")

# 📞 Қўлда рақам киритилганда
@router.message(lambda m: m.text and m.text.startswith("+998") and m.text[1:].isdigit())
async def handle_manual_phone(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    phone_text = message.text.strip()

    # 📁 Файллардан маълумотларни оламиз
    status_data = load_json(USER_STATUS_PATH)
    passenger_data = load_json(PASSENGER_PATH)

    user_status = status_data.get(user_id, {})
    user_type = user_status.get("status")  # "driver" ёки "passenger"

    # ❗ Рақам тўлиқ форматида эмас — 13та белги бўлмаса
    if len(phone_text) != 13:
        await message.answer("❗ Илтимос, рақамингизни +998901234567 кўринишида тўлиқ киритинг.")
        return
    
    # 👤 Агар йўловчи бўлса ва телефон рақами кутилса
    if user_type == "passenger":
        passenger = passenger_data.get(user_id)
        if passenger and passenger.get("waiting_for_phone"):
            passenger["phone"] = phone_text
            passenger["waiting_for_phone"] = False

            try:
                with open(PASSENGER_PATH, 'w', encoding='utf-8') as f:
                    json.dump(passenger_data, f, ensure_ascii=False, indent=4)
            except Exception as e:
                await message.answer("❗ Рақамни сақлашда хатолик юз берди. Илтимос, қайта урининг.")
                logging.error(f"Телефон рақам сақлашда хатолик: {e}")

            await message.answer("✅ Рақам сақланди. Мос ҳайдовчилар юбориляпти...", reply_markup=types.ReplyKeyboardRemove())

            order = passenger.get("order")
            if order:
                await recommend_multiple_drivers_to_passenger(user_id, order, message.bot)
        return

    # 🚗 Агар ҳайдовчи бўлса — рақамни сақлаб, анкета давом эттирилади
    elif user_type == "driver":
        await state.update_data(phone=phone_text)
        await message.answer("Машина русуми (масалан: Nexia 3):")
        await state.set_state(DriverInfo.car_model)
        return

    # 👻 Агар аниқланмаган фойдаланувчи бўлса — жавоб бермаймиз
    return


async def ask_for_phone_number(message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Телефон рақамни юбориш", request_contact=True)],
            [KeyboardButton(text="📱 Қўлда рақам киритиш")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "📱 Телефон рақамингизни юборинг:\n\n"
        "1. Автоматик: '📞 Телефон рақамни юбориш' тугмасини босинг\n"
        "2. Ёки '📱 Қўлда рақам киритиш' тугмасини босиб, рақамни ўзингиз киритинг",
        reply_markup=keyboard
    )

async def notify_driver(driver_id: str, passenger_id: str, passenger_order: dict):
    text = (
        f"🧍‍♂️ *Йўловчи маълумотлари:*\n"
        f"📍 Манзил: {passenger_order.get('location')}\n"
        f"🕓 Вақт: {passenger_order.get('time')}\n"
        f"📞 Алоқа: @{passenger_order.get('username', passenger_id)}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Қабул қилиш", callback_data=f"accept_passenger_{passenger_id}")]
        ]
    )

    await bot.send_message(
        chat_id=int(driver_id),
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(lambda c: c.data.startswith("select_driver_"))
async def process_driver_selection(callback: CallbackQuery):
    driver_id = callback.data.split("_")[-1]
    passenger_id = callback.from_user.id

    order = get_passenger_order(passenger_id)
    if not order:
        return await callback.message.answer("Буйрутма топилмади.")

    order["username"] = callback.from_user.username
    await notify_driver(driver_id, passenger_id, order)
    await callback.message.answer("Ҳайдовчига хабар юборилди!")

from asyncio import create_task, sleep

# Ҳар бир йўловчи учун таймерларни сақлаш
pending_timers = {}

@router.callback_query(lambda c: c.data.startswith("choose_driver_"))
async def process_driver_choice(callback_query: CallbackQuery):
    passenger_id = str(callback_query.from_user.id)
    driver_id = callback_query.data.split("_")[-1]

    # JSON файллардан маълумотларни ол
    passengers = load_json(PASSENGER_PATH)
    drivers = load_json(DRIVER_PATH)

    passenger = passengers.get(passenger_id)
    driver = drivers.get(driver_id)

    if not passenger or not driver:
        await callback_query.answer("Маълумот топилмади.")
        return
    
    order = passenger.get("order", {})

    # ✅ Агар йўловчи аллақачон ҳайдовчи танлаган бўлса
    if order.get("chosen_driver_id"):
        await callback_query.answer("✅ Сиз аллақачон ҳайдовчи танлагансиз.", show_alert=True)
        return

    # 🔒 Танланган ҳайдовчи ID ни сақлаш
    order["chosen_driver_id"] = driver_id

    passengers[passenger_id]["order"] = order
    save_json(PASSENGER_PATH, passengers)

    # 👤 Йўловчи маълумотлари
    passenger_name = callback_query.from_user.full_name
    price = order.get("price", -1)
    price_text = f"{price:,} сўм" if price > 0 else "Аниқланмаган"

    # ✅ Ҳайдовчига хабар юбориш
    msg_to_driver = (
        f"🛣 Сизга мос йўловчи:\n\n"
        f"📍 Йўналиш: {passenger['order']['from_district']} ➝ {passenger['order']['to_district']}\n"
        f"📅 Сана: {passenger['order']['date']}\n"
        f"⏰ Вақт: {passenger['order']['time']}\n\n"
        f"👤 *Йўловчи*: {passenger_name}\n"
        f"💵 Таклиф қилинган нарх: {price_text}\n"
    )

    accept_btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Қабул қилиш", callback_data=f"accept_passenger_{passenger_id}")
    ]])

    # ✅ Йўловчига тасдиқ хабар
    await callback_query.message.answer("✅ Ҳайдовчига хабар юборилди, агар 5 дақиқада жавоб бермаса, навбатдаги ҳайдовчига юборилади.")
    await bot.send_message(driver_id, msg_to_driver, reply_markup=accept_btn)

    # Callback’га жавоб бериш (тугмани "pending" ҳолатдан чиқариш)
    await callback_query.answer()

    # 🕓 5 дақиқа кутиш ва кейин навбатдаги ҳайдовчига юбориш
    task = create_task(wait_for_driver_response(passenger_id, driver_id))
    pending_timers[passenger_id] = task

async def wait_for_driver_response(passenger_id, driver_id):
    await sleep(300)  # 5 дақиқа = 300 секунд

    passengers = load_json(PASSENGER_PATH)
    passenger = passengers.get(passenger_id)

    if not passenger:
        return

    order = passenger.get("order", {})
    
    # Агар йўловчи тасдиқ олмаган бўлса
    if order.get("chosen_driver_id") == driver_id:
        order["chosen_driver_id"] = None  # Танловни бекор қилиш

        passengers[passenger_id]["order"] = order
        passengers = load_json(PASSENGER_PATH)

        # ✅ Кейинги ҳайдовчига тавсия қилиш
        await recommend_multiple_drivers_to_passenger(
            passenger_id=passenger_id,
            user_order=order,
            bot=bot
        )

@router.callback_query(lambda c: c.data.startswith("accept_passenger_"))
async def process_accept_passenger(callback_query: CallbackQuery):
    driver_id = str(callback_query.from_user.id)
    passenger_id = callback_query.data.split("_")[-1]

    drivers = load_json(DRIVER_PATH)
    passengers = load_json(PASSENGER_PATH)

    driver = drivers.get(driver_id)
    passenger = passengers.get(passenger_id)

    if not driver or not passenger:
        await callback_query.answer("Маълумот топилмади.")
        return

    # 🚫 Таймерни бекор қиламиз агар бор бўлса
    task = pending_timers.pop(passenger_id, None)
    if task:
        task.cancel()

    # ❌ Агар жой қолмаган бўлса, қабул қилишга рухсат йўқ
    if driver.get("order", {}).get("available_seats", 0) <= 0:
        await callback_query.answer("❌ Жой қолмаган!", show_alert=True)
        return
    
    # 🧍‍♂️ Йўловчига тўлиқ маълумот
    driver_info_text = (
        f"✅ Танловингиз маъқулланди!\n\n"
        f"🚘 Ҳайдовчи маълумотлари:\n"
        f"👤 Исм: {driver['profile']['name']}\n"
        f"📞 Телефон: {driver['profile']['phone']}\n"
        f"🚗 Машина: {driver['profile']['car_model']} ({driver['profile']['car_number']})\n"
        f"📍 Йўналиш: {driver['order']['from_district']} ➝ {driver['order']['to_district']}\n"
        f"📅 Сана: {driver['order']['date']}\n"
        f"⏰ Вақт: {driver['order']['time']}"
    )
    try:
        await bot.send_message(
            chat_id=int(passenger_id), 
            text=driver_info_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚘 Ҳайдовчи етиб келди", callback_data=f"arrived_yes_{driver_id}")]
            ])
        )
    except Exception as e:
        print(f"❌ Хатолик юборишда: {e}")

    passenger_name = callback_query.from_user.full_name

    # ✅ Ҳайдовчига тўлиқ маълумот юбориш
    full_info = (
        f"🧍‍♂️ Йўловчи маълумотлари:\n\n"
        f"👤 Йўловчи: {passenger_name}\n"
        f"📞 Телефон: {passenger.get('phone', 'Номаълум')}\n"
        f"📍 Йўналиш: {passenger['order']['from_district']} ➝ {passenger['order']['to_district']}\n"
        f"📅 Сана: {passenger['order']['date']}\n"
        f"⏰ Вақт: {passenger['order']['time']}\n"
        f"💰 Нарх: {passenger['order'].get('price', 'Номаълум')} сўм"
    )
    #await callback_query.message.answer(full_info)
    await send_or_edit_text(callback_query.message, full_info, reply_markup=None)

    # 🪑 Ҳайдовчида камайтирамиз
    if "available_seats" in driver["order"]:
        driver["order"]["available_seats"] = max(0, driver["order"]["available_seats"] - 1)

    # 👥 accepted_passengers рўйхатига қўшамиз
    driver_order = driver["order"]
    driver_order.setdefault("accepted_passengers", [])
    if not any(p['passenger_id'] == passenger_id for p in driver_order["accepted_passengers"]):
        driver_order["accepted_passengers"].append({
            "passenger_id": passenger_id,
            "price": passenger['order'].get('price', 0)
        })

    # 👀 Агар охирги жой тўлган бўлса, ҳайдовчига хабар
    if driver_order["available_seats"] == 0:
        try:
            await bot.send_message(
                chat_id=int(driver_id),
                text="✅ Охирги йўловчи қабул қилинди.\n🚗 Машина тўлди!\n\nЙўлга чиққанингизда тасдиқласангиз йўловчиларга билдиршнома юборамиз.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🛣 Йўлга чиқдим", callback_data="on_the_way")]
                ])
            )
        except Exception as e:
            print(f"❌ Ҳайдовчига хабар юборишда хато: {e}")

    # 🕓 Вақт белгиси
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 📝 Йўловчи буюртмасини янгилаймиз
    if "order" in passenger:
        order = passenger["order"]
        order["status"] = "accepted"
        order.setdefault("status_timestamps", {})
        order["status_timestamps"]["accepted"] = timestamp
        order["chosen_driver_id"] = driver_id 

    # 🔐 Файлларни қайта ёзамиз
    save_json(DRIVER_PATH, drivers)
    save_json(PASSENGER_PATH, passengers)

    await callback_query.answer("✅ Йўловчи қабул қилинди.")

# 🚗 Ҳайдовчи "Йўлга чиқдим" босганда
@router.callback_query(F.data == "on_the_way")
async def process_driver_on_the_way(callback_query: CallbackQuery):
    driver_id = str(callback_query.from_user.id)

    drivers = load_json(DRIVER_PATH)
    driver = drivers.get(driver_id)

    if not driver or "order" not in driver:
        await callback_query.answer("Буюртма топилмади.", show_alert=True)
        return

    order = driver["order"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ✅ Статус ва вақтни белгилаш
    order["status"] = "on_the_way"
    order.setdefault("status_timestamps", {})["on_the_way"] = timestamp

    passengers = load_json(PASSENGER_PATH)

    # 🧍‍♂️ accepted_passengers рўйхатидаги ҳар бир йўловчига хабар
    accepted_passengers = order.get("accepted_passengers", [])
    for passenger_id in accepted_passengers:
        passenger = passengers.get(passenger_id)
        if not passenger:
            continue

        # ✅ Йўловчида ҳам статусни янгилаш
        if "order" in passenger:
            passenger_order = passenger["order"]
            passenger_order["status"] = "on_the_way"
            passenger_order.setdefault("status_timestamps", {})["on_the_way"] = timestamp

        try:
            await bot.send_message(
                chat_id=int(passenger_id),
                text="🚘 Ҳайдовчи йўлга чиқди.\n\nЕтиб борганида тасдиқлашингизни сўраймиз.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Етиб келди", callback_data=f"arrived_yes_{driver_id}"),
                            InlineKeyboardButton(text="❌ Ҳали келмади", callback_data=f"arrived_no_{driver_id}")
                        ]
                    ]
                )
            )
        except Exception as e:
            print(f"❌ Йўловчига хабар юборишда хато: {e}")

    # 🚗 Ҳайдовчига хабар
    await send_or_edit_text(
        callback_query.message,
        "✅ Сафарингиз бехатар бўлсин!.\n\nЕтиб боргач тасдиқлашни унутманг.\n\nСизга оқ йўл тилаймиз!!!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Манзилга етиб келдим", callback_data=f"arrived_destination")]
            ]
        )
    )

    # 🔐 Файлни сақлаш
    save_json(PASSENGER_PATH, passengers)
    save_json(DRIVER_PATH, drivers)

@router.callback_query(F.data.startswith("arrived_yes_"))
async def process_arrived_yes(callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    driver_id = data_parts[-1]  # arrived_yes_<driver_id>
    passenger_id = str(callback_query.from_user.id)

    # ⏳ Вақтни тайёрлаш
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 🧍‍♂️ Йўловчининг order объектига статус сақлаш
    passengers = load_json(PASSENGER_PATH)
    drivers = load_json(DRIVER_PATH)

    passenger = passengers.get(passenger_id)
    driver = drivers.get(driver_id)

    if not passenger or "order" not in passenger or not driver or "order" not in driver:
        await callback_query.answer("Ордер топилмади.", show_alert=True)
        return
    
    passenger_order = passenger["order"]
    passenger_order.setdefault("status_timestamps", {})["arrived_confirmation"] = timestamp

    driver_order = driver["order"]

    # Агар ҳайдовчида ҳали "on_the_way" белгиланмаган бўлса
    if driver_order.get("status") != "on_the_way":
        driver_order["status"] = "on_the_way"
        driver_order.setdefault("status_timestamps", {})["on_the_way"] = timestamp

        accepted_passengers = driver_order.get("accepted_passengers", [])
        for item in accepted_passengers:
            p_id = item if isinstance(item, str) else item.get("passenger_id")
            if not p_id:
                continue
            p = passengers.get(p_id)
            if p and "order" in p:
                p["order"]["status"] = "on_the_way"
                p["order"].setdefault("status_timestamps", {})["on_the_way"] = timestamp
    
    # ✅ Ҳамкорлик учун миннатдорлик ва "Манзилга етдим" тугмаси
    arrived_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Манзилга етдим", callback_data=f"finished_trip_{driver_id}")]
    ])
    
    # Javob sifatida yo‘lovchiga minnatdorchilik bildiruvchi xabar
    await send_or_edit_text(
        callback_query,
        text="✅ Ҳамкорлигингиздан миннатдормиз! 😊\n\n*Сафарингиз бехатар бўлсин.*\n\nМанзилга етганингизда тасдиқлаб қўйинг.",
        reply_markup=arrived_keyboard,
        parse_mode="Markdown"
    )

    # 🔐 Сақлаш
    save_json(PASSENGER_PATH, passengers)
    save_json(DRIVER_PATH, drivers)

@router.callback_query(F.data.startswith("finished_trip_"))
async def process_trip_finished(callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    driver_id = data_parts[-1]  # finished_trip_<driver_id>
    passenger_id = str(callback_query.from_user.id)

    passengers = load_json(PASSENGER_PATH)
    drivers = load_json(DRIVER_PATH)

    passenger = passengers.get(passenger_id)
    driver = drivers.get(driver_id)

    if not passenger or "order" not in passenger:
        await callback_query.answer("Буюртма топилмади.", show_alert=True)
        return

    order = passenger["order"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 🔵 Йўловчи сафарини done қилиш
    order["status"] = "arrived"
    order.setdefault("status_timestamps", {})["arrived"] = timestamp

    # 🟡 Тарихга сақлаш
    passenger.setdefault("order_history", []).append(order)
    del passenger["order"]

    # 🔐 Сақлаш
    save_json(PASSENGER_PATH, passengers)

    # 🚘 Feedback тугмаларини чиқариш
    await send_or_edit_text(
        callback_query,
        text="🚘 Бизнинг хизматдан фойдаланганингиз учун раҳмат.\n\nҚуйида ҳайдовчини баҳолашингиз мумкин:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍 Яхши", callback_data=f"feedback_good_{driver_id}"),
                    InlineKeyboardButton(text="👎 Ёмон", callback_data=f"feedback_bad_{driver_id}")
                ]
            ]
        )
    )

    # ✅ Йўловчига тасдиқ хабар
    await send_or_edit_text(
        callback_query,
        text="✅ Сафар муваффақиятли тугади! 🚘\n\nҲамкорлигингиз учун катта раҳмат! 😊",
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("arrived_no_"))
async def process_arrived_no(callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    driver_id = data_parts[-1]  # arrived_no_<driver_id>

    await callback_query.answer("⏳ Ҳайдовчи етиб бормаган деб қайд этилди.", show_alert=True)

    # Йўловчига яна бир бор тасдиқ тугмаси билан хабар юбориш
    await send_or_edit_text(
        callback_query.message,
        "⏳ Ҳайдовчи хабар юборилди.\n\nМашина етиб келганида тасдиқлашингизни сўраймиз.\n\nИлтимос, бироз кутиб туринг!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Ҳайдовчи етиб келди", callback_data=f"arrived_yes_{driver_id}")]
            ]
        )
    )

    # Агар керак бўлса ҳайдовчига ҳам хабар бериш
    try:
        await bot.send_message(
            chat_id=int(driver_id),
            text="❗ Йўловчи етиб бормаганингизни қайд этди."
        )
    except Exception as e:
        print(f"❌ Ҳайдовчига хабар юборишда хато: {e}")

@router.callback_query(F.data.startswith("arrived_destination"))
async def process_driver_arrived(callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    driver_id = data_parts[-1]  # arrived_destination_<driver_id>

    drivers = load_json(DRIVER_PATH)
    passengers = load_json(PASSENGER_PATH)

    driver = drivers.get(driver_id)
    if not driver or "order" not in driver:
        await callback_query.answer("Буюртма топилмади.", show_alert=True)
        return

    order = driver["order"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ✅ Статусни якунлаш
    order["status"] = "arrived"
    order.setdefault("status_timestamps", {})["arrived"] = timestamp


    # Сафар давомийлигини ҳисоблаш
    on_the_way_time = order.get("status_timestamps", {}).get("on_the_way")
    arrived_time = order.get("status_timestamps", {}).get("arrived")

    if on_the_way_time and arrived_time:
        # Вақтни ҳисоблаш
        on_the_way_dt = datetime.strptime(on_the_way_time, "%Y-%m-%d %H:%M:%S")
        arrived_dt = datetime.strptime(arrived_time, "%Y-%m-%d %H:%M:%S")
        trip_duration = arrived_dt - on_the_way_dt
        hours, remainder = divmod(trip_duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        duration_text = f"{hours} соат {minutes} дақиқага"

        # Сафар давомийлигини қўшиш
        duration_message = f"✅ Сафар якунланди.\n\nСафар давомийлиги: {duration_text}.\n\nЙўловчилар фикрини кутамиз."
    else:
        duration_message = "✅ Сафар якунланди. Йўловчилар фикрини кутамиз."
    
    # 🧍‍♂️ Ҳар бир accepted_passenger'га сўров юбориш
    accepted_passengers = order.get("accepted_passengers", [])

    # ✅ Ҳар бир accepted_passenger учун статусни "arrived" қилиш
    for passenger_id in accepted_passengers:
        passenger = passengers.get(passenger_id)
        if not passenger or "order" not in passenger:
            continue

        p_order = passenger["order"]

        if p_order.get("status") != "arrived":
            # 🔵 Йўловчи сафарини arrived қилиш
            p_order["status"] = "arrived"
            p_order.setdefault("status_timestamps", {})["arrived"] = timestamp

            # 🟡 Тарихга сақлаш
            passenger.setdefault("order_history", []).append(p_order)
            del passenger["order"]

        try:
            await bot.send_message(
                chat_id=int(passenger_id),
                text="🚘 Бизнинг хизматдан фойдаланганингиз учун раҳмат.\n\nҚуйида ҳайдовчини баҳолашингиз мумкин",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="👍 Яхши", callback_data=f"feedback_good_{driver_id}"),
                            InlineKeyboardButton(text="👎 Ёмон", callback_data=f"feedback_bad_{driver_id}")
                        ]
                    ]
                )
            )
        except Exception as e:
            print(f"❌ Йўловчига сўров юборишда хато: {e}")

    # 🚗 Ҳайдовчига тасдиқ хабар
    await send_or_edit_text(
        callback_query.message,
        duration_message,
        reply_markup=None
    )

    # 🔐 Файлни сақлаш
        # 🧾 Йўловчилар маълумотини сақлаш
    save_json(DRIVER_PATH, drivers)
    save_json(PASSENGER_PATH, passengers)

@router.callback_query(lambda c: c.data.startswith("feedback_"))
async def process_feedback(callback_query: CallbackQuery):
    data = callback_query.data
    parts = data.split("_")
    
    if len(parts) < 3:
        await callback_query.answer("❌ Нотўғри формат.", show_alert=True)
        return

    _, feedback_type, driver_id = parts
    passenger_id = str(callback_query.from_user.id)

    passengers = load_json(PASSENGER_PATH)
    drivers = load_json(DRIVER_PATH)

    passenger = passengers.get(passenger_id)
    driver = drivers.get(driver_id)

    if not passenger or not driver:
        await callback_query.answer("❌ Ҳайдовчи ёки йўловчи топилмади.", show_alert=True)
        return

    # ⭐ Feedback
    feedback = 1 if feedback_type == "good" else -1

    if "rating" not in driver:
        driver["rating"] = 0
    if "feedbacks" not in driver:
        driver["feedbacks"] = []

    driver["feedbacks"].append(feedback)

    # Рейтингни қайта ҳисоблаш
    driver["rating"] = sum(driver["feedbacks"]) / len(driver["feedbacks"])

    # Йўловчининг буюртмасини done қилиш (агар ҳали тарихга ўтказилмаган бўлса)
    if "order" in passenger:
        order = passenger["order"]

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order["status"] = "arrived"
        order.setdefault("status_timestamps", {})["arrived"] = now

        passenger.setdefault("order_history", []).append(order)
        del passenger["order"]

    # 🔐 Сақлаш
    save_json(DRIVER_PATH, drivers)
    save_json(PASSENGER_PATH, passengers)

    await send_or_edit_text(callback_query, "✅ Баҳо учун раҳмат! Буюртмангиз ёпилди ва тарихга ўтказилди.")

from aiogram.filters import CommandStart, CommandObject

@router.message(CommandStart(deep_link=True))
@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext, bot: Bot, command: CommandObject):
    user_id = str(message.from_user.id)
    referral_id = command.args  # start параметридаги referral ID

    logging.info(f"Фойдаланувчи ID: {user_id}")
    
    # 📁 Статус файлдан олиш
    status_data = load_json(USER_STATUS_PATH)
    user_status = status_data.get(user_id, {}).get("status", "new_user")
    logging.info(f"Фойдаланувчининг статуси: {user_status}")

    # 📌 Referral'ни қайд этиш (фақат биринчи марта кирганда)
    if referral_id and referral_id != user_id:
        referrer_id = referral_id
        # Агар бу фойдаланувчи аввал рўйхатда бўлмаса
        if user_id not in status_data:
            status_data[user_id] = {
                "status": "new_user",
                  "referrer": referrer_id,  # Биринчи таклиф қилган одам
                  "first_name": message.from_user.first_name
            }
            # Referrer'нинг invited_users рўйхатига қўшамиз
            if referrer_id not in status_data:
                status_data[referrer_id] = {"status": "new_user", "invited_users": []}
            status_data[referrer_id].setdefault("invited_users", [])
            if user_id not in status_data[referrer_id]["invited_users"]:
                status_data[referrer_id]["invited_users"].append(user_id)
            save_json(USER_STATUS_PATH, status_data)
        else:
            # Агар аллақачон базада бўлса, аммо first_name йўқ бўлса, қўшамиз
            if "first_name" not in status_data[user_id]:
                status_data[user_id]["first_name"] = message.from_user.first_name
                save_json(USER_STATUS_PATH, status_data)
    
    else:
        # Агар referral бўлмаса ҳам, first_name сақлаб қўйиш
        if user_id not in status_data:
            status_data[user_id] = {
                "status": "new_user",
                "first_name": message.from_user.first_name
            }
            save_json(USER_STATUS_PATH, status_data)
        else:
            if "first_name" not in status_data[user_id]:
                status_data[user_id]["first_name"] = message.from_user.first_name
                save_json(USER_STATUS_PATH, status_data)

    # ➡️ Кейинги қисм: мавжуд кодингизни сақлаймиз
    if user_status == "new_user":
        text = "🤖 Ботга хуш келибсиз!\nКимлигингизни танланг:"
        await send_or_edit_last(user_id, state, bot, text, start_kb(int(user_id)))
    else:
        if user_status == "driver":
            if is_driver_approved(user_id):
                await message.answer("🚘 Ҳайдовчи учун меню:", reply_markup=start_kb(int(user_id)))
            else:
                text_driver = "Йўловчи буюртмаларини кўриш учун маълумотларингизни юборинг!"
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🧾 Маълумот юбориш", callback_data="haydovchi")],
                    [InlineKeyboardButton(text="Маълумот ҳолати", callback_data="is_driver_approved_check")]
                ])
                await message.answer(text_driver, reply_markup=keyboard)
        elif user_status == "passenger":
            text = "🏠 Бош меню:"
            await message.answer(text, reply_markup=start_kb(int(user_id)))

@router.callback_query(F.data == "invite_friends")
async def invite_friends_callback(callback_query: types.CallbackQuery, bot: Bot):
    user_id = str(callback_query.from_user.id)
    bot_username = (await bot.me()).username
    invite_link = f"https://t.me/{bot_username}?start={user_id}"

    text = (
        "🎉 Дўстларингизни таклиф қилинг ва бонуслар олинг!\n\n"
        f"Ҳаволангиз: {invite_link}\n\n"
        "Дўстларингиз шу ҳавола орқали ботга кирса, сизга бонус ёзилади! 🚀"
    )
    await callback_query.message.answer(text)
    await callback_query.answer()

@router.callback_query(F.data == "my_stats")
async def show_my_stats(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    
    # 📁 Файлдан статуслар оламиз
    status_data = load_json(USER_STATUS_PATH)
    user_info = status_data.get(user_id, {})
    
    # Нечта дўст таклиф қилгани
    invited_users = user_info.get("invited_users", [])
    invited_count = len(invited_users)

    # Унинг статуси (driver / passenger)
    user_status = user_info.get("status", "Аниқланмаган")

    # 📊 Асосий статистика
    text = (
        f"📊 Сизнинг статистика:\n\n"
        f"👤 Статус: {user_status.capitalize()}\n"
        f"👥 Таклиф қилинган дўстлар сони: {invited_count} та\n"
    )

    # 👥 Агар таклиф қилинганлар бор бўлса, уларнинг исмларини чиқарамиз
    if invited_users:
        text += "\n🧑‍🤝‍🧑 Таклиф қилинган дўстлар:\n"
        for idx, invited_id in enumerate(invited_users, 1):
            invited_info = status_data.get(str(invited_id), {})
            first_name = invited_info.get("first_name", "Номаълум")
            text += f"{idx}. {first_name}\n"
    else:
        text += "\n⏳ Ҳали дўст таклиф қилинмаган."

    await callback_query.message.answer(text)
    await callback_query.answer()

# ✅ 2. /admin буйруғи орқали approval panel очиш
#@router.callback_query(Text("approve_panel"))
@router.callback_query(lambda c: c.data == "approve_panel")
async def open_admin_panel(callback_query: CallbackQuery):
    user_id = int(callback_query.from_user.id)
    if str(user_id) not in ADMINS:
        await callback_query.message.answer("🚫 Сизда рухсат йўқ.")
        return

    drivers = load_drivers()
    pending_drivers = {
        k: v for k, v in drivers.items()
        if v.get("status") == "driver" and not v.get("approved", False)
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
async def approve_driver(callback_query: CallbackQuery, state: FSMContext):
    driver_id = callback_query.data.split(":")[1]
    users = load_drivers()

    if driver_id not in users:
        await callback_query.message.answer(f"⚠️ Хатолик: Ҳайдовчи {driver_id} топилмади.")
        return
    
    user = users[driver_id]
    user["approved"] = True
    save_driver(users)

    await callback_query.message.answer(f"✅ Ҳайдовчи {driver_id} муваффақиятли тасдиқланди.")

    # ✅ Ҳайдовчига тасдиқланганлиги ҳақида хабар юбориш
    try:
        await bot.send_message(
            int(driver_id),
            text="✅ Сиз админ томонидан тасдиқландингиз!\nЭнди асосий менюдан фойдаланишингиз мумкин.",
            reply_markup=start_kb(int(driver_id))
        )
    except Exception as e:
        await callback_query.message.answer(f"⚠️ Хабар юбориб бўлмади: {e}")

# Масалан, админларга хабар юбориш
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

async def check_today_departures(bot):
    today = datetime.today().strftime("%Y-%m-%d")

    if not os.path.exists(DRIVER_PATH):
        return

    drivers = load_json(DRIVER_PATH)

    for driver_id, driver_data in drivers.items():
        order = driver_data.get("order", {})
        if order and order.get("date") == today and order.get("status") == "new":
            await bot.send_message(
                chat_id=int(driver_id),
                text="📅 Бугун йўлга чиқиш кунингиз!\n\n🚘 Йўлга чиқдингизми?",
                reply_markup=create_departure_confirmation_keyboard(driver_id)
            )

def get_bot_statistics():
    users = load_users()           # Foydalanuvchilar statuslari
    passengers = load_passenger()  # Yo‘lovchi buyurtmalari
    drivers = load_drivers()       # Haydovchi buyurtmalari

    total_passengers = sum(1 for u in users.values() if u.get("status") == "passenger")
    total_drivers = sum(1 for u in users.values() if u.get("status") == "driver")

    total_orders_passengers = 0
    total_orders_drivers = 0
    active_orders = 0
    active_orders_passengers = 0
    active_orders_drivers = 0

    # Yo‘lovchilar buyurtма тарихини ҳисоблаш
    for passenger_data in passengers.values():
        history = passenger_data.get("order_history", [])
        total_orders_passengers += len(history)

        if passenger_data.get("order"):  # faol buyurtma бор
            active_orders_passengers += 1
            active_orders += 1

    # Haydovchilar buyurtма тарихини ҳисоблаш
    for driver_data in drivers.values():
        history = driver_data.get("order_history", [])
        total_orders_drivers += len(history)

        if driver_data.get("order"):  # faol buyurtma бор
            active_orders_drivers += 1
            active_orders += 1

    total_orders = total_orders_passengers + total_orders_drivers

    return {
        "active_orders": active_orders,
        "total_orders": total_orders,
        "total_passengers": total_passengers,
        "total_orders_passengers": total_orders_passengers,
        "active_orders_passengers": active_orders_passengers,
        "total_drivers": total_drivers,
        "total_orders_drivers": total_orders_drivers,
        "active_orders_drivers": active_orders_drivers
    }

# "📋 Статистика"
@router.callback_query(F.data == "statistika")
async def show_statistics(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    # Сизнинг статистика логикаингиз
    await callback_query.message.answer("Ҳайдовчи статистикаси тайёрланмоқда...")
    stats = get_bot_statistics()

    text = (
        "<b>/statistics</b>\n"
        "↳ <b>Ботдаги жорий статистика:</b>\n\n"
        f"- 📅 Бугунги сафарлар: {stats['total_orders']} та\n"
        f"- 🚗 Ҳайдовчилар: {stats['total_drivers']} та\n"
        f"- 🧍‍♂️ Йўловчилар сони: {stats['total_passengers']} та\n"
        f"- ✅ Якунланган буюртмалар: {stats['total_orders'] - stats['active_orders']} та\n"
        f"- ⏳ Жорий буюртмалар: {stats['active_orders']} та\n"
        f"- ⭐ Ўртача рейтинг: 4.8\n"      # Агар реал ҳисоб-китоб бўлса, динамик қилиб олиб келиш мумкин
        f"- 💬 Бугунги feedback'лар: 20 та\n\n"  # Бу ҳам худди шундай
        f"- 📦 Ҳайдовчилар буюртмалар: {stats['total_orders_drivers']}\n"
        f"- ⏳ Жараёндаги Ҳайдовчи буюртмалари: {stats['active_orders_drivers']}\n\n"
        f"- 📦 Йўловчилар буюртмалар: {stats['total_orders_passengers']}\n"
        f"- ⏳ Жараёндаги Йўловчи буюртмалари: {stats['active_orders_passengers']}"
    )

    await callback_query.message.answer(text, parse_mode="HTML")

# Ҳайдовчилар рўйхати чиқарадиган функция
@router.callback_query(F.data == "show_drivers_list")
async def show_drivers_list(callback_query: CallbackQuery):
    drivers = load_drivers()

    text = "<b>🚗 Ҳайдовчилар рўйхати:</b>\n\n"
    for user_id, driver_data in drivers.items():
        profile = driver_data.get("profile", {})
        name = profile.get("name", "Номаълум")
        rating = driver_data.get("rating", 0)
        
        accepted_passengers = driver_data.get("order", {}).get("accepted_passengers", [])
        accepted_count = len(accepted_passengers)
        total_income = sum(p.get("price", 0) for p in accepted_passengers)

        orders = len(driver_data.get("order_history", []))

        text += (
            f"👤 <b>{name}</b> (ID: <code>{user_id}</code>)\n"
            f"• 📦 Буюртмалар: {orders} та\n"
            f"• 🧍‍♂️ Қабул қилинган йўловчилар: {accepted_count} та\n"
            f"• ⭐ Рейтинг: {rating}\n"
            f"• 💰 Даромад: {total_income:,} сўм\n\n"
        )

    await callback_query.message.answer(text, parse_mode="HTML")


@router.callback_query(lambda c: c.data in [
    "orders", "driver", "passenger", "change_user_status", "choose_role",
    "admin", "upload_files"
] or c.data.endswith("_dan"))
async def handle_callback(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data = callback_query.data

    logging.info(f"Callback data: {data}")  # Debug

    if data == "orders":
        # Буюртмаларни кўрсатиш
        await callback_query.message.answer("Буйрутма қўшишни бошлаймиз...")
        from handlers.order import start_order
        await start_order(callback_query.message, state)

    elif data == "driver":
        save_user_status(user_id, "driver")

        # Тасдиқланган ҳайдовчи текширилади
        if is_driver_approved(user_id):
            await callback_query.message.edit_text("🚘 Ҳайдовчи учун меню:", reply_markup=start_kb(user_id))
        else:
            await callback_query.message.edit_text(
                "Йўловчи буюртмаларини кўриш учун маълумотларингизни юборинг!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🧾 Маълумот юбориш", callback_data="haydovchi")],
                    [InlineKeyboardButton(text="Маълумот ҳолати", callback_data="is_driver_approved_check")]
                ])
            )

    elif data == "passenger":
        save_user_status(user_id, "passenger")
        await callback_query.message.edit_text(f"🏠 *Бош меню:*", reply_markup=None, parse_mode="Markdown")
        await callback_query.message.answer("Манзилни танлаш:", reply_markup=start_kb(user_id))

    elif data == "change_user_status":
        save_user_status(user_id, "new_user")
        await callback_query.message.edit_reply_markup(reply_markup=None)
        await callback_query.message.answer("🏠 Бош меню:", reply_markup=start_kb(user_id))

    elif data == "admin":
        if str(user_id) not in ADMINS:
            return

        # Инлайн клавиатура тузиш
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Ҳайдовчи тасдиғи", callback_data="approve_panel")],
            [InlineKeyboardButton(text="📋 Буюртмалар", callback_data="view_order")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="statistika")],
            [InlineKeyboardButton(text="📁 Файлларни юклаш", callback_data="upload_files")]
        ])

        #await callback_query.message.answer("👮 Админ панел!", reply_markup=keyboard)
        await callback_query.message.edit_text("👮 Админ панел!", reply_markup=keyboard, parse_mode="Markdown")

    
    elif data == "upload_files":  # Агар "Файлларни юклаш" тугмаси босилса
        await send_json_files(callback_query.message)

    else:
        logging.warning(f"handlers/start.py Номаълум callback data: {data}")

    # Бу ерда "Матн ёки клавиатура ўзгармаган" хатоси бўлиши мумкин, шунга кўра, 
    # бу жавобни олишга уринишнинг ўзи бекор қилинган.
    try:
        await callback_query.answer("Сиз танладингиз: " + data)
    except TelegramBadRequest:
        pass  # "Message is not modified" ёки шунга ўхшаш хато чиқса, бекор қилинади

#@router.message(Command("admin"))
#async def admin_command(message: Message, state: FSMContext, bot: Bot):
#    user_id = message.from_user.id
#    if str(user_id) not in ADMINS:
#            return
#    await message.answer("👮 Админ панел!", reply_markup=start_kb(user_id))
#    #await message.edit_text("👮 Админ панел!", reply_markup=keyboard, parse_mode="Markdown")

from aiogram.types.input_file import FSInputFile

async def send_json_files(message):
    try:
        # Фойдаланувчиларни `.json` файлидан юклаш
        file = FSInputFile(USER_STATUS_PATH)
        await message.answer_document(file, caption="Фойдаланувчилар рўйхати")

        # Ҳайдовчиларни `.json` файлидан юклаш
        file = FSInputFile(DRIVER_PATH)
        await message.answer_document(file, caption="Ҳайдовчилар рўйхати")

        # Пасажирлар рўйхати
        file = FSInputFile(PASSENGER_PATH)
        await message.answer_document(file, caption="Пасажирлар рўйхати")

    except Exception as e:
        logging.error(f"Файлларни юклашда хатолик: {e}")
        await message.answer("Файлларни юклашда хатолик юз берди.")
