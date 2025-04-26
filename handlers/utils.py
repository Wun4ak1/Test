# handlers/utils.py
import json
from aiogram import Bot, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, time as dtime
import logging
import os
from config import TOKEN
from location import calculate_price

# Ботни яратиш
bot = Bot(token=TOKEN)

# Лойиҳа папкасининг йўлини олиш
project_dir = os.path.dirname(os.path.abspath(__file__))

USER_STATUS_PATH = os.path.join(project_dir, '..', 'user_statuses.json')
PASSENGER_PATH = os.path.join(project_dir, '..', 'passenger.json')
DRIVER_PATH = os.path.join(project_dir, '..', 'driver.json')

#logging.basicConfig(level=logging.INFO, filename="bot.log", filemode="a", format="%(asctime)s - %(levelname)s - %(message)s")
logging.basicConfig(level=logging.INFO)
# === STATUS VA ORDER MA'LUMOTLAR ===
def load_users():
    try:
        with open(USER_STATUS_PATH, "r", encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users):
    with open(USER_STATUS_PATH, "w", encoding='utf-8') as file:
        json.dump(users, file, ensure_ascii=False, indent=2)

def get_user_status(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get("status", "new_user")

def save_user_status(user_id, status):
    users = load_users()
    user_id = str(user_id)

    if user_id not in users or not isinstance(users[user_id], dict):
        users[user_id] = {}

    current_status = users[user_id].get("status", "new_user")

    # Янги рольлар (passenger, driver) ҳолатини текшириш ва сақлаш
    if status in ["new_user", "passenger", "driver"]:
        users[user_id]["status"] = status
    else:
        if current_status in ["passenger", "driver"]:
            users[user_id]["status"] = current_status
        else:
            users[user_id]["status"] = "new_user"

    save_users(users)
    logging.info(f"Фойдаланувчи {user_id} статуси янгиланди: {users[user_id]['status']}")

# JSON файлни ўқиш
def load_json(file_path):
    if not os.path.exists(file_path):
        return {}  # Агар файл йўқ бўлса, бўш луғат қайтарилади
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        # Агар файл бузилган бўлса, автоматик тозаланади
        return {}

# JSON файлга маълумотни сақлаш
def save_json(file_path, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"❗ JSON файлни сақлашда хатолик: {e}")

# === passenger drivers MA'LUMOTLAR ===
# ✅ 4. utils.py — load/save функциялар
def load_passenger():
    try:
        with open(PASSENGER_PATH, "r", encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_passenger(users):
    with open(PASSENGER_PATH, "w", encoding='utf-8') as file:
        json.dump(users, file, ensure_ascii=False, indent=4)

def load_drivers():
    try:
        with open(DRIVER_PATH, "r", encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_driver(data):
    with open(DRIVER_PATH, "w", encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

# === save_order MA'LUMOTLAR get_ ===
def get_passenger_order(user_id):
    try:
        with open(PASSENGER_PATH, 'r', encoding="utf-8") as file:
            data = json.load(file)
            user_data = data.get(str(user_id))
            if user_data:
                order = user_data.get("order")
                return order
            return None
    except FileNotFoundError:
        return None

def save_passenger_order(user_id, data):
    try:
        if os.path.exists(PASSENGER_PATH):
            with open(PASSENGER_PATH, 'r', encoding='utf-8') as file:
                all_data = json.load(file)
        else:
            all_data = {}

        user_id = str(user_id)

        # Агар user мавжуд бўлмаса, бошидан тузамиз
        if user_id not in all_data:
            all_data[user_id] = {
                "order": {},
                "order_history": []
            }

        # ✅ Агар "order" калити йўқ бўлса
        if "order" not in all_data[user_id]:
            all_data[user_id]["order"] = {}

        # ✅ order ичида маълумотларни сақлаш
        for key, value in data.items():
            all_data[user_id]["order"][key] = value

        with open(PASSENGER_PATH, 'w', encoding='utf-8') as file:
            json.dump(all_data, file, ensure_ascii=False, indent=4)

    except Exception as e:
        logging.error(f"save_passenger_order хатолик: {e}")

def get_driver_order(user_id):
    try:
        with open(DRIVER_PATH, 'r', encoding="utf-8") as file:
            data = json.load(file)
            user_data = data.get(str(user_id))
            if user_data:
                order = user_data.get("order")
                return order
            return None
    except FileNotFoundError:
        return None

def save_driver_order(user_id, data):
    try:
        user_id = str(user_id)

        # 1. Драйвер буйрутмаларини юклаш
        if os.path.exists(DRIVER_PATH):
            with open(DRIVER_PATH, 'r', encoding='utf-8') as file:
                all_data = json.load(file)
        else:
            all_data = {}

        logging.debug(f"[save_driver_order] Юкланган драйвер маълумотлари: {all_data.get(user_id)}")

        # 2. Агар user мавжуд бўлмаса, яратиш
        if user_id not in all_data:
            all_data[user_id] = {
                "order": {},
                "order_history": []
            }
            logging.debug(f"[save_driver_order] Янги user қўшилди: {user_id}")
        elif "order" not in all_data[user_id]:
            all_data[user_id]["order"] = {}
            logging.debug(f"[save_driver_order] Мавжуд user, лекин 'order' йўқ эди: {user_id}")

        # 3. Мавжуд маълумотларни order га қўшиш
        for key, value in data.items():
            all_data[user_id]["order"][key] = value

        # 4. available_seats ни ўз профилдан олиш
        profile = all_data[user_id].get("profile", {})
        seat_count = profile.get("seat_count")
        if seat_count:
            all_data[user_id]["order"]["available_seats"] = int(seat_count)
            logging.debug(f"[save_driver_order] available_seats қўшилди: {seat_count}")
        else:
            logging.warning(f"[save_driver_order] seat_count топилмади — ID: {user_id}")

        # 5. Янгиланган driver_orders.json ни сақлаш
        with open(DRIVER_PATH, 'w', encoding='utf-8') as file:
            json.dump(all_data, file, ensure_ascii=False, indent=4)

        logging.info(f"[save_driver_order] Буюртма сақланди — ID: {user_id}")

    except Exception as e:
        logging.error(f"save_driver_order хатолик: {e}")

def load_orders(user_type: str):
    return load_passenger() if user_type == "passenger" else load_drivers()

# === УМУМИЙ САҚЛАШ ФУНКЦИЯСИ ===
REQUIRED_FIELDS = ["to_region", "to_district", "from_region", "from_district", "date", "time"]

async def save_order(user_id, user_type, bot):
    user_id = str(user_id)
    file_path = DRIVER_PATH if user_type == "driver" else PASSENGER_PATH

    # 📂 Маълумотларни юклаш
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    else:
        data = {}

    # Фойдаланувчи борлигини текшириш
    if user_id not in data:
        print(f"❌ Фойдаланувчи топилмади: {user_id}")
        return None

    user_data = data[user_id]
    
    # 👤 Агар йўловчи бўлса, телефон рақамини юборганлигини текшириш
    if user_type == "passenger":
        if not user_data.get("phone"):  # Телефон рақами йўқ
            phone_request_keyboard = ReplyKeyboardMarkup(
                resize_keyboard=True,
                one_time_keyboard=True,
                keyboard=[
                    [KeyboardButton(text="📞 Телефон рақамни юбориш", request_contact=True)],
                    [KeyboardButton(text="⏹ Қўлда киритиш")]
                ]
            )
            user_data["waiting_for_phone"] = True

            # 📝 JSON'га "waiting_for_phone"ни янгилаш
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)

            await bot.send_message(
                chat_id=user_id,
                text="📱 Илтимос, телефон рақамингизни ёзиб ёки тугма орқали юборинг:",
                reply_markup=phone_request_keyboard
            )
            return None  # Телефон рақами ўрнатилмаганда, ордерни сақламаслик

    # ✅ Энди order маълумотини текшириш
    order_data = user_data.get("order", {})
    print(f"✅ Маълумот топилди: {order_data}")

    # Агар ордер бўлса ва тўлиқ маълумотлар йўқ бўлса, хато хабарини юбориш
    if not order_data:
        print("❌ Order маълумоти йўқ.")
        return None

    if not all(order_data.get(field) for field in REQUIRED_FIELDS):
        print(f"❌ Тўлиқ маълумот йўқ: {order_data}")
        return None

    # 🆕 Янги order_number — тарихдаги ордерлар сонига асосланган
    order_number = len(user_data.get("order_history", [])) + 1

    # 🕓 Ҳозирги вақт
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Янги ордер яратамиз (нарх билан)
    new_order = {
        **order_data,
        "order_number": order_number,
        "status": "new",
        "status_timestamps": {
            "created": timestamp
        }
    }

    # ✅ Агар фойдаланувчи йўловчи бўлса, нархни ҳисоблаймиз
    if user_type == "passenger":
        calculated_price = calculate_price(
            order_data.get("from_region", ""),
            order_data.get("to_region", ""),
            order_data.get("from_district", ""),
            order_data.get("to_district", "")
        )
        new_order["price"] = calculated_price  # 👉 Нарх қўшилди

    user_data["order"] = new_order

    # 🧹 Вақтинчалик майдонларни тозалаш
    for key in REQUIRED_FIELDS + ["chosen_driver_id"]:
        user_data.pop(key, None)

    # 🔒 Сақлаш
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    print("✅ Сақлаш якунланди.")

    # Агар йўловчи бўлса, мос ҳайдовчиларни тавсия қилиш
    if user_type == "passenger":
        await recommend_multiple_drivers_to_passenger(
            passenger_id=user_id,
            user_order=new_order,
            bot=bot
        )

    # Агар ҳайдовчи ордерни берган бўлса, йўловчига хабар юбориш (status != "done")
    if user_type == "driver":
        with open(PASSENGER_PATH, 'r', encoding='utf-8') as file:
            all_passengers = json.load(file)

        for p_id, p_data in all_passengers.items():
            passenger_order = p_data.get("order", {})
            if not passenger_order:
                continue
            # Мослаш ва статус текшириш
            if is_match(new_order, passenger_order) and p_data.get("status") != "arrived":
                await recommend_multiple_drivers_to_passenger(
                    passenger_id=p_id,
                    user_order=passenger_order,
                    bot=bot
                )

    return new_order

def get_order(user_id, user_type):
    filename = DRIVER_PATH if user_type == "driver" else PASSENGER_PATH
    
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            orders = json.load(f)
            return orders.get(str(user_id), {})
    return {}

async def match_and_notify(user_id: str, user_type: str, new_order: dict, bot):
    other_type = "driver" if user_type == "passenger" else "passenger"
    from_path = DRIVER_PATH if other_type == "driver" else PASSENGER_PATH

    if not os.path.exists(from_path):
        return

    with open(from_path, 'r', encoding='utf-8') as file:
        other_data = json.load(file)

    for other_id, other_user_data in other_data.items():
        other_order = other_user_data.get("order")
        if other_order and is_match(new_order, other_order):
            print(f"🔁 Мос {other_type} топилди: {other_id}")
            await notify_driver_and_passenger(
                driver_id=other_id if user_type == "passenger" else user_id,
                passenger_id=user_id if user_type == "passenger" else other_id,
                driver_order=other_order if user_type == "passenger" else new_order,
                passenger_order=new_order if user_type == "passenger" else other_order,
                bot=bot
            )
            update_driver_seats(other_id)

def clear_passenger_order(user_id):
    passengers = load_passenger()
    user_id = str(user_id)

    if user_id in passengers:
        passengers[user_id].pop("order", None)
        save_passenger(passengers)
        logging.info(f"{user_id} йўловчи буюртмаси ўчирилди.")

def clear_driver_order(user_id):
    drivers = load_drivers()
    user_id = str(user_id)

    if user_id in drivers:
        drivers[user_id].pop("order", None)
        save_driver(drivers)
        logging.info(f"{user_id} ҳайдовчи буюртмаси ўчирилди.")

# 2. user_statuses.json ичида фойдаланувчи роли сақланаётганини инобатга олиб, шунга қараб қайси файлга ёзишни аниқлаш
def get_user_role(user_id: int):
    statuses = load_json(USER_STATUS_PATH)
    return statuses.get(str(user_id), {}).get("status") # "role"

def get_all_passenger_orders():
    users = load_passenger()
    all_orders = []

    for user_id, user_data in users.items():
        order = user_data.get("order")
        if order:
            all_orders.append({
                "user_id": user_id,
                "from": order.get("from_district"),
                "to": order.get("to_district"),
                "date": order.get("date"),
                "time": order.get("time"),
                "order_number": order.get("order_number", 0)
            })

    return all_orders

# ----------------------------------------------------------------------------------------

# ✅ 2. Энг мос келадиган йўловчиларни қидириш функцияси:
def find_matching_passengers(driver_orders):
    driver_order = driver_orders.get("order") if "order" in driver_orders else driver_orders

    driver_from = driver_order.get("from_district", "").strip().lower()
    driver_to = driver_order.get("to_district", "").strip().lower()
    driver_date = driver_order.get("date")
    driver_time = driver_order.get("time")

    passengers = load_passenger()
    matched_passengers = []

    for user_id, passenger_data in passengers.items():
        order = passenger_data.get("order")
        if not order:
            continue

        passenger_from = order.get("from_district", "").strip().lower()
        passenger_to = order.get("to_district", "").strip().lower()
        passenger_date = order.get("date")
        passenger_time = order.get("time")

        if (
            passenger_from == driver_from and
            passenger_to == driver_to and
            passenger_date == driver_date and
            passenger_time == driver_time
        ):
            matched_passengers.append({
                "user_id": user_id,
                "from": order.get("from_district"),
                "to": order.get("to_district"),
                "date": order.get("date"),
                "time": order.get("time"),
                "order_number": order.get("order_number", 0)
            })

    return matched_passengers

# Ҳайдовчига буйрутма тақдим қилиш
async def offer_order_to_driver(driver_id, order_details):
    # Ҳайдовчига буйрутма тақдим қилиш учун хабар юбориш
    # Айтайлик, ботга хабар ёзилган деб қабул қиламиз
    message = f"Сизга янги буйрутма тақдим этилди:\n{order_details}"
    # Масалан, телефон рақамини хабарга қўшиш
    await send_message(driver_id, message)

async def send_message(user_id, text, reply_markup=None, parse_mode=None):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode  # ✅ эндиликда parse_mode қабул қилади
        )
    except Exception as e:
        print(f"❌ send_message error: {e}")

# Йўловчи буйрутмасига мос ҳайдовчи тавсия қилиш
def recommend_driver(user_order):
    try:
        # Ҳайдовчиларнинг буйрутмаси
        with open(DRIVER_PATH, 'r', encoding='utf-8') as file:
            drivers_data = json.load(file)
        
        suitable_drivers = []

        # Йўловчи буйрутмасига мос ҳайдовчи қидириш
        for driver in drivers_data.values():
            if (driver["from_district"] == user_order["from_district"] and 
                driver["to_district"] == user_order["to_district"] and
                driver["time_type"] == user_order["time_type"] and
                (driver["date"] == user_order["date"] or driver["date"] is None) and
                driver["available_seats"] > 0):
                suitable_drivers.append(driver)
        
        # Мос ҳайдовчилардан рейтинг ва ўрин сонига кўра тартиблаш
        #suitable_drivers.sort(key=lambda x: (x["available_seats"], -x["rating"]))
        suitable_drivers.sort(key=lambda d: (-d.get("rating", 0), d.get("available_seats", 0)))


        # Энг мос ҳайдовчи
        if suitable_drivers:
            return suitable_drivers[0]
        else:
            return None
    except FileNotFoundError:
        return None

async def recommend_multiple_drivers_to_passenger(passenger_id, user_order, bot):
    try:
        # 🛒 Ҳайдовчилар маълумотларини юклаймиз
        with open(DRIVER_PATH, 'r', encoding='utf-8') as file:
            drivers_data = json.load(file)
        
        # 📁 Фойдаланувчилар статусини юклаш
        status_data = load_json(USER_STATUS_PATH)
        passenger_info = status_data.get(str(passenger_id), {})
        invited_users = passenger_info.get("invited_users", [])

        matched_drivers = []

        # 🚕 Ҳар бир ҳайдовчини текширамиз
        for driver_id, driver_data in drivers_data.items():
            profile = driver_data.get("profile", {})
            # Ҳайдовчининг ордер маълумотларини олиш
            order = driver_data.get("order", {})
            
            # Агар ордер тўлиқ бўлмаса, бу ҳайдовчини ўтказиб юбориш
            if not all(order.get(field) for field in ["from_district", "to_district", "date", "time"]):
                print(f"⚠️ Ҳайдовчи маълумоти тўлиқ эмас, ID={driver_id}")
                continue

            # Ҳайдовчи маълумотларини тўлдириш
            driver_info = {
                "name": profile.get("name", "Номаълум"),
                "phone": profile.get("phone", "Номаълум"),
                "car_model": profile.get("car_model", "Номаълум"),
                "car_number": profile.get("car_number", "Номаълум"),
                "from_district": order.get("from_district", "Номаълум"),
                "to_district": order.get("to_district", "Номаълум"),
                "date": order.get("date", "Номаълум"),
                "time": order.get("time", "Номаълум"),
                "available_seats": order.get("available_seats", 0),
                "rating": driver_data.get("rating", 0),
                "id": driver_id,
                "accepted_passenger_count": len(order.get("accepted_passengers", []))
            }

            # Ҳайдовчи маълумоти тўлиқ бўлса, мос келган ҳайдовчини qo'shish
            if is_match(user_order, order) and order.get("available_seats", 0) > 0:
                matched_drivers.append(driver_info)

        # Агар мос келадиган ҳайдовчилар топилмаса
        if not matched_drivers:
            await bot.send_message(passenger_id, "⏳ Мос ҳайдовчилар солиштирилмоқда,\nТез фурсатда Сиз билан боғланамиз.")
            return

        # 🚫 Танланган ҳайдовчини чиқариб ташлаш
        chosen_driver_id = user_order.get("chosen_driver_id")
        if chosen_driver_id:
            matched_drivers = [
                driver for driver in matched_drivers if driver["id"] != chosen_driver_id
            ]

        if not matched_drivers:
            await bot.send_message(passenger_id, "⏳ Танланган ҳайдовчи билан боғланиб бўлмади.\nБошқа ҳайдовчилар қидирилмоқда.")
            return
        
        # 🧠 Ҳайдовчиларни гуруҳларга ажратиш
        invited_drivers = [d for d in matched_drivers if d["id"] in invited_users]
        new_drivers = [d for d in matched_drivers if d["accepted_passenger_count"] == 0 and d["id"] not in invited_users]
        experienced_drivers = [d for d in matched_drivers if d["accepted_passenger_count"] > 0 and d["id"] not in invited_users]

        # Сортировка
        invited_drivers.sort(key=lambda d: (-d.get("rating", 0), -d.get("available_seats", 0)))
        new_drivers.sort(key=lambda d: (-d.get("rating", 0), -d.get("available_seats", 0)))
        experienced_drivers.sort(key=lambda d: (-d.get("rating", 0), -d.get("available_seats", 0)))

        # 🔥 Якуний тартиб
        matched_drivers = invited_drivers + new_drivers + experienced_drivers

        # 📤 Ҳар бирини йўловчига қайта юбориш
        text = f"🔄 Танланган ҳайдовчи билан боғланиб бўлмади.\nСизга бошқа мос {len(matched_drivers)} та ҳайдовчи топилди:\n\n"

        for i, driver in enumerate(matched_drivers, start=1):
            driver_text = f"{i}. 🚘 Мос ҳайдовчи:\n\n"
            driver_text += f"👤 Ҳайдовчи: {driver['name']}\n"
            #f"📞 Телефон: {driver['phone']}\n"
            driver_text += f"🚗 Автомобил: {driver['car_model']}\n"
            #f"🔢 Давлат рақами: {driver['car_number']}\n"
            driver_text += f"📍 Йўналиш: {driver['from_district']} ➝ {driver['to_district']}\n"
            driver_text += f"📅 Сана: {driver['date']}\n"
            driver_text += f"⏰ Вақт: {driver['time']}\n"
            #f"🆔 ID: {driver['id']}\n"

            # Агар бу таклиф қилинган ҳайдовчи бўлса, белгилаймиз
            if driver['id'] in invited_users:
                driver_text += "⭐ Бу ҳайдовчи сизнинг таклифингиз орқали рўйхатдан ўтган!\n"

            # ✅ Тасдиқлаш тугмаси
            choose_btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Шу ҳайдовчини танлаш",
                    callback_data=f"choose_driver_{driver['id']}"
                )]
            ])

            # Юбориш
            await bot.send_message(
                chat_id=passenger_id,
                text=driver_text,
                reply_markup=choose_btn,
                parse_mode="HTML"
            )

    except Exception as e:
        print(f"❌ recommend_multiple_drivers_to_passenger хатолик: {e}")
        await bot.send_message(passenger_id, "❌ Хатолик юз берди. Илтимос, кейинроқ қайта уриниб кўринг.")
