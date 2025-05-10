# handlers/created_by_admin_order.py  Манзил, вилоят, сана ва вақтни танлаш билан боғлиқ умумий функциялар
import json
from aiogram import Router, Bot, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from utils import (
    load_orders, get_order, save_order, save_driver_order, save_passenger_order, get_driver_order, get_passenger_order,
    send_or_edit_text, recommend_multiple_drivers_to_passenger, is_match, 
    load_drivers, DRIVER_PATH, PASSENGER_PATH
)
from common_order import (
    create_from_region_keyboard, create_from_district_keyboard, 
    create_to_region_keyboard, create_to_district_keyboard, 
    create_day_keyboard, create_time_keyboard, check_existing_order, SLUG_TO_REGION, SLUG_TO_DISTRICT, TIME_SLOTS
)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from states import EditOrder
import logging

router = Router()

def generate_order_preview(order: dict, highlight: str = "") -> str:
    def bold_if(field, text):
        return f"**{text}** ✏️" if highlight == field else text

    price_text = ""
    if order.get("user_type") == "passenger":
        price = order.get("price")
        if price is not None:
            price_text = bold_if('price', f"\n💰 Нарх: {price:,} сўм")  # Vergul bilan formatlangan

    return (
        f"*Буюртма таҳрирланди!*\n\n"
        f"{bold_if('from', f'📍 Қайердан: {order.get('from_region', '')} - {order.get('from_district', '')}')}\n"
        f"{bold_if('to', f'📍 Қайерга: {order.get('to_region', '')} - {order.get('to_district', '')}')}\n"
        f"{bold_if('date', f'📅 Санаси: {order.get('date', '')}')}\n"
        f"{bold_if('time', f'⏰ Вақти: {order.get('time', '')}')}"
        f"{price_text}"
    )

def format_order_with_edit_buttons(order):
    price_text = ""
    if order.get("user_type") == "passenger":
        price = order.get("price")
        if price is not None:
            price_text = f"\n💰 Нарх: {price:,} сўм"

    text = (
        f"🚘 Буюртма маълумотлари:\n\n"
        f"📍 Қайси ҳудуддан: {order.get('from_region', '—')} / {order.get('from_district', '—')}\n"
        f"📍 Қайси ҳудудга: {order.get('to_region', '—')} / {order.get('to_district', '—')}\n"
        f"📅 Сана: {order.get('date', '—')}\n"
        f"⏰ Вақт: {order.get('time', '—')}"
        f"{price_text}"
    )
    return text

