# handlers/common_order.py  Манзил, вилоят, сана ва вақтни танлаш билан боғлиқ умумий функциялар
import json
import os
from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from location import REGIONS_AND_DISTRICTS, calculate_price
from utils import (
    load_orders, load_passenger, load_drivers, get_driver_order, get_passenger_order, save_order,
    save_driver_order, save_passenger_order, send_or_edit_text, is_time_match, get_user_status,
    save_driver_order_history, clear_driver_order, save_passenger_order_history, clear_passenger_order, DRIVER_PATH, PASSENGER_PATH
)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
from unidecode import unidecode     # pip install Unidecode
from states import OrderState
import logging

router = Router()

# Вилоятларни рўйхат қилиб олиш:
regions = list(REGIONS_AND_DISTRICTS.keys())

# Фор билан айлантириш:
for region in regions:
#    print(f"Вилоят: {region}")
    for district in REGIONS_AND_DISTRICTS[region]:
#        print(f"  - Туман: {district}")
        pass

def parse_user_type(callback_data: str) -> str:
    if callback_data.startswith("driver_edit") or callback_data.startswith("driver_"):
        return "driver"
    elif callback_data.startswith("passenger_edit") or callback_data.startswith("passenger_"):
        return "passenger"
    else:
        return "unknown"

def slugify(t): return unidecode(t).replace("'", "").replace(" ", "_").lower()

REGION_TO_SLUG = {r: slugify(r) for r in REGIONS_AND_DISTRICTS}
SLUG_TO_REGION = {v: k for k, v in REGION_TO_SLUG.items()}

DISTRICT_TO_SLUG, SLUG_TO_DISTRICT = {}, {}
for r, ds in REGIONS_AND_DISTRICTS.items():
    for d in ds:
        s = slugify(d)
        DISTRICT_TO_SLUG[(r, d)] = s
        SLUG_TO_DISTRICT[s] = d
# -----------------------------------------------
# helpers to build callback
# -----------------------------------------------
def cb(p, *parts): return f"{p}_{'_'.join(parts)}"

