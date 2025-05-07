# handlers/start.py
import matplotlib.pyplot as plt
import logging
import json
from aiogram import Bot, Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.enums.parse_mode import ParseMode
from aiogram.utils.markdown import hbold, hitalic
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from datetime import datetime
import time
from zoneinfo import ZoneInfo

import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import TOKEN, INVITE_BONUS

ADMINS = os.getenv("ADMINS")
if ADMINS:
    ADMINS = {int(i) for i in ADMINS.split(",")}
else:
    ADMINS = set()

from states import DriverInfo, AdminStates
from keyboards.start_kb import start_kb
from keyboards.inline import invite_actions_kb
from utils import (
    load_json, save_json, load_users, save_user_status, 
    recommend_multiple_drivers_to_passenger, edit_selected_driver_message, delete_unselected_driver_messages, 
    get_passenger_order, load_passenger, send_or_edit_text, send_or_edit_last, 
    load_drivers, save_driver, load_passenger, save_passenger, create_departure_confirmation_keyboard,
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

    # ✅ Танланган тугмани "✅ Танланди" деб ўзгартириш
    keyboard = callback_query.message.reply_markup
    if keyboard:
        new_inline_keyboard = []

        for row in keyboard.inline_keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data == f"choose_driver_{driver_id}":
                    # 🎯 Фақат танланган тугмани "Танланди" қиламиз
                    new_inline_keyboard.append([
                        InlineKeyboardButton(text="✅ Танланди", callback_data="chosen_disabled"),
                        InlineKeyboardButton(text="🔁 Навбатдаги ҳайдовчилар", callback_data="show_next_drivers")
                    ])
                    break  # Танланган тугмадан кейин бошқа тугмалар керак эмас

        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=new_inline_keyboard)
        )

    # 🔴 Танланмаган ҳайдовчиларга юборилган хабарларни ўчириш
    await delete_unselected_driver_messages(passenger_id, driver_id, bot)

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
    #await callback_query.message.answer("✅ Ҳайдовчига хабар юборилди, агар 10 дақиқада жавоб бермаса, навбатдаги ҳайдовчилар юборилади.")
    await bot.send_message(driver_id, msg_to_driver, reply_markup=accept_btn)

    # Callback’га жавоб бериш (тугмани "pending" ҳолатдан чиқариш)
    await callback_query.answer()

    # 🕓 5 дақиқа кутиш ва кейин навбатдаги ҳайдовчига юбориш
    task = create_task(wait_for_driver_response(passenger_id, driver_id))
    pending_timers[passenger_id] = task

#@dp.callback_query_handler(lambda c: c.data == "chosen_disabled")
@router.callback_query(F.data == "chosen_disabled")
async def chosen_disabled_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("Бу ҳайдовчи танланган", show_alert=False)

@router.callback_query(F.data == "show_next_drivers")
async def show_next_drivers_callback(callback: CallbackQuery, bot: Bot):
    passenger_id = str(callback.from_user.id)
    try:
        # ⛔ Таймерни бекор қилиш
        task = pending_timers.pop(passenger_id, None)
        if task:
            task.cancel()

        # 🗃 Йўловчи маълумотини юклаймиз
        passengers = load_json(PASSENGER_PATH)
        passenger = passengers.get(passenger_id)
        if not passenger:
            return

        # 🚶‍♂️ Йўловчи ордери
        order = passenger.get("order", {})
        if not order:
            return

        # 🔁 exclude_driver_ids тайёрлаш
        excluded_ids = order.get("excluded_driver_ids", [])
        chosen_driver_id = order.get("chosen_driver_id")
        if chosen_driver_id:
            excluded_ids.append(chosen_driver_id)
            order["excluded_driver_ids"] = list(set(excluded_ids))  # Уникаллаштириш
            order["chosen_driver_id"] = None  # Бекор қилиш

        # 📝 Сақлаш
        passengers[passenger_id]["order"] = order
        save_json(PASSENGER_PATH, passengers)

        # 🔁 Яна ҳайдовчилар тавсия қилиш
        await recommend_multiple_drivers_to_passenger(
            passenger_id=passenger_id,
            user_order=order,
            bot=bot
        )

        # ✅ Callback жавобини ёпиш
        await callback.answer()

    except Exception as e:
        print(f"❌ show_next_drivers хатолик: {e}")
        await bot.send_message(passenger_id, "❌ Хатолик юз берди. Кейинроқ қайта уриниб кўринг.")