def create_edit_order_keyboard(order: dict) -> InlineKeyboardMarkup:
    user_type = order.get("user_type", "driver")  # ёки passenger, default driver деб қўйилган

    buttons = [
        [InlineKeyboardButton(
            text=f"📍 Қайердан: {order.get('from_region', '')} - {order.get('from_district', '')}", 
            callback_data=f"{user_type}_edit_from_location")],
        [InlineKeyboardButton(
            text=f"📍 Қайерга: {order.get('to_region', '')} - {order.get('to_district', '')}", 
            callback_data="edit_to_location")],
        [InlineKeyboardButton(
            text=f"📅 Санаси: {order.get('date', '')}", 
            callback_data="edit_date")],
        [InlineKeyboardButton(
            text=f"⏰ Вақти: {order.get('time', '')}", 
            callback_data="edit_time")]
    ]

    # 👉 Агар йўловчи бўлса, НАРХ тахрирлаш кнопкаси қўшамиз
    if order.get("user_type") == "passenger":
        buttons.append([
            InlineKeyboardButton(
                text=f"💰 Нарх: {order.get('price', '—')} сўм",
                callback_data="edit_price")
        ])

    buttons.append([
        InlineKeyboardButton(
            text="❌ Бекор қилиш",
            callback_data=f"{user_type}_edit_cancel_edit")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def utype(raw): return "passenger" if raw.startswith("p") else "driver"

@router.callback_query(F.data.in_({"passenger_edit_order", "driver_edit_order"}))
async def handle_edit_order_menu(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    user_type = "passenger" if callback.data.startswith("passenger") else "driver"
    # print(f"handle_edit_order_menu callback.data: {callback.data}")

    # ❗️ Бу ерда қўшиш керак:
    should_stop = await check_existing_order(callback, user_id, user_type, is_editing=True)
    if should_stop:
        return
    
    orders = load_orders(user_type)
    order = orders.get(user_id, {}).get("order")
    # print(f"handle_edit_order_menu: user_id={user_id}, user_type={user_type}, order={order}") #, orders={orders}")

    if not order:
        await callback.message.answer(f"Сизнинг фаол буюртмангиз йўқ, {user_type}.")
        return

    text = format_order_with_edit_buttons(order)
    keyboard = create_edit_order_keyboard(order)

    # Сохраняем user_type в состояние
    await state.update_data(user_type=user_type)

    await send_or_edit_text(
        callback.message,
        text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    #await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

#@router.callback_query(F.data == "_edit_from_location")
@router.callback_query(F.data.in_({"passenger_edit_from_location", "driver_edit_from_location"}))
async def handle_edit_from_location(callback_query: CallbackQuery, state: FSMContext):
    user_id = str(callback_query.from_user.id)

    # callback_query.data фақат "_edit_from_location" бўлса, user_type'ни state'дан оламиз
    data = await state.get_data()
    user_type = data.get("user_type")  # "passenger" ёки "driver"

    orders = load_orders(user_type)
    order = orders.get(user_id, {}).get("order")
    # print(f"handle_edit_from_location: user_id={user_id}, user_type={user_type}") #, order={order}, orders={orders}")

    if not order:
        await callback_query.message.answer("handle_edit_from_location Сизнинг фаол буюртмангиз йўқ, {user_type}.")
        return

    # Керакли маълумотларни state га сақлаб қўйиш
    await state.update_data(
        to_region=order.get("to_region"),
        to_district=order.get("to_district"),
        user_type=user_type
    )

    # Создаем клавиатуру для выбора нового региона
    keyboard = create_from_region_keyboard(
        user_type,                     # u
        order.get("to_region"),        # to_r
        order.get("to_district"),      # to_d
        edit=True                      # edit
    )
    await callback_query.message.edit_text("✏️ *Қайси Вилоятдан кетасиз?* 📍", reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(lambda c: "_efr_" in c.data)
async def edit_from_region(cb: CallbackQuery, state: FSMContext):
    raw, rslug = cb.data.split("_efr_")
    user_type = utype(raw)
    region = SLUG_TO_REGION[rslug]
    user_id = str(cb.from_user.id)

    orders = load_orders(user_type)
    order = (orders.get(user_id) or {}).get("order")
    if not order:
        await cb.answer("❌ Буйрутма топилмади", show_alert=True); return

    await state.update_data(from_region=region, to_region=order["to_region"], to_district=order["to_district"])

    kb = create_from_district_keyboard(user_type, order["to_region"], order["to_district"], region, edit=True)
    await cb.message.edit_text(f"📍 *{region}* — туманни танланг:", reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(lambda c: "_efd_" in c.data)
async def edit_from_district(cb: CallbackQuery, state: FSMContext):
    raw, dslug = cb.data.split("_efd_")
    user_type = utype(raw)
    district = SLUG_TO_DISTRICT[dslug]

    data = await state.get_data()
    region = data.get("from_region")

    await state.update_data(from_district=district)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Тасдиқлаш",
            callback_data=f"{user_type}_confirm_edit_from"
        ),
        InlineKeyboardButton(
            text="❌ Бекор қилиш",
            callback_data=f"{user_type}_cancel_edit"
        )
    ]])

    await cb.message.edit_text(f"📍 *Кетиш ҳудуди:* {region} / {district}", reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data == "edit_to_location")
async def handle_edit_to_location(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)

    data = await state.get_data()
    user_type = data.get("user_type")  # oldindan saqlab qo‘yilgan bo‘lishi kerak

    if not user_type:
        await callback.message.answer("Илтимос, аввал буюртма яратинг.")
        return
    
    #user_type = "passenger" if callback.data.startswith("passenger") else "driver"

    orders = load_orders(user_type)
    order = orders.get(user_id, {}).get("order")

    if not order:
        await callback.message.answer("Сизнинг фаол буюртмангиз йўқ.")
        return

    await state.update_data(to_region=order.get("to_region"), to_district=order.get("to_district"))

    keyboard = create_to_region_keyboard(user_type, True)

    await callback.message.edit_text("✏️ *Қайси Ҳудудга борасиз?* 📍", reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(lambda c: "_etr_" in c.data)
async def edit_to_region(cb: CallbackQuery, state: FSMContext):
    raw, rslug = cb.data.split("_etr_")
    user_type = utype(raw)
    region = SLUG_TO_REGION[rslug]
    await state.update_data(to_region=region)

    kb = create_to_district_keyboard(user_type, region, edit=True)
    await cb.message.edit_text(f"📍 *Борадиган вилоят:* {region}\n\nТуманни танланг:", reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(lambda c: "_etd_" in c.data)
async def edit_to_district(cb: CallbackQuery, state: FSMContext):
    raw, dslug = cb.data.split("_etd_")
    user_type = utype(raw)
    district = SLUG_TO_DISTRICT[dslug]
    region = (await state.get_data()).get("to_region")

    await state.update_data(to_district=district)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"{user_type}_confirm_edit_to"),
        InlineKeyboardButton(text="❌ Бекор қилиш", callback_data=f"{user_type}_cancel_edit")
    ]])
    await cb.message.edit_text(f"📍 *Борадиган ҳудуд:* {region} / {district}", reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data == "edit_date")