# ----------------------------------------------------------------------------------------

time_ranges = {
    "morning": ("06:00", "11:59"),
    "afternoon": ("12:00", "15:59"),
    "evening": ("16:00", "19:59"),
    "night": ("20:00", "23:59"),
    "late_night": ("00:00", "05:59"),
}

def parse_time_str(time_str):
    """ HH:MM -> datetime.time """
    try:
        return datetime.strptime(time_str.strip(), "%H:%M").time()
    except Exception as e:
        print(f"❌ parse_time_str хато: {e}")
        return None

def get_range_label(start_time, end_time):
    """ Диапазонга мос label'ни қайтаради: morning, evening ва ҳ.к. """
    for label, (range_start, range_end) in time_ranges.items():
        rs = parse_time_str(range_start)
        re = parse_time_str(range_end)

        if rs == start_time and re == end_time:
            return label
    return None

def convert_to_exact_or_range_label(time_val):
    """
    Агар "HH:MM" бўлса — аниқ вақт
    Агар "HH:MM - HH:MM" бўлса — диапазон label'га айлантирилади
    Агар "evening", "afternoon" бўлса — тўғридан-тўғри қабул қилинади
    """
    if "-" in time_val:
        parts = time_val.split("-")
        if len(parts) == 2:
            start = parse_time_str(parts[0])
            end = parse_time_str(parts[1])
            if start and end:
                label = get_range_label(start, end)
                if label:
                    return label
    elif ":" in time_val:
        return time_val.strip()
    elif time_val.strip() in time_ranges:
        return time_val.strip()

    return None

