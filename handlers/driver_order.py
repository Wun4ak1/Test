# handlers/driver_order.py
from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils import (
    load_users, get_all_passenger_orders, get_driver_order,
    find_matching_passengers, send_or_edit_text
)
from datetime import datetime, timedelta
from states import OrderState
import logging

router = Router()

# example: handlers/driver_order.py
# 🛠 2. Манзилни танлаш (вилоят → туман) 🏘 Қайси тумандан йўлга чиқасиз? f"📍 *Қайси туманга борасиз?*"
# ✅ 1. Тасдиқлаш ёки Бекор қилиш (callback'лар)


# 🧾 Фақат мос йўналишдаги буюртмаларни чиқариш
@router.callback_query(F.data == "view_passenger_orders")
async def view_passenger_orders(callback: CallbackQuery):
    orders = get_all_passenger_orders()

    if not orders:
        await callback.message.answer("Йўловчи буюртмалари топилмади.")
        return

    text = "🧾 Барча йўловчи буюртмалари:\n\n"
    for order in orders:
        text += (
            f"📍 {order['from']} ➝ {order['to']}\n"
            f"📅 {order['date']} | ⏰ {order['time']}\n"
            f"№: {order['order_number']}\n\n"
        )

    await callback.message.answer(text)

@router.callback_query(lambda c: c.data.startswith("select_passenger_"))
async def show_passenger_info(callback_query: CallbackQuery):
    user_id = callback_query.data.split("_")[-1]
    users = load_users()

    user_data = users.get(user_id)
    if not user_data or "order" not in user_data:
        await callback_query.message.answer("Бу йўловчи маълумотлари топилмади.")
        return

    order = user_data["order"]
    order_text = (
        f"📍 Манзил: {order.get('from_district')} ➡ {order.get('to_district')}\n"
        f"🕔 Кетиш вақти: {order.get('time')}\n"
        f"📦 Буюртма №: {order.get('order_number')}"
    )

    contact_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Боғланиш", url=f"tg://user?id={user_id}")]
    ])

    await callback_query.message.answer(order_text, reply_markup=contact_button)

@router.callback_query(F.data.startswith("passenger_order_"))
async def show_passenger_order(callback_query: CallbackQuery):
    data = callback_query.data  # Масалан: "passenger_order_123456789_2"
    parts = data.split("_")

    if len(parts) < 4:
        await callback_query.message.answer("❌ Буюртма маълумотлари нотўғри.")
        return
    
    passenger_id = parts[2]
    order_index = parts[3]

    users = load_users()
    passenger_data = users.get(passenger_id, {})
    order_history = passenger_data.get("order_history", [])

    try:
        order = order_history[int(order_index)]
        from_district = order.get("from_district", "❓")
        to_district = order.get("to_district", "❓")
        date = order.get("date", "❓")
        time = order.get("time", "❓")
        order_number = order.get("order_number", "❓")

        message = (
            f"📦 Буюртма №{order_number}\n"
            f"🚏 Қаердан: {from_district}\n"
            f"🎯 Қаерга: {to_district}\n"
            f"📅 Кетиш санаси: {date}\n"
            f"🕰 Кетиш вақти: {time}"
        )
        await callback_query.message.answer(message)
    except (IndexError, ValueError):
        await callback_query.message.answer("❌ Буюртма топилмади.")

# ✅ 3. Ҳайдовчига мос йўловчиларни чиқариш:
@router.callback_query(F.data == "show_matching_passengers")
async def show_matching_passengers(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    driver_orders = get_driver_order(user_id)

    passengers = find_matching_passengers(driver_orders)

    if not passengers:
        await callback_query.message.answer("Ҳозирча мос келадиган йўловчилар йўқ.")
    else:
        text = "🚗 Мос йўловчилар:\n\n"
        for p in passengers:
            text += f"👤 ID: {p['user_id']}\n📍 {p['from']} ➡️ {p['to']}\n📅 {p['date']}, ⏰ {p['time']}\n\n"
        await callback_query.message.answer(text)

@router.message(lambda message: message.text == "👥 Мос йўловчилар")
async def show_matching_passengers(message: Message):
    user_id = str(message.from_user.id)
    driver_order = get_driver_order(user_id)

    if not driver_order:
        await message.answer("Сиз ҳали маршрут киритмагансиз.")
        return

    passengers = find_matching_passengers(driver_order)

    if not passengers:
        await message.answer("Ҳозирча мос келадиган йўловчилар йўқ.")
        return

    text = "🚘 Мос келадиган йўловчилар:\n\n"
    for p in passengers:
        text += f"📍 {p['from']} → {p['to']}\n🕒 {p['date']}\n🕒 {p['time']}\n📦 Буюртма №{p['order_number']}\n\n"

    await message.answer(text)

@router.callback_query(lambda c: c.data.startswith("departed_"))
async def handle_departure_response(callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    answer = data_parts[1]
    driver_id = data_parts[2]

    if answer == "yes":
        await callback_query.message.edit_text("✅ Сафарингиз муваффақиятли бошлангани учун раҳмат! Йўлингиз беминат бўлсин.")
        # Агар керак бўлса, базада `status`: 'on_way' ёки `departed_at` белгиси қўшиш мумкин
    else:
        await callback_query.message.edit_text("❌ Ҳали йўлга чиқмаганингиз қайд этилди. Илтимос, тайёр бўлганда маълум қилинг.")