async def wait_for_driver_response(passenger_id, driver_id):
    await sleep(600)  # 5 дақиқа = 300 секунд

    passengers = load_json(PASSENGER_PATH)
    passenger = passengers.get(passenger_id)

    if not passenger:
        return

    order = passenger.get("order", {})
    
    # Агар йўловчи тасдиқ олмаган бўлса
    if order.get("chosen_driver_id") == driver_id:
        # 🟡 Танланмаган ҳайдовчилар рўйхатига қўшамиз
        excluded = order.get("excluded_driver_ids", [])
        if driver_id not in excluded:
            excluded.append(driver_id)
        order["excluded_driver_ids"] = excluded

        # ❌ Танловни бекор қиламиз
        order["chosen_driver_id"] = None

        # 🗂 Сақлаш
        passengers[passenger_id]["order"] = order
        save_json(PASSENGER_PATH, passengers)

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

    # ❗ Танланган ҳайдовчи текширилади
    chosen_driver_id = passenger.get("order", {}).get("chosen_driver_id")
    if chosen_driver_id != driver_id:
        await callback_query.answer("❌ Бу йўловчи сиз томонидан танланмаган. Ёки қабул қилишга кеч қолдингиз.", show_alert=True)
        return

    # 💸 Баланс/бонусдан 10% ҳисоблаймиз ва ушлаб қоламиз
    price = passenger['order'].get('price', 0)
    commission = round(price * 0.10)

    balance = driver.get("balance", 0)
    bonus = driver.get("bonus", 0)

    if balance + bonus < commission:
        await callback_query.answer(
            "❌ Балансингизда етарли маблағ йўқ. Йўловчини қабул қилиш учун илтимос балансни тўлдиринг.",
            show_alert=True
        )
        return

    if balance >= commission:
        driver["balance"] -= commission
    else:
        remaining = commission - balance
        driver["balance"] = 0
        driver["bonus"] -= remaining

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
        f"💰 Нарх: {passenger['order'].get('price', 'Номаълум')} сўм\n\n"
        f"Йўлга чиққанингизда тасдиқласангиз йўловчиларга билдиршнома юборамиз."
    )

    # 🛣 Йўлга чиқдим тугмаси ҳар сафар юборилади
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛣 Йўлга чиқдим", callback_data="on_the_way")]
    ])

    await send_or_edit_text(callback_query.message, full_info, reply_markup=reply_markup)

    # 🪑 Ҳайдовчида жой камайтирилади
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
    timestamp = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")

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
    timestamp = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")

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
    timestamp = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")

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
    timestamp = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")

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