def is_time_match(time1, time2):
    print(f"🕰 {time1} ва {time2} ўртасида солиштириш")
    def parse_range(val):
        if "-" in val:
            start_str, end_str = val.split("-")
            start = parse_time_str(start_str)
            end = parse_time_str(end_str)
            return start, end
        elif val in time_ranges:
            start_str, end_str = time_ranges[val]
            return parse_time_str(start_str), parse_time_str(end_str)
        elif ":" in val:
            t = parse_time_str(val)
            return t, t
        return None, None

    t1_start, t1_end = parse_range(time1)
    t2_start, t2_end = parse_range(time2)

    if not (t1_start and t1_end and t2_start and t2_end):
        print("❌ Вақтни парслашда муаммо")
        return False

    # Агар t1 интервал т2 интервал ичида бўлса
    latest_start = max(t1_start, t2_start)
    earliest_end = min(t1_end, t2_end)

    match = latest_start <= earliest_end
    print(f"🕰 Диапазон мослиги: {match}")
    return match

def is_match(order1, order2):
    from_district_match = order1.get("from_district") == order2.get("from_district")
    to_district_match = order1.get("to_district") == order2.get("to_district")
    to_region_match = order1.get("to_region") == order2.get("to_region")

    time1 = order1.get("time", "")
    time2 = order2.get("time", "")
    time_match = False  # Вақтни аввалдан ўтказиш

    date1_str = order1.get("date")
    date2_str = order2.get("date")

    try:
        today = datetime.today().date()
        date1 = datetime.strptime(date1_str, "%Y-%m-%d").date()
        date2 = datetime.strptime(date2_str, "%Y-%m-%d").date()

        # Саналарни мослаштириш: агар дата бўлмаса, вақт мослиги текширилади
        date_match = (
            date1 == date2 or  # Агар саналар бир хил бўлса
            (date1 < today)  # Агар сана ўтган бўлса, ва вақтни текширишнинг кераги йўқ
        )

        # Агар сана бир хил бўлса, вақтни ҳам текшириб чиқамиз
        if date1 == date2:
            time_match = is_time_match(time1, time2)

    except Exception as e:
        print(f"❌ Sana parse xato: {e}")
        date_match = False

    print(f"🔍 Солиштириш:")
    print(f"    from_district: {order1.get('from_district')} == {order2.get('from_district')}")
    print(f"    to_district  : {order1.get('to_district')} == {order2.get('to_district')}")
    print(f"    to_region  : {order1.get('to_region')} == {order2.get('to_region')}")
    print(f"    date         : {order1.get('date')} == {order2.get('date')}")
    print(f"    time         : {order1.get('time')} == {order2.get('time')}")
    print(f"    🕰 Вақт мослиги: {is_time_match(order1.get('time', ''), order2.get('time', ''))}")

    return (
        from_district_match and
        to_region_match and
        date_match and
        time_match
    )