async def handle_edit_date(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    #user_type = "passenger" if callback.data.startswith("passenger") else "driver"

    data = await state.get_data()
    user_type = data.get("user_type")

    orders = load_orders(user_type)
    order = orders.get(user_id, {}).get("order")
    #print(f"handle_edit_date: user_id={user_id}, user_type={user_type}, order={order}")
    
    if not order:
        await callback.message.answer("Сизнинг фаол буюртмангиз йўқ.")
        return

    await state.update_data(
        to_region=order.get("to_region"), 
        to_district=order.get("to_district"),
        from_region=order.get("from_region"),
        from_district=order.get("from_district")
    )

    keyboard = create_day_keyboard(
        user_type,                    # 1‑параметр
        order["to_region"],           # 2
        order["to_district"],         # 3
        order["from_region"],         # 4
        order["from_district"],       # 5
        True                          # edit=True
    )

    await callback.message.edit_text("✏️ *Қайси Куни кетасиз?*", reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(lambda c: "_ed_" in c.data)   # p_ed_today, d_ed_other, ...
async def edit_date(cb: CallbackQuery, state: FSMContext):
    raw, day_key = cb.data.split("_ed_")
    user_type = utype(raw)

    # «custom» бўлса – қўлдан сана киритиш
    if day_key == "custom":
        await cb.message.answer("📅 Сана киритинг (Йил-Ой-Кун, масалан: 2025-05-30):")
        await state.update_data(user_type=user_type)
        await state.set_state(EditOrder.waiting_for_custom_date)
        await cb.answer(); return

    # «today / tomorrow / other»
    today = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    selected = today if day_key == "today" else \
               today + timedelta(days=1) if day_key == "tomorrow" else None

    if selected:
        await state.update_data(date=selected.strftime("%Y-%m-%d"))

    text = f"📅 *Танланган сана:* {selected if selected else 'Бошқа кун'}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"{user_type}_confirm_edit_date"),
        InlineKeyboardButton(text="❌ Бекор қилиш", callback_data=f"{user_type}_cancel_edit")
    ]])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data == "edit_time")