@router.callback_query(F.data.startswith("user_detail:"))
async def show_user_detail(callback: CallbackQuery):
    user_id = callback.data.split(":")[1]
    
    # 📥 Маълумотларни юклаш
    users = load_users()
    passengers = load_passenger()
    drivers = load_drivers()

    user_info = users.get(user_id, {})
    passenger_info = passengers.get(user_id, {})
    driver_info = drivers.get(user_id, {})

    text = f"<b>👤 Фойдаланувчи ID:</b> <code>{user_id}</code>\n"

    if user_info:
        text += f"📌 Статус: {user_info.get('status', '❓')}\n"
        text += f"📛 Исм: {user_info.get('first_name', 'йўқ')}\n"

    if passenger_info:
        order = passenger_info.get("order")
        if order:
            text += "\n<b>🧍‍♂️ Йўловчи буюртмаси:</b>\n"
            for key, value in order.items():
                text += f"- {key}: {value}\n"

    if driver_info:
        order = driver_info.get("order")
        if order:
            text += "\n<b>🚗 Ҳайдовчи буюртмаси:</b>\n"
            for key, value in order.items():
                text += f"- {key}: {value}\n"

    if not passenger_info and not driver_info:
        text += "\nℹ️ Буюртма маълумотлари мавжуд эмас."

    await callback.message.answer(text, parse_mode="HTML")

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
    timestamp = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")

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

        now = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")
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
        is_first_time = user_id not in status_data
        #bot_username = (await callback_query.bot.me()).username

        if is_first_time:
            status_data[user_id] = {
                "status": "new_user",
                "referrer": referrer_id,
                "first_name": message.from_user.first_name,
                "timestamp": time.time()
            }

            # ✅ Админга хабар юбориш
            full_name = message.from_user.full_name
            username = message.from_user.username or "—"
            for admin_id in ADMINS:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔍 Подробно", callback_data=f"user_detail:{user_id}")]
                ])
                try:
                    await bot.send_message(
                        admin_id,
                        text=(
                            f"🆕 <b>Янги фойдаланувчи ботга кирди</b>\n\n"
                            f"👤 Исм: {full_name}\n"
                            f"🔗 Username: @{username if username != '—' else 'йўқ'}\n"
                            f"🆔 ID: <code>{user_id}</code>"
                        ),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"❌ Админга хабар юборишда хато: {e}")

            # Referrer маълумотларини янгилаш
            status_data.setdefault(referrer_id, {"status": "new_user"})
            status_data[referrer_id].setdefault("invited_users", [])
            if user_id not in status_data[referrer_id]["invited_users"]:
                status_data[referrer_id]["invited_users"].append(user_id)
            save_json(USER_STATUS_PATH, status_data)

            # ✅ BONUS бериш
            referrer_data = load_drivers().get(referrer_id)
            if referrer_data:
                referrer_data.setdefault("bonus", 0)
                referrer_data["bonus"] += INVITE_BONUS
                save_driver({**load_drivers(), referrer_id: referrer_data})

                invited_name = message.from_user.first_name
                text = (
                    f"🎉 Сиз таклиф қилган {invited_name} ботдан фойдалана бошлади!\n\n"
                    f"Сизга {INVITE_BONUS} сўм бонус тақдим этилди.\n\n"
                    "Яна дўстларингизни таклиф қилинг ва кўпроқ бонуслар тўпланг!"
                )
                await bot.send_message(
                    referrer_id,
                    text, 
                    reply_markup=await invite_actions_kb(bot, referrer_id)
                )

            else:
                # Рефер йўловчи бўлса
                passengers = load_passenger()
                if referrer_id in passengers:
                    passengers[referrer_id].setdefault("bonus", 0)
                    passengers[referrer_id]["bonus"] += INVITE_BONUS // 2
                    save_passenger(passengers)

                    invited_name = message.from_user.first_name

                    await bot.send_message(
                        referrer_id, 
                        text=(
                            f"🎉 Сиз таклиф қилган {invited_name} ботдан фойдалана бошлади!\n\n"
                            f"Сизга {INVITE_BONUS // 2} сўм бонус тақдим этилди.\n\n"
                            "Яна кўпроқ бонус олиш учун дўстларингизни таклиф қилинг!"
                        ),
                        reply_markup=await invite_actions_kb(bot, referrer_id)
                    )

        else:
            if "first_name" not in status_data[user_id]:
                status_data[user_id]["first_name"] = message.from_user.first_name
                save_json(USER_STATUS_PATH, status_data)

    else:
        # Агар referral бўлмаса ҳам, first_name сақлаб қўйиш
        if user_id not in status_data:
            status_data[user_id] = {
                "status": "new_user",
                "first_name": message.from_user.first_name,
                "timestamp": time.time()  # ⏱ биринчи уланган вақт
            }
            save_json(USER_STATUS_PATH, status_data)

            # 🔔 Админга хабар
            for admin_id in ADMINS:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔍 Подробно", callback_data=f"user_detail:{user_id}")]
                ])
                try:
                    await bot.send_message(
                        admin_id,
                        text=(
                            f"🆕 <b>Янги фойдаланувчи ботга кирди</b>\n\n"
                            f"👤 Исм: {message.from_user.full_name}\n"
                            f"🔗 Username: @{message.from_user.username or 'йўқ'}\n"
                            f"🆔 ID: <code>{user_id}</code>"
                        ),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"❌ Админга хабар юборишда хато: {e}")
        else:
            if "first_name" not in status_data[user_id]:
                status_data[user_id]["first_name"] = message.from_user.first_name
                save_json(USER_STATUS_PATH, status_data)

    # ➡️ Кейинги қисм:
    if user_status == "new_user":
        text = "🤖 Ботга хуш келибсиз!\nКимлигингизни танланг:"
        await send_or_edit_last(user_id, state, bot, text, start_kb(int(user_id)))
    else:
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