def create_contact_button(user_id: int, name: str, phone: str | None = None) -> InlineKeyboardMarkup:
    buttons = []

    if phone:
        buttons.append([
            InlineKeyboardButton(
                text="📞 Телефон рақам",
                url=f"tel:{phone}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="👤 Профилни очиш",
            url=f"tg://user?id={user_id}"
            #url=f"https://t.me/{name}" if name.startswith("@") else f"tg://user?id={user_id}"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def notify_driver_and_passenger(driver_id, passenger_id, driver_order, passenger_order, bot):
    from_district = passenger_order.get("from_district", "Номаълум")
    to_district = passenger_order.get("to_district", "Номаълум")
    date = passenger_order.get("date", "Номаълум")
    time = passenger_order.get("time", "Номаълум")

    # 🔹 Ҳайдовчининг маълумотларини оламиз
    # user_statuses.json дан маълумотларни ўқиш
    with open(USER_STATUS_PATH, "r", encoding="utf-8") as f:
        user_statuses = json.load(f)

    # Ҳайдовчи маълумотлари
    driver_info = user_statuses.get(str(driver_id), {}).get("profile", {})
    driver_name = driver_info.get("name", "Номаълум")
    driver_phone = driver_info.get("phone", "Номаълум")
    driver_car = driver_info.get("car_model", "Номаълум")
    driver_car_number = driver_info.get("car_number", "Номаълум")

    # 🔹 Telegram орқали йўловчининг исмини олиш
    passenger_user = await bot.get_chat(passenger_id)
    passenger_name = passenger_user.full_name

    # 🚘 Ҳайдовчига — йўловчи маълумоти
    passenger_from = passenger_order.get("from_district", "Номаълум")
    passenger_to = passenger_order.get("to_district", "Номаълум")
    passenger_date = passenger_order.get("date", "Номаълум")
    passenger_time = passenger_order.get("time", "Номаълум")

    # 👤 Ҳайдовчига — мос йўловчи маълумоти
    driver_text = (
        f"🧍‍♂️ Мос йўловчи топилди!\n\n"
        f"👤 Йўловчи: {passenger_name}\n"
        f"🆔 ID: `{passenger_id}`\n"
        #f"📞 Телефон: {passenger_phone}\n"
        f"📍 Йўналиш: {from_district} ➝ {to_district}\n"
        f"📅 Сана: {date}\n"
        f"⏰ Вақт: {time}"
    )
    await send_message(
        driver_id,
        driver_text,
        reply_markup=create_driver_confirm_buttons(passenger_id),  # passenger_id ни улаямиз
        parse_mode="Markdown"
    )

    # 🧍‍♂️ Йўловчига — ҳайдовчи маълумоти
    driver_from = driver_order.get("from_district", "Номаълум")
    driver_to = driver_order.get("to_district", "Номаълум")
    driver_date = driver_order.get("date", "Номаълум")
    driver_time = driver_order.get("time", "Номаълум")

    # 👉 Йўловчига хабар
    passenger_text = (
        f"🚘 Мос ҳайдовчи топилди!\n\n"
        f"👤 Ҳайдовчи: {driver_name}\n"
        f"📞 Телефон: {driver_phone}\n"
        f"🚗 Автомобил: {driver_car}\n"
        f"🔢 Давлат рақами: {driver_car_number}\n"
        f"📍 Йўналиш: {driver_from} ➝ {driver_to}\n"
        f"📅 Сана: {driver_date}\n"
        f"⏰ Вақт: {driver_time}\n"
        f"🆔 ID: `{driver_id}`"
    )
    await send_message(passenger_id, passenger_text, parse_mode="Markdown")

def update_driver_seats(driver_id):
    try:
        if os.path.exists(DRIVER_PATH):
            with open(DRIVER_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            driver_id = str(driver_id)
            if driver_id in data and "available_seats" in data[driver_id]["order"]:
                current = data[driver_id]["order"]["available_seats"]
                data[driver_id]["order"]["available_seats"] = max(current - 1, 0)

                with open(DRIVER_PATH, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)

    except Exception as e:
        logging.error(f"update_driver_seats хатолик: {e}")

# Ҳайдовчи учун тугма, йўловчини танлаши учун
def create_driver_confirm_buttons(passenger_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Қабул қилиш ✅",
                    callback_data=f"accept_{passenger_id}"
                ),
                InlineKeyboardButton(
                    text="Рад этиш ❌",
                    callback_data=f"reject_{passenger_id}"
                )
            ]
        ]
    )
    return keyboard


# ----------------------------------------------------------------------------------------

def create_departure_confirmation_keyboard(driver_id: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ҳа", callback_data=f"departed_yes_{driver_id}"),
            InlineKeyboardButton(text="❌ Йўқ", callback_data=f"departed_no_{driver_id}")
        ]
    ])
    return keyboard