async def handle_edit_time(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    # user_type = "passenger" if callback.data.startswith("passenger") else "driver"

    data = await state.get_data()
    user_type = data.get("user_type")

    orders = load_orders(user_type)
    order = orders.get(user_id, {}).get("order")

    if not order:
        await callback.message.answer("Сизнинг фаол буюртмангиз йўқ.")
        return

    await state.update_data(
        to_region=order.get("to_region"), 
        to_district=order.get("to_district"),
        from_region=order.get("from_region"),
        from_district=order.get("from_district"),
        date=order.get("date")
    )

    current_order = {
        "to_region": order.get("to_region"),
        "to_district": order.get("to_district"),
        "from_region": order.get("from_region"),
        "from_district": order.get("from_district"),
        "date": order.get("date")
    }

    keyboard = create_time_keyboard(
        current_order, 
        user_type,
        True  # Мухим
    )
    await callback.message.edit_text("✏️ *Қайси Вақтда кетасиз?*", reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(lambda c: "_et_" in c.data)        # p_et_evening  /  d_et_morning
async def edit_time(cb: CallbackQuery, state: FSMContext):
    raw, time_key = cb.data.split("_et_")
    user_type = utype(raw)

    time_range = TIME_SLOTS.get(time_key, (None, "00:00 - 00:00"))[1]   # "06:00 - 11:59"
    await state.update_data(time=time_range)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"{user_type}_confirm_edit_time"),
        InlineKeyboardButton(text="❌ Бекор қилиш", callback_data=f"{user_type}_cancel_edit")
    ]])
    await cb.message.edit_text(f"⏰ *Танланган вақт:* {time_range}", reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.message(EditOrder.waiting_for_custom_date)
async def save_custom_date(msg: Message, state: FSMContext):
    try:
        sel_date = datetime.strptime(msg.text.strip(), "%Y-%m-%d").date()
    except ValueError:
        await msg.answer("❌ Формат нотўғри. Йил-Ой-Кун тарзда киритинг, масалан 2025-05-30.")
        return

    data = await state.get_data()
    user_type = data.get("user_type", "passenger")
    await state.update_data(date=sel_date.strftime("%Y-%m-%d"))
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"{user_type}_confirm_edit_date"),
        InlineKeyboardButton(text="❌ Бекор қилиш", callback_data=f"{user_type}_cancel_edit")
    ]])
    await msg.answer(f"📅 *Танланган сана:* {sel_date}", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "edit_price")
async def handle_edit_price(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    data = await state.get_data()
    user_type = data.get("user_type", "passenger")

    price = data.get("price", 100000)  # Агар state да бўлмаса, 100,000 деб оламиз
    await state.update_data(price=price)

    keyboard = create_price_edit_keyboard(price, user_type)
    await callback.message.edit_text(
        f"💰 Нарх: {price:,} сўм\n\n➖ ёки ➕ тугмалар орқали ўзгартиринг:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

def create_price_edit_keyboard(price: int, user_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 {price:,} сўм", callback_data="noop")],
            [
                InlineKeyboardButton(text="➖ 1000", callback_data=f"{user_type}_price_minus_1000"),
                InlineKeyboardButton(text="➕ 1000", callback_data=f"{user_type}_price_plus_1000")
            ],
            [
                InlineKeyboardButton(text="➖ 10000", callback_data=f"{user_type}_price_minus_10000"),
                InlineKeyboardButton(text="➕ 10000", callback_data=f"{user_type}_price_plus_10000")
            ],
            [InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"{user_type}_confirm_edit_price")]
        ]
    )