@router.callback_query(F.data == "my_invites")
async def show_my_invites(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    
    # 📁 Файлдан статуслар оламиз
    status_data = load_json(USER_STATUS_PATH)
    user_info = status_data.get(user_id, {})
    
    # Нечта дўст таклиф қилгани
    invited_users = user_info.get("invited_users", [])
    invited_count = len(invited_users)

    # Унинг статуси (driver / passenger)
    user_status = user_info.get("status", "Аниқланмаган")

    # 👥 Бонусни ҳисоблаш (иккала базадан)
    driver_data = load_json(DRIVER_PATH)
    passenger_data = load_json(PASSENGER_PATH)

    driver_bonus = driver_data.get(user_id, {}).get("bonus", 0)
    passenger_bonus = passenger_data.get(user_id, {}).get("bonus", 0)

    total_bonus = driver_bonus + passenger_bonus

    # Бонус маълумотини алоҳида файллардан оламиз
    bonus = 0
    if user_status == "new_user":
        user_status = "Янги фойдаланувчи"  # Янги фойдаланувчи бўлса, статусни ўзгартириб қўямиз
    elif user_status == "passenger":
        passenger_data = load_json(PASSENGER_PATH)
        bonus = passenger_data.get(user_id, {}).get("bonus", 0)
        user_status = "Йўловчи"  # Йўловчи бўлса, статусни ўзгартириб қўямиз
    elif user_status == "driver":
        driver_data = load_json(DRIVER_PATH)
        bonus = driver_data.get(user_id, {}).get("bonus", 0)
        user_status = "Ҳайдовчи"   # Ҳайдовчи бўлса, статусни ўзгартириб қўямиз
    else:
        user_status = "Аниқланмаган"

    # 📊 Асосий статистика
    text = (
        f"📊 Сизнинг статистика:\n\n"
        f"👤 Статус:  {user_status.capitalize()}\n"
        f"👥 Таклиф қилинган дўстлар сони:  {invited_count} та\n"
        f"🎁 Жами бонус:  <b>{total_bonus} сўм</b>\n"
    )

    # 👥 Агар таклиф қилинганлар бор бўлса, уларнинг исмларини чиқарамиз
    if invited_users:
        text += "\n🧑‍🤝‍🧑 Таклиф қилинганлар:\n"
        for idx, invited_id in enumerate(invited_users, 1):
            invited_info = status_data.get(str(invited_id), {})
            first_name = invited_info.get("first_name", "Номаълум")
            text += f"{idx}. {first_name}\n"
    else:
        text += "\n⏳ Ҳали дўст таклиф қилинмаган."

    await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()

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

PAGE_SIZE = 5  # Ҳар саҳифада 5 та йўловчи

def get_passenger_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⏪ Олдинги", callback_data=f"show_passengers_page_{page - 1}"))
    if page * PAGE_SIZE < total:
        buttons.append(InlineKeyboardButton(text="⏩ Кейингиси", callback_data=f"show_passengers_page_{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

@router.callback_query(F.data.startswith("show_passengers_list"))
@router.callback_query(F.data.startswith("show_passengers_page_"))
async def show_passengers_list(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS:
        return

    # Саҳифа рақамини аниқлаш
    data = callback_query.data
    if data == "show_passengers_list":
        page = 1
    else:
        try:
            page = int(data.replace("show_passengers_page_", ""))
        except ValueError:
            page = 1

    # Маълумотларни юклаш
    status_data = load_json(USER_STATUS_PATH)
    passengers = load_passenger()

    # Тартиблаш: timestamp бўйича (энг сўнги уланганлар юқорида)
    sorted_passenger_ids = sorted(
        passengers.keys(),
        key=lambda uid: status_data.get(uid, {}).get("timestamp", 0),
        reverse=True
    )

    # Кейин сортланганлардан рўйхат йиғилади
    passenger_items = [(uid, passengers[uid]) for uid in sorted_passenger_ids]
    #passenger_items = list(passengers.items())
    total = len(passenger_items)
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    if start >= total:
        await callback_query.message.answer("⛔️ Бу саҳифада йўловчилар йўқ.")
        return

    text = f"<b>🧍‍♂️ Йўловчилар рўйхати (саҳифа {page}):</b>\n\n"

    user_statuses = load_users()

    for idx, (passenger_id, passenger_data) in enumerate(passenger_items[start:end], start + 1):
        text += await format_passenger_display(bot, passenger_id, passenger_data, idx, user_statuses)

    keyboard = get_passenger_keyboard(page, total)

    try:
        await callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback_query.answer(text, parse_mode="HTML", reply_markup=keyboard)

# бугунги timestampни қўшиш функцияси
def add_missing_timestamps():
    status_data = load_users()  #: # load_json(USER_STATUS_PATH)
    current_time = int(time.time())  # бугунги timestamp
    #current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Сана сифатида

    modified = False
    for user_id, user_info in status_data.items():
        if "timestamp" not in user_info:
            user_info["timestamp"] = current_time
            modified = True

    if modified:
        save_json(USER_STATUS_PATH, status_data)
        print("✅ Timestamp'лар қўшилди.")
    else:
        print("ℹ️ Барча фойдаланувчиларда timestamp бор экан.")

async def format_passenger_display(bot, passenger_id: str, passenger_data: dict, index: int, user_statuses: dict):
    # 🧾 Telegram'дан маълумот олиш
    try:
        user = await bot.get_chat(passenger_id)
        full_name = user.full_name
        username = f"@{user.username}" if user.username else "–"
    except TelegramForbiddenError:
        full_name = "🚫 Аккаунт ўчирилган"
        username = "–"
    except Exception:
        full_name = "❓ Номаълум"
        username = "–"

    phone = passenger_data.get("phone", "–")
    bonus = passenger_data.get("bonus", 0)

    # timestamp — user_statuses.json орқали
    status_data = user_statuses.get(str(passenger_id), {})
    timestamp = status_data.get("timestamp")
    if timestamp:
        joined_at = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    else:
        joined_at = "—"

    # 🧮 Ҳисоблаш:
    # 1 ҳафта = 7 кун = 7 × 24 × 60 × 60 = 604800 секунд.
    # logging.info(f"User {passenger_id} timestamp: {timestamp}")

    return (
        f"{index}.  <b>{full_name}</b>\n"
        f"🆔  <code>{passenger_id}</code>\n"
        f"{username}\n"
        f"📞 Тел:  <b>{phone}</b>\n"
        f"🎁 Бонус:  <b>{bonus} сўм</b>\n"
        f"🗓 Уланган сана: <b>{joined_at}</b>\n"
        f"──────────────\n\n"
    )
    
@router.callback_query(lambda c: c.data in [
    "driver", "passenger", "change_user_status",
    "admin", "upload_files", "view_order", "view_order_passenger", "view_order_driver"
])
async def handle_callback(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data = callback_query.data

    logging.info(f"Callback data: {data}")  # Debug

    if data == "driver":
        save_user_status(user_id, "driver")
        await callback_query.message.edit_text("🚘 Ҳайдовчи учун меню:", reply_markup=start_kb(user_id))

    elif data == "passenger":
        save_user_status(user_id, "passenger")
        await callback_query.message.edit_text("🚘 Йўловчи учун меню:", reply_markup=start_kb(user_id))

    elif data == "change_user_status":
        save_user_status(user_id, "new_user")  # Статусни "new_user" га қайтарамиз
        #await callback_query.message.edit_reply_markup(reply_markup=None)  # Эски тугмаларни йўқ қиламиз
        await callback_query.message.edit_text("📋 Ролни қайта танланг:", reply_markup=start_kb(user_id))

    elif data == "admin":
        if user_id not in ADMINS:
        #if str(user_id) not in ADMINS:
            return

        stats = get_bot_statistics()  # ✅ Статистика
        
        drivers_count = stats.get("total_drivers", 0)
        passengers_count = stats.get("total_passengers", 0)
        driver_orders = stats.get("total_orders_drivers", 0)
        passenger_orders = stats.get("total_orders_passengers", 0)
        #total_income = stats.get("total_income", 0)
        #total_users = stats.get("total_users", 0)
        #total_feedbacks = stats.get("total_feedbacks", 0)
        #total_referrals = stats.get("total_referrals", 0)
        #total_bonus = stats.get("total_bonus", 0)
        #total_invited = stats.get("total_invited", 0)

        # Инлайн клавиатура тузиш
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Ҳайдовчи тасдиғи", callback_data="approve_panel")],
            [InlineKeyboardButton(text="📦 Доставка буюртмалари", callback_data="view_delivery_orders")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="statistika")],
            [InlineKeyboardButton(text=f"🚘 Ҳайдовчилар рўйхати ({drivers_count})", callback_data="show_drivers_list")],
            [InlineKeyboardButton(text=f"🚗 Ҳайдовчи ордерлари ({driver_orders})", callback_data="view_order_driver")],
            [InlineKeyboardButton(text=f"👥 Йўловчилар рўйхати ({passengers_count})", callback_data="show_passengers_list")],
            [InlineKeyboardButton(text=f"🧍‍♂️ Йўловчи ордерлари ({passenger_orders})", callback_data="view_order_passenger")],
            [InlineKeyboardButton(text="📁 Файлларни юклаш", callback_data="upload_files")]
        ])
    
        await callback_query.message.edit_text("👮 Админ панел!", reply_markup=keyboard, parse_mode="Markdown")

    elif data == "view_order":
        if user_id not in ADMINS:
            return
        # Админ учун охирги ордерларни кўрсатиш
        await show_recent_orders(callback_query.message, user_type="driver")  # ёки "passenger" керак бўлса
        #await show_recent_orders(callback_query.message, user_type="passenger")  # Йўловчиларнинг ордерларини кўрсатиш
        # Агар ҳайдовчиларнинг ордерларини кўрсатиш керак бўлса, "driver"ни ўрнатинг:
        # await show_recent_orders(callback_query.message, user_type="driver")

    elif data == "view_order_passenger":
        if user_id not in ADMINS:
            return
        # Йўловчи ордерларини кўрсатиш
        await show_recent_orders(callback_query.message, user_type="passenger")

    elif data == "view_order_driver":
        if user_id not in ADMINS:
            return
        # Ҳайдовчи ордерларини кўрсатиш
        await show_recent_orders(callback_query.message, user_type="driver")

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

@router.callback_query(lambda c: c.data == "admin_back_to_panel")
async def back_to_admin_panel(callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Ҳайдовчи тасдиғи", callback_data="approve_panel")],
        [InlineKeyboardButton(text="📦 Доставка буюртмалари", callback_data="view_delivery_orders")],
        [InlineKeyboardButton(text="📋 Буюртмалар", callback_data="view_order")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="statistika")],
        [InlineKeyboardButton(text="📅 Бугунги ордерлар", callback_data="today_orders")],
        [InlineKeyboardButton(text="🚘 Ҳайдовчилар рўйхати", callback_data="show_drivers_list")],
        [InlineKeyboardButton(text="🚗 Ҳайдовчи ордерлари", callback_data="view_order_driver")],
        [InlineKeyboardButton(text="👥 Йўловчилар рўйхати", callback_data="show_passengers_list")],
        [InlineKeyboardButton(text="🧍‍♂️ Йўловчи ордерлари", callback_data="view_order_passenger")],
        [InlineKeyboardButton(text="📁 Файлларни юклаш", callback_data="upload_files")]
    ])

    await callback_query.message.edit_text("👮 Админ панел!", reply_markup=keyboard)