# ✅ 1. utils.py файлида approval статусини текшириш функцияси:
def is_driver_approved(user_id: int) -> bool:
    try:
        with open(DRIVER_PATH, "r", encoding="utf-8") as file:
            drivers = json.load(file)
        driver_data = drivers.get(str(user_id))
        return driver_data and driver_data.get("approved", False)
    except Exception as e:
        logging.error(f"Approval текширишда хато: {e}")
        return False

# ----------------------------------------------------------------------------------------

# 📥 Йўловчи Буюртмани тарихга сақлаш
def save_passenger_order_history(user_id, order_data):
    users = load_passenger()
    user_id_str = str(user_id)

    if user_id_str not in users:
        users[user_id_str] = {"status": "passenger"}

    if "order_history" not in users[user_id_str]:
        users[user_id_str]["order_history"] = []

    # Тарихга буйрутмани қўшиш
    users[user_id_str]["order_history"].append(order_data)

    save_passenger(users)
    logging.info(f"Фойдаланувчи {user_id} учун буйрутма тарихга қўшилди: {order_data}")

def get_passenger_order_history(user_id):
    data = load_passenger()
    user_id = str(user_id)

    # Фойдаланувчининг буйрутма тарихини текшириш
    if user_id in data and "order_history" in data[user_id]:
        return data[user_id]["order_history"]
    return []