# p/d       = passenger / driver  (бир ҳарф)
# etr/efd   = edit_to_region / edit_from_district ва ҳ.к.
# tr/td/fr/fd = to_region, to_district, from_region, from_district
# -----------------------------------------------
@router.callback_query(F.data == "go_back_step")
async def go_back_step(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback_query.from_user.id
    user_type = data.get("user_type", "driver")  # default to driver

    # ❓ Қайси босқичдамиз
    if "to_district" in data:
        # Тумандан → Вилоятга
        region = data["to_region"]
        reply_markup = create_to_district_keyboard(user_type, region)
        await send_or_edit_text(
            callback_query.message,
            f"📍 Йўналиш: *{region}*\n\n📍 *Қайси ТУМАНГА борасиз?*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        await state.update_data(to_district=None)  # орқага қайтганда ўчириб қўямиз

    elif "to_region" in data:
        # Вилоятдан → бошланғичга
        reply_markup = create_to_region_keyboard(user_type)
        await send_or_edit_text(
            callback_query.message,
            "📍 *Қайси ҲУДУДГА борасиз?*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        await state.update_data(to_region=None)

    elif "from_district" in data:
        from_region = data.get("from_region")
        to_r = data.get("to_region")
        to_d = data.get("to_district")
        reply_markup = create_from_district_keyboard(user_type, to_r, to_d, from_region)
        await send_or_edit_text(
            callback_query.message,
            f"📍 Йўналиш: {to_r} / {to_d}\n📍 Қайси МАҲАЛЛАДАН кетасиз?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        await state.update_data(from_district=None)

    elif "from_region" in data:
        to_r = data.get("to_region")
        to_d = data.get("to_district")
        reply_markup = create_from_region_keyboard(user_type, to_r, to_d)
        await send_or_edit_text(
            callback_query.message,
            f"📍 Йўналиш: {to_r} / {to_d}\n📍 *Қайси ВИЛОЯТДАН кетасиз?*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        await state.update_data(from_region=None)

    elif "date" in data:
        to_r = data.get("to_region")
        to_d = data.get("to_district")
        from_r = data.get("from_region")
        from_d = data.get("from_district")
        reply_markup = create_day_keyboard(user_type, to_r, to_d, from_r, from_d)
        await send_or_edit_text(
            callback_query.message,
            "📅 *Қайси кунга кетасиз?*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        await state.update_data(date=None)

    elif "time" in data:
        reply_markup = create_time_keyboard(data, user_type)
        await send_or_edit_text(
            callback_query.message,
            "⏰ *Қайси вақт оралиғида кетасиз?*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        await state.update_data(time=None)

    else:
        # Бошқа ҳолат: бошидан бошлаймиз
        reply_markup = create_to_region_keyboard(user_type)
        await send_or_edit_text(
            callback_query.message,
            "📍 *Қайси ҲУДУДГА борасиз?*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

@router.callback_query(lambda c: c.data == "BACK_TO_PREV")
async def go_back_step(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prev_step = data.get("prev_step")
    user_type = data.get("user_type")
    user_id = callback_query.from_user.id

    if prev_step == "choose_to_region":
        reply_markup = create_to_region_keyboard(user_type)
        await state.update_data(prev_step=None)  # энди бошланғич ҳолат
        await send_or_edit_text(callback_query.message,
                                "📍 *Қайси ҲУДУДГА борасиз?*",
                                reply_markup=reply_markup,
                                parse_mode="Markdown")

    elif prev_step == "choose_to_district":
        region = data.get("to_region")
        reply_markup = create_to_district_keyboard(user_type, region)
        await state.update_data(prev_step="choose_to_region")
        await send_or_edit_text(callback_query.message,
                                f"📍 Йўналиш: *{region}*\n\n📍 *Қайси ТУМАНГА борасиз?*",
                                reply_markup=reply_markup,
                                parse_mode="Markdown")

    elif prev_step == "choose_from_region":
        to_region = data.get("to_region")
        to_district = data.get("to_district")
        reply_markup = create_from_region_keyboard(user_type, to_region, to_district)
        await state.update_data(prev_step="choose_to_district")
        await send_or_edit_text(callback_query.message,
                                f"📍 Йўналиш: {to_region} / *{to_district}*\n\n📍 *Қайси ВИЛОЯТДАН кетасиз?*",
                                reply_markup=reply_markup,
                                parse_mode="Markdown")

    else:
        await callback_query.answer("🔙 Орқага қайтиш мумкин эмас.", show_alert=True)

# 1. ▼ TO REGION
def create_to_region_keyboard(u, edit=False):
    cnt = count_orders_to_region(u, "to")
    pref = f"{u[0]}_{'etr' if edit else 'tr'}"
    btns = [InlineKeyboardButton(
              text = f"{r} ({cnt.get(r,0)})" if cnt.get(r,0) else f"{r}",
              callback_data=cb(pref, REGION_TO_SLUG[r])
           ) for r in REGIONS_AND_DISTRICTS]
    
    rows = [btns[i:i+3] for i in range(0, len(btns), 3)]
#    if not edit:
#        rows.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="BACK_TO_PREV")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# 1. count_orders_to_region
def count_orders_to_region(user_type: str, direction: str):
    orders = load_drivers() if user_type == "passenger" else load_passenger()
    region_key = "to_region" if direction == "to" else "from_region"

    count_by_region = {}
    for order in orders.values():
        order_data = order.get("order", order)
        region = order_data.get(region_key)
        if region:
            count_by_region[region] = count_by_region.get(region, 0) + 1

    return count_by_region

# 2. ▼ TO DISTRICT
def create_to_district_keyboard(u, region, edit=False):
    cnt = count_orders_to_district(u,"to",region)
    pref = f"{u[0]}_{'etd' if edit else 'td'}"
    btns=[InlineKeyboardButton(
            text = f"{d} ({cnt.get(f'{region}_{d}',0)})" if cnt.get(f'{region}_{d}',0) else f"{d}",
            callback_data=cb(pref, DISTRICT_TO_SLUG[(region,d)])
         ) for d in REGIONS_AND_DISTRICTS[region]]

    rows = [btns[i:i+3] for i in range(0, len(btns), 3)]
    if not edit:
        rows.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="BACK_TO_PREV")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# 2. count_orders_to_district
def count_orders_to_district(user_type: str, direction: str, to_region: str):
    orders = load_drivers() if user_type == "passenger" else load_passenger()
    region_key = "to_region" if direction == "to" else "from_region"
    district_key = "to_district" if direction == "to" else "from_district"

    count_by_district = {}
    for order in orders.values():
        order_data = order.get("order", order)
        if order_data.get(region_key) != to_region:
            continue

        district = order_data.get(district_key)
        key = f"{to_region}_{district}"
        if district:
            count_by_district[key] = count_by_district.get(key, 0) + 1

    return count_by_district

# 3. ▼ FROM REGION
def create_from_region_keyboard(u, to_r, to_d, edit=False):
    cnt = count_orders_from_region(u,to_r,to_d)
    pref = f"{u[0]}_{'efr' if edit else 'fr'}"
    btns=[InlineKeyboardButton(
            text = f"{r} ({cnt.get(r,0)})" if cnt.get(r,0) else f"{r}",
            callback_data=cb(pref, REGION_TO_SLUG[r])
         ) for r in REGIONS_AND_DISTRICTS]

    rows = [btns[i:i+3] for i in range(0, len(btns), 3)]
    if not edit:
        rows.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="BACK_TO_PREV")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# 3. count_orders_from_region
def count_orders_from_region(user_type: str, to_region: str, to_district: str):
    orders = load_drivers() if user_type == "passenger" else load_passenger()

    count_by_region = {}
    for order in orders.values():
        order_data = order.get("order", order)

#        if order_data.get("status") != "new":
#            continue

        if to_region and order_data.get("to_region") != to_region:
            continue
        if to_district and order_data.get("to_district") != to_district:
            continue

        from_region = order_data.get("from_region")
        if from_region:
            count_by_region[from_region] = count_by_region.get(from_region, 0) + 1

    return count_by_region

# 4. ▼ FROM DISTRICT
def create_from_district_keyboard(u, to_r, to_d, from_r, edit=False):
    cnt = count_orders_from_district(u,to_r,to_d,from_r)
    pref = f"{u[0]}_{'efd' if edit else 'fd'}"
    btns=[InlineKeyboardButton(
            text = f"{d} ({cnt.get(f'{from_r}_{d}',0)})" if cnt.get(f'{from_r}_{d}',0) else f"{d}",
            callback_data=cb(pref, DISTRICT_TO_SLUG[(from_r,d)])
        ) for d in REGIONS_AND_DISTRICTS[from_r]]

    rows = [btns[i:i+3] for i in range(0, len(btns), 3)]
    if not edit:
        rows.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="BACK_TO_PREV")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# 4. count_orders_from_district
def count_orders_from_district(
    user_type: str, 
    to_region: str, 
    to_district: str, 
    from_region: str
):
    orders = load_drivers() if user_type == "passenger" else load_passenger()
    from_region_key = "from_region" #if direction == "to" else "to_region"
    from_district_key = "from_district" #if direction == "to" else "to_district"
    to_region_key = "to_region" #if direction == "to" else "from_region"
    to_district_key = "to_district" #if direction == "to" else "from_district"

    count_by_district = {}
    for order in orders.values():
        order_data = order.get("order", order)
        if (order_data.get(to_region_key) != to_region or 
            order_data.get(to_district_key) != to_district or 
            order_data.get(from_region_key) != from_region):
            continue

        from_district = order_data.get(from_district_key)
        key = f"{from_region}_{from_district}"
        if from_district:
            count_by_district[key] = count_by_district.get(key, 0) + 1

    return count_by_district

# 5. ▼ DAY
def create_day_keyboard(u,to_r,to_d,from_r,from_d,edit=False):
    cnt = count_orders_date(u,to_r,to_d,from_r,from_d)
    pref=f"{u[0]}_{'ed' if edit else 'day'}"
    days={"📆 Бугун":"today","📆 Эртага":"tomorrow","📅 Бошқа кун":"other"}
    kb=[[InlineKeyboardButton(
            text = f"{l} ({cnt.get(k,0)})" if cnt.get(k,0) else f"{l}", # else f"▫️ {l}",
            callback_data=cb(pref,k)
       )] for l, k in days.items()]

#    if not edit:
#        kb.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="BACK_TO_PREV")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# 5. count_orders_date
def count_orders_date(user_type: str, to_region: str, to_district: str, from_region: str, from_district: str):
    orders = load_drivers() if user_type == "passenger" else load_passenger()
    count_by_date = defaultdict(int)

    today = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    tomorrow = today + timedelta(days=1)

    for order in orders.values():
        order_data = order.get("order", order)

        if (order_data.get("to_region") != to_region or
            order_data.get("to_district") != to_district or
            order_data.get("from_region") != from_region or
            order_data.get("from_district") != from_district):
            continue

        day_str = order_data.get("date")
        if not day_str:
            continue

        try:
            order_date = datetime.strptime(day_str, "%Y-%m-%d").date()
            if order_date == today:
                count_by_date["today"] += 1
            elif order_date == tomorrow:
                count_by_date["tomorrow"] += 1
            else:
                count_by_date["other"] += 1
        except ValueError:
            # Нотўғри форматдаги саналар "other"га тушсин
            count_by_date["other"] += 1

    return dict(count_by_date)

# 6. ▼ TIME
TIME_SLOTS = {
    "morning": ("🌅 Эрталаб (06:00–12:00)", "06:00 - 11:59"),
    "afternoon": ("🌤 Кундуз (12:00–16:00)", "12:00 - 15:59"),
    "evening": ("🌇 Кечқурун (16:00–20:00)", "16:00 - 19:59"),
    "night": ("🌃 Кечаси (20:00–00:00)", "20:00 - 23:59"),
    "late_night": ("🌙 Тун (00:00–06:00)", "00:00 - 05:59")
}
def create_time_keyboard(curr, u, edit=False):
    pref = f"{u[0]}_{'et' if edit else 't'}"
    btns = []

    selected_date = curr.get("date")
    is_today = selected_date == datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d")
    now = datetime.now(ZoneInfo("Asia/Tashkent"))
    now_time = now.time()

    for key, (label, time_range) in TIME_SLOTS.items():
        start_str, end_str = time_range.split(" - ")
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()

        # ⏳ Агар диапазон тўлиқ ўтган бўлса, кўрсатмаймиз
        if is_today and end_time <= now_time:
            continue

        # 🌟 Интерфейс учун вақтни янгилаймиз
        if is_today and start_time < now_time < end_time:
            shown_range = f"{now.strftime('%H:%M')}–{end_str}"
        else:
            shown_range = f"{start_str}–{end_str}"

        # 🌅 Эрталаб → 🌅 Эрталаб (14:32–15:59)
        new_label = f"{label.split('(')[0]}({shown_range})"

        count = count_orders_time(u, curr, time_range)
        btns.append([InlineKeyboardButton(
            text=f"{new_label} ({count})" if count > 0 else new_label,
            callback_data=cb(pref, key)
        )])

#    if not edit:
#        btns.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="BACK_TO_PREV")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

def create_exact_time_keyboard(user_type, current_order, orders, is_editing: bool = False) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=4)

    selected_date = current_order.get("date")
    is_today = selected_date == datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d")
    now_hour = datetime.now(ZoneInfo("Asia/Tashkent")).hour

    for hour in range(24):
        if is_today and hour < now_hour:
            continue  # ўтган вақтларни кўрсатмаймиз

        time_str = f"{hour:02d}:00"
        count = count_orders_time(user_type, current_order, orders, time_str)
        button_text = f"{time_str} ({count})" if count > 0 else time_str
        callback_prefix = "edit_exact_time:" if is_editing else "exact_time:"
        callback_data = f"{callback_prefix}{time_str}"
        keyboard.insert(InlineKeyboardButton(text=button_text, callback_data=callback_data))

    return keyboard

# 6. count_orders_time
def count_orders_time(user_type: str, current_order: dict, time_range: str) -> int:
    orders = load_drivers() if user_type == "passenger" else load_passenger()
#    print(f"✅ Юкланган буйруқлар: {orders}")
    from_region = current_order.get("from_region")
    from_district = current_order.get("from_district")
    to_region = current_order.get("to_region")
    to_district = current_order.get("to_district")
    date = current_order.get("date")
#    print(f"✅ current_order: {current_order}")
    count = 0
    for order in orders.values():
        order_data = order.get("order", order)

        if from_region and order_data.get("from_region") != from_region:
            continue
        if from_district and order_data.get("from_district") != from_district:
            continue
        if to_region and order_data.get("to_region") != to_region:
            continue
        if to_district and order_data.get("to_district") != to_district:
            continue
        if date and order_data.get("date") != date:
            continue

        order_time = order_data.get("time")
        if not order_time:
            continue
        # Текшириш: order_time ва time_range
        #print(f"✅ order_time={order_time}, time_range={time_range}")
        
        # ✅ Бу ерда солиштириш функцияси
        match = is_time_match(order_time, time_range)
        #print(f"🔄 Текшириш: order_time={order_time}, time_range={time_range}, ⏱ Мосми: {match}")
        if match:
            count += 1

    return count

def count_filtered_orders(user_type: str, current_order: dict, filter_key: str, filter_value: str) -> int:
    orders = load_drivers() if user_type == "passenger" else load_passenger()
    
    count = 0
    for order in orders.values():
        order_data = order.get("order", order)

        if filter_key == "day":
            # Бугун/эртага фильтр
            today = datetime.now(ZoneInfo("Asia/Tashkent")).date()
            date_value = order_data.get("date")
            if not date_value:
                continue
            order_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            if filter_value == "today" and order_date != today:
                continue
            elif filter_value == "tomorrow" and order_date != today + timedelta(days=1):
                continue
        elif order_data.get(filter_key) != filter_value:
            continue

        match = True
        for key in ["from_region", "from_district", "to_region", "to_district"]:
            if current_order and current_order.get(key) and order_data.get(key) != current_order.get(key):
                match = False
                break

        if match:
            count += 1

    return count

def get_current_order(user_id, user_type):
    orders = load_drivers() if user_type == "driver" else load_passenger()
    user_id = str(user_id)
    if user_id in orders:
        return orders[user_id].get("order", {})
    return {}

# 📍 Умумий "status == new" текширувчи блок
async def check_existing_order(
    callback_query: CallbackQuery, 
    user_id: int, 
    user_type: str, 
    is_editing: bool = False
):
    # 🧹 user_type ни тозалаш:  "passenger_edit" → "passenger",  "driver_edit" → "driver"
    #if user_type.startswith("passenger"):
    #    user_type = "passenger"
    #elif user_type.startswith("driver"):
    #    user_type = "driver"

    # 🔓 Таҳрир (is_editing=True) бўлса – текширмасдан рухсат
    if is_editing or "_edit_" in callback_query.data:
        return False

    print(
        f"🔍 check_existing_order: user_id={user_id}, "
        f"user_type={user_type}, callback_data={callback_query.data}"
    )

    # ⛔️ Акс ҳолда текширув қиламиз
    if user_type == "driver":
        order = get_driver_order(user_id)
    else:
        order = get_passenger_order(user_id)

    if order:
        status = order.get("status", "draft")

        if status == "draft":
            # ❌ буйрутма ҳали тўлиқ эмас — давом этилади
            return False

        elif status == "new":
            # ✅ Тасдиқланган, лекин ҳали ҳаракатда эмас — ўзгартиришга рухсат
            to_region = order.get("to_region", "—")
            from_district = order.get("from_district", "—")
            to_district = order.get("to_district", "—")
            date = order.get("date", "—")
            time = order.get("time", "—")

            text = (
                f"❗️ Сизда тасдиқланган буюртма мавжуд:\n\n"
                f"📍 Манзил: *{to_region}*\n"
                f"🛫 *{from_district} → {to_district}*\n"
                f"🗓 Сана: *{date}*\n"
                f"🕰 Вақт: *{time}*\n\n"
                f"Янги буюртма бериш учун аввалгисини ўзгартиринг ёки бекор қилинг."
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Ўзгартириш", callback_data=f"{user_type}_edit_order")],
                [InlineKeyboardButton(text="❌ Бекор қилиш", callback_data="cancel_order")]
            ])

            await send_or_edit_text(
                callback_query.message,
                text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return True
        
        elif status == "arrived":
            # ✅ Сафар якунланган, ордерни тарихга ўтказиш керак
            timestamp = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")
            path = DRIVER_PATH if user_type == "driver" else PASSENGER_PATH

            with open(path, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                user_data = data.get(str(user_id), {})
                if "order" in user_data:
                    order = user_data["order"]
                    order["status"] = "arrived"
                    order["arrived"] = timestamp
                    user_data.setdefault("order_history", []).append(order)
                    del user_data["order"]
                    f.seek(0)
                    json.dump(data, f, ensure_ascii=False, indent=4)
                    f.truncate()

            # ✅ Ордер тарихга ўтказилди — янги яратишга рухсат
            return False

        else:
            # ❗️ Буйрутма реал жараёнда — фақат бекор қилиш мумкин
            order_status_text = {
                "waiting_for_driver": "Ҳайдовчи кутилмоқда",
                "on_the_way": "Йўлда",
                "arrived": "Жойга етиб келди",
                "completed": "Сафар якунланган",
                "done": "Буюртма бажарилган",
            }

            current_status_text = order_status_text.get(status, "Номаълум ҳолат")

            text = (
                f"❗️ Сизда амалга оширилаётган буюртма мавжуд.\n"
                f"Бу вақтда янги буюртма бериш мумкин эмас.\n\n"
                f"📝 Буюртманинг маълумотлари:\n"
                f"📍 Манзил: *{order.get('to_region', '—')}*\n"
                f"🛫 *{order.get('from_district', '—')} → {order.get('to_district', '—')}*\n"
                f"🗓 Сана: *{order.get('date', '—')}*\n"
                f"🕰 Вақт: *{order.get('time', '—')}*\n\n"
                f"Ҳолати: *{current_status_text}*."
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Бекор қилиш", callback_data="cancel_order")]
            ])

            await send_or_edit_text(
                callback_query.message,
                text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return True

    return False

# @router.callback_query(F.data == "add_order")
@router.callback_query(lambda c: c.data.startswith("add_"))
async def choose_to_region(callback_query: CallbackQuery, state: FSMContext):
    user_type = "passenger" if callback_query.data == "add_p" else "driver"
    user_id = callback_query.from_user.id

    if await check_existing_order(callback_query, user_id, user_type):
        return

    await state.update_data(user_type=user_type, prev_step=None)

    # 🟡 Бошланғич order объектини яратиш
    if user_type == "driver":
        save_driver_order(user_id, {"status": "draft"})
    else:
        save_passenger_order(user_id, {"status": "draft"})

    reply_markup = create_to_region_keyboard(user_type)

    await send_or_edit_text(
        callback_query.message,
        "📍 *Қайси ҲУДУДГА борасиз?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@router.callback_query(lambda c: "_tr_" in c.data)
async def choose_to_district(callback_query: CallbackQuery, state: FSMContext):
    raw, rslug = callback_query.data.split("_tr_")           # raw=p / d
    user_type = "passenger" if raw.startswith("p") else "driver"
    region = SLUG_TO_REGION[rslug]
    user_id = callback_query.from_user.id

    if await check_existing_order(callback_query, user_id, user_type):
        return

    await state.update_data(to_region=region, prev_step="choose_to_region")

    if user_type == "driver":
        save_driver_order(user_id, {"to_region": region})
    else:
        save_passenger_order(user_id, {"to_region": region})

    reply_markup = create_to_district_keyboard(user_type, region)

    await send_or_edit_text(
        callback_query.message,
        f"📍 Йўналиш: *{region}*\n\n📍 *Қайси ТУМАНГА борасиз?*",
        reply_markup=reply_markup,
        parse_mode="Markdown")

@router.callback_query(lambda c: "_td_" in c.data)
async def choose_from_region(cb: CallbackQuery, state: FSMContext):
    raw, dslug = cb.data.split("_td_")
    user_type = "passenger" if raw.startswith("p") else "driver"
    district = SLUG_TO_DISTRICT[dslug]
    region   = (await state.get_data()).get("to_region")

    await state.update_data(to_district=district, prev_step="choose_to_district")

    user_id = cb.from_user.id
    if await check_existing_order(cb, user_id, user_type):
        return

    if user_type == "driver":
        save_driver_order(user_id, {"to_district": district})
    else:
        save_passenger_order(user_id, {"to_district": district})

    data = await state.get_data()

    # Ҳозиргичаги маълумотларни чиқарамиз
    to_region = data.get("to_region", "—")

    text = (
        f"📍 Йўналиш: {to_region} / *{district}*\n\n"
        f"📍 *Қайси ВИЛОЯТДАН кетасиз?*"
    )

    to_region = data.get("to_region")
    to_district = data.get("to_district")

    reply_markup = create_from_region_keyboard(user_type, to_region, to_district)

    await send_or_edit_text(
        cb.message,
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@router.callback_query(lambda c: "_fr_" in c.data)
async def choose_from_district(cb: CallbackQuery, state: FSMContext):
    raw, rslug = cb.data.split("_fr_")
    user_type = "passenger" if raw.startswith("p") else "driver"
    region = SLUG_TO_REGION[rslug]
    user_id = cb.from_user.id

    if await check_existing_order(cb, user_id, user_type):
        return

    await state.update_data(from_region=region)
    
    if user_type == "driver":
        save_driver_order(user_id, {"from_region": region})
    else:
        save_passenger_order(user_id, {"from_region": region})
    
    # 👉 current_order ни оламиз
    data = await state.get_data()

    # Ҳозиргичаги маълумотларни чиқарамиз
    to_r = data.get("to_region", "—")
    to_d = data.get("to_district", "—")

    text = (
        f"📍 Йўналиш: *{to_r} / {to_d}*\n\n"
        f"📍 *{region}*\n\n📍 *Қайси ТУМАНДАН борасиз?*"
    )

    kb = create_from_district_keyboard(user_type, to_r, to_d, region, False)

    await send_or_edit_text(
        cb.message,
        text,
        reply_markup=kb,
        parse_mode="Markdown")

@router.callback_query(lambda c: "_fd_" in c.data)
async def choose_date(cb: CallbackQuery, state: FSMContext):
    raw, dslug = cb.data.split("_fd_")
    user_type = "passenger" if raw.startswith("p") else "driver"
    district = SLUG_TO_DISTRICT[dslug]
    region   = (await state.get_data()).get("from_region")

    await state.update_data(from_district=district)

    user_id = cb.from_user.id
    if await check_existing_order(cb, user_id, user_type):
        return
    print(f"choose_date: {user_type}")
    if user_type == "driver":
        save_driver_order(user_id, {"from_district": district})
    else:
        save_passenger_order(user_id, {"from_district": district})

    data = await state.get_data()

    # Ҳозиргичаги маълумотларни чиқарамиз
    to_r = data.get("to_region", "—")
    to_d = data.get("to_district", "—")
    from_region = data.get("from_region", "—")

    text = (
        f"📍 Йўналиш: *{to_r} / {to_d}*\n"
        f"📍 Манзил: {from_region} / *{district}*\n\n"
        f"🗓 *Қачон кетмоқчисиз?*"
    )

    kb = create_day_keyboard(user_type, to_r, to_d, region, district, False)

    await send_or_edit_text(
        cb.message,
        text,
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.message(OrderState.waiting_for_custom_date)
async def handle_custom_date(message: Message, state: FSMContext):
    try:
        selected_date = datetime.strptime(message.text.strip(), "%Y-%m-%d")
        now = datetime.now(ZoneInfo("Asia/Tashkent"))

        if selected_date.date() < now.date():
            await message.answer("⛔ Бу сана ўтган. Илтимос, келгуси санани киритинг. (Йил-Ой-Кун форматида, масалан: 2025-05-30)")
            return

        formatted_day = selected_date.strftime("%Y-%m-%d")
        await state.update_data(date=formatted_day)

        user_id = message.from_user.id
        data = await state.get_data()
        user_type = data.get("user_type", "passenger")

        if user_type == "driver":
            save_driver_order(user_id, {"date": formatted_day})
        else:
            save_passenger_order(user_id, {"date": formatted_day})

        # 🕒 Вақт слотлари
        time_slots = {
            "morning": "06:00",
            "afternoon": "13:00",
            "evening": "18:00",
            "night": "21:00",
            "late_night": "01:00"
        }

        available_buttons = []
        for key, time_str in time_slots.items():
            slot_time = datetime.strptime(f"{formatted_day} {time_str}", "%Y-%m-%d %H:%M")
            if slot_time > now:
                label = {
                    "morning": "🌅 Эрталаб (06:00–11:59)",
                    "afternoon": "☀️ Кундузи (12:00–15:59)",
                    "evening": "🌇 Кечқурун (16:00–19:59)",
                    "night": "🌃 Кечаси (20:00–23:59)",
                    "late_night": "🌙 Тун (00:00–05:59)",
                }[key]
                available_buttons.append([
                    InlineKeyboardButton(
                        text=label, 
                        callback_data=f"{user_type}_time_{key}"
                    )
                ])

        available_buttons.append([
            InlineKeyboardButton(
                text="🕰 Аниқ вақт", 
                callback_data=f"{user_type}_time_exact"
            )
        ])

        if not available_buttons:
            await message.answer("⛔ Ушбу сана учун барча вақтлар ўтиб кетган. Илтимос, бошқа кунни танланг.")
            return

        markup = InlineKeyboardMarkup(inline_keyboard=available_buttons)
        await message.answer("🕰 Қайси вақтда йўлга чиқасиз?", reply_markup=markup)

    except ValueError:
        await message.answer("❌ Нотўғри формат. Илтимос, санани Йил-Ой-Кун кўринишида киритинг. (масалан: 2025-05-30)")

@router.callback_query(lambda c: "_day_" in c.data)
async def choose_time_slot(callback_query: CallbackQuery, state: FSMContext):
    data_parts = callback_query.data.split("_day_")
    if len(data_parts) != 2:
        await callback_query.answer("❌ Нотўғри callback маълумоти.")
        return

    user_type_raw, day_key = data_parts
    user_type = "driver" if user_type_raw == "d" else "passenger"  # ✅ user_type ни конвертация қилиб олиш

    now = datetime.now(ZoneInfo("Asia/Tashkent"))
    if day_key == "today":
        selected_date = now.date()
    elif day_key == "tomorrow":
        selected_date = now.date() + timedelta(days=1)
    else:
        example_date = (datetime.now(ZoneInfo("Asia/Tashkent")).date() + timedelta(days=5)).strftime("%Y-%m-%d")
        await callback_query.message.answer(
            f"📅 Илтимос, сана киритинг (Йил-Ой-Кун форматда, масалан: {example_date}):"
        )
        await state.update_data(user_type=user_type)
        await state.set_state(OrderState.waiting_for_custom_date)
        return

    formatted_date = selected_date.strftime("%Y-%m-%d")
    await state.update_data(date=formatted_date)

    user_id = callback_query.from_user.id
    if user_type == "driver":
        save_driver_order(user_id, {"date": formatted_date})
    else:
        save_passenger_order(user_id, {"date": formatted_date})

    data = await state.get_data()
    curr = {
        "from_region": data.get("from_region"),
        "from_district": data.get("from_district"),
        "to_region": data.get("to_region"),
        "to_district": data.get("to_district"),
        "date": data.get("date")
    }

    # Ҳозиргичаги маълумотларни чиқарамиз
    to_region = data.get("to_region", "—")
    from_district = data.get("from_district", "—")
    to_district = data.get("to_district", "—")
    date = data.get("date", "—")

    text = (
        f"📍 Манзил: *{to_region}*\n"
        f"📍 Йўналиш: *{from_district} → {to_district}*\n\n"
        f"🗓 Сана: *{date}*\n\n"
        f"🕰 *Қайси вақтда йўлга чиқасиз?*"
    )
    keyboard = create_time_keyboard(curr, user_type)

    await send_or_edit_text(
        callback_query.message,
        text,
        reply_markup=keyboard
    )

@router.callback_query(lambda c: "_time_exact" in c.data)
async def ask_exact_time(callback_query: CallbackQuery, state: FSMContext):
    user_type = callback_query.data.split("_time_")[0]

    user_id = callback_query.from_user.id
    if await check_existing_order(callback_query, user_id, user_type):
        return

    await callback_query.message.answer("⏰ Илтимос, аниқ кетиш вақтини киритинг (масалан: 14:30):")

    await state.update_data(user_type=user_type)

    await state.set_state(OrderState.waiting_for_exact_time)

@router.message(OrderState.waiting_for_exact_time)
async def handle_exact_time(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()

    try:
        selected_date_str = data.get("date")
        if not selected_date_str:
            await message.answer("❗️ Сана топилмади. Илтимос, аввало сана танланг.")
            return
        
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        entered_time = datetime.strptime(message.text.strip(), "%H:%M").time()
        full_datetime = datetime.combine(selected_date, entered_time)
        now = datetime.now(ZoneInfo("Asia/Tashkent"))

        if full_datetime <= now:
            await message.answer("⛔ Ушбу вақт аллақачон ўтган. Илтимос, келажакдаги вақтни киритинг. (масалан: 18:45)")
            return

        # Вақт тўғри бўлса — сақланади
        formatted_time = entered_time.strftime("%H:%M")
        await state.update_data(time=formatted_time)
        await state.update_data(departure_time=f"{selected_date_str} {formatted_time}")

        user_type = data.get("user_type", "passenger")
#-------------------------------------------------------------------------------------
        # ❗️ Аввал текширамиз: агар order мавжуд ва status == "new" бўлса → маълумот киритилмасин
        if user_type == "driver":
            order = get_driver_order(user_id)
        else:
            order = get_passenger_order(user_id)


        # Фақат йўловчи бўлса нарх ҳисоблаймиз
        if user_type == "passenger":
            price = calculate_price(
                from_region,
                to_region,
                from_district,
                to_district
            )
            price_text = f"\n💰 Нарх: *{price:,} сўм*" if price > 0 else "\n💰 Нарх: *Аниқланмади*"
        else:
            price_text = ""  # Ҳайдовчида нарх кўрсатилмайди

        # ❗️ Агар order мавжуд ва status new бўлса → маълумот киритилмасин
        if order and order.get("status") == "new":
            # Ҳозиргичаги маълумотларни чиқарамиз
            to_region = order.get("to_region", "—")
            from_region = order.get("from_region", "—")
            from_district = order.get("from_district", "—")
            to_district = order.get("to_district", "—")
            date = order.get("date", "—")
            time = order.get("time", "—")
            
            if user_type == "passenger":
                price_text = order.get("price", "—")
            else:
                price_text = ""  # Ҳайдовчида нарх кўрсатилмайди

            text = (
                f"❗️ Сизда тасдиқланган буюртма мавжуд:\n\n"
                f"📍 Манзил: *{to_region}*\n"
                f"🛫 *{from_district} → {to_district}*\n"
                f"🗓 Сана: *{date}*\n"
                f"🕰 Вақт: *{time}*\n"
                f"{price_text}\n"
                f"\nЯнги буюртма бериш учун аввалгисини ўзгартиринг ёки бекор қилинг."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Ўзгартириш", callback_data=f"{user_type}_edit_order")],
                [InlineKeyboardButton(text="❌ Бекор қилиш", callback_data="cancel_order")]
            ])

            await send_or_edit_text(
                message,  # агар callback_query.message бўлса, шуни алмаштир
                text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return
    
        # Янгиланган вақтни сақлаймиз
        if user_type == "driver":
            save_driver_order(user_id, {"time": formatted_time})
            order_data = get_driver_order(user_id)
        else:
            save_passenger_order(user_id, {"time": formatted_time})
            order_data = get_passenger_order(user_id)

        # Ҳозиргичаги маълумотларни чиқарамиз
        to_region = order_data.get("to_region", "—")
        from_region = order_data.get("from_region", "—")
        from_district = order_data.get("from_district", "—")
        to_district = order_data.get("to_district", "—")
        date = order_data.get("date", "—")

        # Фақат йўловчи бўлса нарх ҳисоблаймиз
        if user_type == "passenger":
            price = calculate_price(
                from_region,
                to_region,
                from_district,
                to_district
            )
            price_text = f"\n💰 Нарх: *{price:,} сўм*" if price > 0 else "\n💰 Нарх: *Аниқланмади*"
            save_passenger_order(user_id, {"price": price})
        else:
            price_text = ""  # Ҳайдовчида нарх кўрсатилмайди

        # Тасдиқлаш экрани
        text = (
            f"📦  *Й Ў Н А Л И Ш:* \n\n"
            f"📍 Манзил:  *{to_region}*\n\n"
            f"🛫 *{from_district} → {to_district}* 🛬\n\n"
            f"🗓 *{date}*\n"
            f"🕰 *{order_data.get('time', formatted_time)}*"
            f"\n🕰 *{price_text}*"
        )

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"{user_type}_confirm_order")],
            [InlineKeyboardButton(text="♻️ Ўзгартириш", callback_data=f"{user_type}_edit_order")],
            [InlineKeyboardButton(text="❌ Бекор қилиш", callback_data="cancel_order")],
        ])

        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
        await state.clear()

    except ValueError:
        await message.answer("❌ Нотўғри формат. Илтимос, вақтни `соат:дақиқа` кўринишида киритинг. (масалан: 14:30)")

@router.callback_query(lambda c: "_t_" in c.data and "exact" not in c.data)
async def check_order(callback_query: CallbackQuery, state: FSMContext):
    parts = callback_query.data.split("_t_")
    user_type_raw = parts[0]
    user_type = "driver" if user_type_raw == "d" else "passenger"
    time_key = parts[1]  # = "evening" каби
    print(f"🔍 Танланган time_key: {time_key}")

    selected_time = TIME_SLOTS.get(time_key, (None, "Аниқ эмас"))[1]  # -> "16:00 - 20:00"

    user_id = callback_query.from_user.id
    if await check_existing_order(callback_query, user_id, user_type):
        return
    
    # Маълумотни сақлаймиз
    if user_type == "driver":
        save_driver_order(user_id, {"time": selected_time})
        order = get_driver_order(user_id)
    else:
        save_passenger_order(user_id, {"time": selected_time})
        order = get_passenger_order(user_id)

    # Ҳозиргичаги маълумотларни чиқарамиз
    to_region = order.get("to_region", "—")
    from_region = order.get("from_region", "—")
    from_district = order.get("from_district", "—")
    to_district = order.get("to_district", "—")
    date = order.get("date", "—")

    # Фақат йўловчи бўлса нарх ҳисоблаймиз
    if user_type == "passenger":
        price = calculate_price(
            from_region,
            to_region,
            from_district,
            to_district
        )
        price_text = f"\n💰 Нарх: *{price:,} сўм*" if price > 0 else "\n💰 Нарх: *Аниқланмади*"
        save_passenger_order(user_id, {"price": price})
    else:
        price_text = ""  # Ҳайдовчида нарх кўрсатилмайди

    text = (
        f"📍 Манзил: *{to_region}*\n"
        f"📍 Йўналиш: *{from_district} → {to_district}*\n"
        f"🗓 Сана: *{date}*\n"
        f"🕰 Вақт: *{selected_time}*\n"
        f"{price_text}\n"
        
        f"✅ Буюртмани тасдиқлайсизми?"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"{user_type}_confirm_order")],
        [InlineKeyboardButton(text="✏️ Таҳрирлаш", callback_data=f"add_{user_type_raw}")]
    ])

    await send_or_edit_text(callback_query.message, text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(lambda c: c.data.endswith("_confirm_order"))
async def confirm_order(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user_type = callback_query.data.replace("_confirm_order", "")

    if user_type == "driver":
        role = "Ҳайдовчи"
    else:
        role = "Йўловчи"

    # ✅ Сақлаш функцияси орқали буюртмани сақлаш
    order = await save_order(user_id, user_type, callback_query.bot)

    if not order:
        #await send_or_edit_text(callback_query.message, "❌ Буюртма тўлиқ эмас ёки хатолик юз берди.")
        await callback_query.answer("❌ Буюртма тўлиқ эмас ёки хатолик юз берди. confirm_order")
        return

    # 📍 Манзиллар
    from_region = order.get("from_region", "—")
    from_district = order.get("from_district", "—")
    to_region = order.get("to_region", "—")
    to_district = order.get("to_district", "—")
    date = order.get("date", "—")
    time = order.get("time", "—")

    # 💰 Нарх фақат йўловчида кўрсатилади
    price_text = ""
    if user_type == "passenger":
        price = order.get("price", -1)
        price_text = f"\n💰 Нарх: *{price:,} сўм*" if price > 0 else "\n💰 Нарх: *Аниқланмади*"

    # 📝 Ҳабар матни
    text = (
        f"✅ Ҳурматли {role}! Буюртмангиз қабул қилинди.\n\n"
        f"📍 Манзил: *{to_region}*\n"
        f"📍 Йўналиш: *{from_district} → {to_district}*\n"
        f"🗓 Сана: *{date}*\n"
        f"🕰 Вақт: *{time}*"
        f"{price_text}\n"
    )

    await send_or_edit_text(callback_query.message, text, parse_mode="Markdown")

@router.callback_query(lambda c: c.data == "cancel_order")
async def cancel_current_order(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user_id_str = str(user_id)

    # Фойдаланувчи типини аниқлаймиз
    order = get_driver_order(user_id)
    user_type = "driver" if order else "passenger"

    if not order:
        order = get_passenger_order(user_id)

    if not order:
        await send_or_edit_text(callback_query.message, "❌ Бекор қилинадиган буюртма топилмади.")
        return

    # Буюртмага статус қўшамиз ва тарихга сақлаймиз
    order["status"] = "cancelled"
    order["cancelled_at"] = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")

    if user_type == "driver":
        save_driver_order_history(user_id, order)
        clear_driver_order(user_id)
    else:
        save_passenger_order_history(user_id, order)
        clear_passenger_order(user_id)

    await send_or_edit_text(callback_query.message, "✅ Буюртмангиз муваффақиятли бекор қилинди.")