@router.message(Command("change_status"))
@router.message(Command("change_role"))  # иккита вариант
async def change_status_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    save_user_status(user_id, "new_user")  # статусни қайта тиклаймиз
    await message.answer("📋 Ролни қайта танланг:", reply_markup=start_kb(user_id))

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


@router.callback_query(lambda c: c.data == "today_orders")
async def show_today_orders(callback: CallbackQuery):
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")  # 2025-05-05 каби форматда
        
        text = "📅 <b>Бугунги ордерлар</b>\n\n"

        # Йўловчи ордерлари
        with open(PASSENGER_PATH, "r", encoding="utf-8") as f:
            passengers = json.load(f)
        for user_id, user_data in passengers.items():
            order = user_data.get("order")
            if order and order.get("date") == today_str and order.get("status") != "done":
                text += f"🧍‍♂️ <b>Йўловчи:</b> {user_data.get('phone', 'Номаълум')}\n"
                text += f"📍 {order.get('from_district')} ➝ {order.get('to_district')}\n"
                text += f"⏰ {order.get('time')} | 💰 {order.get('price', '—')} сўм\n\n"

        # Ҳайдовчи ордерлари
        with open(DRIVER_PATH, "r", encoding="utf-8") as f:
            drivers = json.load(f)
        for user_id, user_data in drivers.items():
            order = user_data.get("order")
            if order and order.get("date") == today_str and order.get("status") != "done":
                profile = user_data.get("profile", {})
                text += f"🚗 <b>Ҳайдовчи:</b> {profile.get('name', 'Номаълум')}\n"
                text += f"📍 {order.get('from_district')} ➝ {order.get('to_district')}\n"
                text += f"⏰ {order.get('time')} | 🚘 {profile.get('car_model', '')} ({profile.get('car_number', '')})\n\n"

        if text.strip() == "📅 <b>Бугунги ордерлар</b>":
            text = "❌ Бугунги ордерлар топилмади."

        await callback.message.edit_text(text, parse_mode="HTML")

    except Exception as e:
        print(f"❌ Бугунги ордерлар хато: {e}")
        await callback.answer("❌ Хатолик юз берди.")