def save_driver_order_history(user_id, driver_order):
    user_id = str(user_id)
    data = load_drivers()

    if user_id not in data:
        data[user_id] = {}

    if "order_history" not in data[user_id]:
        data[user_id]["order_history"] = []

    data[user_id]["order_history"].append(driver_order)

    with open(DRIVER_PATH, 'w') as file:
        json.dump(data, file, indent=4)

def get_driver_order_history(user_id):
    data = load_drivers()
    user_id = str(user_id)

    # Фойдаланувчининг буйрутма тарихини текшириш
    if user_id in data and "order_history" in data[user_id]:
        return data[user_id]["order_history"]
    return []

# Йўловчига тарихни кўрсатиш
async def show_passenger_order_history(user_id, callback_query):
    order_history = get_passenger_order_history(user_id)

    if order_history:
        order_text = "📋 Сизнинг буйрутмаларингиз:\n"
        for order in order_history:
            order_text += f"📍 Манзил: {order.get('from_district', 'Nomaʼlum')} → {order.get('to_district', 'Nomaʼlum')},\n" \
                          f"🕒 Вақт: {order.get('time', 'Кўрсатилмаган')}\n"
        await callback_query.message.answer(order_text)
    else:
        await callback_query.message.answer("❌ Сизнинг буйрутма тарихингиз мавжуд эмас.")