@router.callback_query(lambda c: "_price_minus_" in c.data or "_price_plus_" in c.data)
async def adjust_price(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_type = data.get("user_type")
    price = data.get("price", 0)

    action = callback.data.split(f"{user_type}_")[1]  # "price_minus_1000" ёки "price_plus_10000"
    if "minus" in action:
        amount = int(action.split("_")[-1])
        price = max(0, price - amount)
    elif "plus" in action:
        amount = int(action.split("_")[-1])
        price += amount

    # Agar narx 0 bolsa ogohlantirish
    if price == 0:
        await callback.answer("❗ Илтимос, нархни киритинг.", show_alert=True)

    # Yangilangan narxni saqlaymiz
    await state.update_data(price=price)

    keyboard = create_price_edit_keyboard(price, user_type)
    await callback.message.edit_text(
        text="💰 *Нархни ўзгартириш:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(lambda c: "_confirm_edit_" in c.data or c.data.endswith("_confirm_edit"))
async def confirm_edit_field(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    state_data = await state.get_data()
    user_id = str(state_data.get("user_id", callback_query.from_user.id))  # ✅ админ учун
    created_by_admin = state_data.get("created_by_admin", False)

    #user_id = callback_query.from_user.id
    #data = await state.get_data()

    # Мисол: "driver_confirm_edit_to" → "driver", "to"
    parts = callback_query.data.split("_confirm_edit")

    user_type_raw = parts[0]  # "driver_edit" ёки "passenger"
    field = parts[1][1:] if len(parts) > 1 else None  # "from", "to", "date", ...

    user_type = user_type_raw.split("_")[0]

    # Маълумотларни state дан оламиз
    updates = {}
    highlight = None

    if field == "from":
        updates["from_region"] = data.get("from_region")
        updates["from_district"] = data.get("from_district")
        highlight = "from"
    elif field == "to":
        updates["to_region"] = data.get("to_region")
        updates["to_district"] = data.get("to_district")
        highlight = "to"
    elif field == "date":
        updates["date"] = data.get("date")
        updates["day"] = data.get("day")
        highlight = "date"
    elif field == "time":
        updates["time"] = data.get("time")
        highlight = "time"
    elif field == "price":
        updates["price"] = data.get("price")
        highlight = "price"
    # Қўшимча майдонлар бўлса, шу ерга қўшиш

    # Order ни сақлаш
    if user_type == "driver":
        save_driver_order(user_id, updates)
        order = get_driver_order(user_id)
    else:
        save_passenger_order(user_id, updates)
        order = get_passenger_order(user_id)

    await state.clear()

    # 🧠 Тавсия логикаси
    if user_type == "passenger":
        await recommend_multiple_drivers_to_passenger(
            passenger_id=user_id,
            user_order=order,
            bot=bot
        )
    elif user_type == "driver":
        with open(PASSENGER_PATH, 'r', encoding='utf-8') as file:
            all_passengers = json.load(file)

        for p_id, p_data in all_passengers.items():
            passenger_order = p_data.get("order", {})
            if not passenger_order:
                continue

            if is_match(order, passenger_order) and p_data.get("status") != "arrived":
                await recommend_multiple_drivers_to_passenger(
                    passenger_id=p_id,
                    user_order=passenger_order,
                    bot=bot
                )

    # 📋 Янгиланган маълумотни қайтариш
    text = generate_order_preview(order, highlight=highlight)
    keyboard = create_edit_order_keyboard(order)

    await callback_query.message.edit_text(text, reply_markup=None, parse_mode="Markdown")

@router.callback_query(lambda c: "_cancel_edit" in c.data)
async def cancel_edit(callback_query: CallbackQuery, state: FSMContext):
    # Ҳар қандай ўзгаришларни бекор қилиш
    await state.clear()
    #await state.finish()

    #text = "❌ Таҳрирлаш бекор қилинди."
    #await callback_query.message.edit_text(text, reply_markup=create_edit_order_keyboard, parse_mode="Markdown")
    await callback_query.message.edit_text("❌ Таҳрирлаш бекор қилинди.")


@router.callback_query(F.data == "confirm_edit_from_location", EditOrder.confirm_from)
async def confirm_from_location(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = call.from_user.id

    order = get_order(user_id)
    order["from_region"] = data.get("from_region")
    order["from_district"] = data.get("from_district")

    save_order(user_id, order)

    await state.clear()
    await call.message.edit_text("✅ Манзил янгиланди.", reply_markup=create_edit_order_keyboard(order))