@router.callback_query(lambda c: c.data.startswith("order_details_"))
async def show_order_details(callback: CallbackQuery):
    try:
        _, user_type, user_id, order_number = callback.data.split("_", 3)
        user_id = str(user_id)
        order_number = int(order_number)

        file_path = DRIVER_PATH if user_type == "driver" else PASSENGER_PATH
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        user = data.get(user_id)
        if not user:
            await callback.answer("❌ Фойдаланувчи топилмади.")
            return

        order = user.get("order")
        if not order or order.get("order_number") != order_number:
            await callback.answer("❌ Ордер топилмади ёки янгиланган.")
            return

        profile = user.get("profile", {})
        phone = user.get("phone", "Номаълум")
        name = profile.get("name") if user_type == "driver" else phone  # Йўловчида profile йўқ

        text = f"📦 <b>Ордер №{order_number}</b>\n"
        text += f"👤 <b>Фойдаланувчи:</b> {name}\n"
        text += f"📞 <b>Телефон:</b> {phone}\n"
        text += f"🧑‍💼 <b>Тури:</b> {user_type.capitalize()}\n\n"

        text += (
            f"📍 <b>Йўналиш:</b> {order.get('from_region', '')}, {order.get('from_district', '')} ➝ "
            f"{order.get('to_region', '')}, {order.get('to_district', '')}\n"
            f"📅 <b>Сана:</b> {order.get('date', '—')} ⏰ {order.get('time', '—')}\n"
            f"💰 <b>Нарх:</b> {order.get('price', '—')} сўм\n"
            f"📊 <b>Статус:</b> {order.get('status', '—')}\n\n"
        )

        timestamps = order.get("status_timestamps", {})
        if timestamps:
            text += "🕓 <b>Вақтлар:</b>\n"
            for key, value in timestamps.items():
                text += f"▪️ {key.capitalize()}: {value}\n"

        back_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Орқага", callback_data=f"back_to_orders_{user_type}")]
        ])

        await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")

    except Exception as e:
        print(f"❌ Падробно хатолиги: {e}")
        await callback.answer("❌ Хатолик юз берди.")