# ----------------------------------------------------------------------------------------

# 📆 Сана кўринишини форматлаш
def format_date(date_str: str) -> str:
    try:
        dep_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.today().date()
        if dep_date == today:
            return "Бугун"
        elif dep_date == today + timedelta(days=1):
            return "Эртага"
        elif dep_date == today + timedelta(days=2):
            return "Индинга"
        return date_str
    except:
        return date_str

def get_available_dates():
    now = datetime.now()
    dates = []

    for i in range(3):  # Фақат 3 кун кўрсатамиз
        day = now.date() + timedelta(days=i)
        dates.append(day.strftime("%Y-%m-%d"))

    return dates

def get_available_times(selected_day):
    now = datetime.now()
    time_slots = {
        "morning": "06:00",
        "afternoon": "13:00",
        "evening": "18:00",
        "night": "21:00",
        "late_night": "01:00"
    }

    available = {}
    for key, time_str in time_slots.items():
        combined = datetime.strptime(f"{selected_day} {time_str}", "%Y-%m-%d %H:%M")
        if combined > now:
            available[key] = time_str

    return available

# 🧰 Универсал хабар чиқариш функцияси
async def send_or_edit_text(target, text: str, reply_markup=None, parse_mode="Markdown"):
    """
    Универсал функция: хабарни таҳрир қилади ёки янги хабар жўнатади.
    `target` - Message ёки CallbackQuery объекти бўлиши мумкин.
    """
    try:
        # Агар CallbackQuery келса
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        # Агар Message келса
        elif isinstance(target, Message):
            await target.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    except TelegramBadRequest as e:
        logging.warning(f"⚠️ Хабар таҳрир қилинмади (TelegramBadRequest): {e}")

        # Агар таҳрир қилиб бўлмаса, янги хабар жўнатамиз
        try:
            if isinstance(target, CallbackQuery):
                await target.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
            elif isinstance(target, Message):
                await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as ex:
            logging.error(f"🚫 Хабарни жўнатишда ҳам хато: {ex}")

async def send_or_edit_last(user_id: int, state: FSMContext, bot, text: str, reply_markup=None, parse_mode=None):
    data = await state.get_data()
    last_msg_id = data.get("last_bot_msg_id")

    try:
        if last_msg_id:
            await bot.edit_message_text(
                text=text,
                chat_id=user_id,
                message_id=last_msg_id,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            sent = await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            await state.update_data(last_bot_msg_id=sent.message_id)

    except TelegramForbiddenError:
        # Фойдаланувчи ботни блоклаган — ҳеч қандай ҳаракат қилмаслик
        print(f"⚠️ Фойдаланувчи {user_id} ботни блоклади.")
        return

    except Exception as e:
        # Бошқа хатолар бўлса, қайта юборишга уриниш
        try:
            sent = await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            await state.update_data(last_bot_msg_id=sent.message_id)
        except TelegramForbiddenError:
            print(f"⚠️ Фойдаланувчи {user_id} ботни блоклади (қайта юборишда).")
        except Exception as ex:
            print(f"⚠️ Хатолик юз берди: {ex}")