@router.callback_query(lambda c: c.data.startswith("back_to_orders_"))
async def back_to_orders(callback: CallbackQuery):
    user_type = callback.data.split("_")[-1]
    await show_recent_orders(callback.message, user_type=user_type)

async def show_recent_orders(message, user_type):
    try:
        if user_type == "passenger":
            file_path = PASSENGER_PATH
        elif user_type == "driver":
            file_path = DRIVER_PATH
        else:
            await message.answer("❌ Нотўғри фойдаланувчи тури.")
            return

        with open(file_path, 'r', encoding='utf-8') as file:
            users_data = json.load(file)

        orders_text = "📝 Ордерлар рўйхати:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for user_id, user_data in users_data.items():
            order = user_data.get("order", {})
            if not order or order.get("status") == "done":
                continue

            if user_type == "passenger":
                phone = user_data.get("phone", "Номаълум")
                orders_text += (
                    f"🧍‍♂️ Телефон: {phone}\n"
                    f"📍 Йўналиш: {order.get('from_district')} ➝ {order.get('to_district')}\n"
                    f"💰 Нарх: {order.get('price', 'Номаълум')} сўм\n"
                    f"🕓 Вақт: {order.get('date')} {order.get('time')}\n\n"
                )
            elif user_type == "driver":
                profile = user_data.get("profile", {})
                name = profile.get("name", "Номаълум")
                orders_text += (
                    f"🚗 Ҳайдовчи: {name}\n"
                    f"📍 Йўналиш: {order.get('from_district')} ➝ {order.get('to_district')}\n"
                    f"📅 Сана: {order.get('date')} {order.get('time')}\n\n"
                )

            # Ордер тафсилоти тугмаси
            #order_number = order.get('order_number')
            #if order_number is None:
            #    continue

            #keyboard.inline_keyboard.append([
            #    InlineKeyboardButton(
            #        text=f"📦 Ордер №{order_number}",
            #        callback_data=f"order_details_{user_type}_{user_id}_{order.get('order_number')}"
            #    )
            #])

        if orders_text == "📝 Ордерлар рўйхати:\n\n":
            orders_text = "❌ Ордерлар топилмади."
            keyboard = None

        await message.answer(orders_text, reply_markup=keyboard)

    except Exception as e:
        print(f"❌ Хатолик: {e}")
        await message.answer("❌ Ордерлар кўрсатилмади.")


def get_bot_statistics():
    try:
        # Ҳамма фойдаланувчиларни юклаймиз
        users = load_users()
        
        with open(DRIVER_PATH, "r", encoding="utf-8") as f:
            drivers = json.load(f)
        with open(PASSENGER_PATH, "r", encoding="utf-8") as f:
            passengers = json.load(f)

        total_drivers = len(drivers)
        total_passengers = len(passengers)

        total_users = len(users)

        # Янги фойдаланувчилар сонини ҳисоблаш
        new_users_count = sum(1 for u in users.values() if u.get("status") == "new_user")

        total_orders_drivers = 0
        active_orders_drivers = 0
        for d in drivers.values():
            order = d.get("order")
            if order:
                total_orders_drivers += 1
                if order.get("status") != "done":
                    active_orders_drivers += 1

        total_orders_passengers = 0
        active_orders_passengers = 0
        for p in passengers.values():
            order = p.get("order")
            if order:
                total_orders_passengers += 1
                if order.get("status") != "done":
                    active_orders_passengers += 1

        total_orders = total_orders_drivers + total_orders_passengers
        active_orders = active_orders_drivers + active_orders_passengers

        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "active_orders": active_orders,
            "total_drivers": total_drivers,
            "total_passengers": total_passengers,
            "total_orders_drivers": total_orders_drivers,
            "active_orders_drivers": active_orders_drivers,
            "total_orders_passengers": total_orders_passengers,
            "active_orders_passengers": active_orders_passengers,
            "new_users": new_users_count
        }

    except Exception as e:
        print(f"❌ Статистика хато: {e}")
        return {
            "total_users": 0,
            "total_orders": 0,
            "active_orders": 0,
            "total_drivers": 0,
            "total_passengers": 0,
            "total_orders_drivers": 0,
            "active_orders_drivers": 0,
            "total_orders_passengers": 0,
            "active_orders_passengers": 0,
            "new_users": 0
        }

# "📋 Статистика"
@router.callback_query(F.data == "statistika")
async def show_statistics(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    # 📥 Барча маълумотларни юклаш
    stats = get_bot_statistics()
    users = load_users()
    #file_path = create_statistics_chart(stats)

    # 📊 Фойдаланувчи турлари бўйича ҳисоблаш
    new_users = sum(1 for u in users.values() if u.get("status") == "new_user")
    total_drivers = sum(1 for u in users.values() if u.get("status") == "driver")
    total_passengers = sum(1 for u in users.values() if u.get("status") == "passenger")


    text = (
        "<b>📊 Бот статистикаси</b>\n\n"
        f"👤 <b>Фойдаланувчилар сони:</b> {stats['total_users']} та\n\n"

        f"👤 <b>Янги фойдаланувчилар:</b> {new_users} та\n"
        f"🚗 Ҳайдовчилар: {total_drivers} та\n"
        f"🧍‍♂️ Йўловчилар: {total_passengers} та\n\n"

        f"📅 <b>Буюртмалар сони:</b> {stats['total_orders']} та\n"
        f"✅ Якунланган: {stats['total_orders'] - stats['active_orders']} та\n"
        f"⏳ Жорий: {stats['active_orders']} та\n\n"
        
        f"🚗 <b>Ҳайдовчилар:</b> {stats['total_drivers']} та\n"
        f"📦 Буюртмалар: {stats['total_orders_drivers']} та\n"
        f"⏳ Жараёнда: {stats['active_orders_drivers']} та\n\n"
        
        f"🧍‍♂️ <b>Йўловчилар:</b> {stats['total_passengers']} та\n"
        f"📦 Буюртмалар: {stats['total_orders_passengers']} та\n"
        f"⏳ Жараёнда: {stats['active_orders_passengers']} та"
    )

    await callback_query.message.answer(text, parse_mode="HTML")

    # 📈 Диаграммани юбориш
    #try:
    #    file_path = create_statistics_chart(stats)
    #    with open(file_path, "rb") as photo:
    #        await callback_query.message.answer_photo(photo, caption="📊 Диаграмма")
    #except Exception as e:
    #    logging.error(f"Диаграмма яратишда хатолик: {e}")
    #if file_path:
    #    chart = FSInputFile(file_path)
    #    await bot.send_photo(callback_query.from_user.id, photo=chart, caption="📊 Диаграмма")

def create_statistics_chart(stats):
    try:
        labels = ['Буюртмалар', 'Йўловчилар', 'Ҳайдовчилар']
        values = [stats['total_orders'], stats['total_passengers'], stats['total_drivers']]
        colors = ['#4caf50', '#2196f3', '#ff9800']

        plt.figure(figsize=(7, 4))
        bars = plt.bar(labels, values, color=colors)
        plt.title("Бот статистикаси", fontsize=14)
        plt.ylabel("Сони")

        # Бар устидан рақамларни кўрсатиш
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, int(yval), ha='center', va='bottom')

        plt.tight_layout()
        file_path = "chart.png"
        plt.savefig(file_path)
        plt.close()
        return file_path
    except Exception as e:
        logging.error(f"Диаграмма яратишда хатолик: {e}")
        return None
