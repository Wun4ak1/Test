# keyboards/start_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from handlers.utils import get_user_status
from config import ADMINS  # Агар ADMINS тўғри жойда бўлса

def start_kb(user_id: int) -> InlineKeyboardMarkup:
    # Фойдаланувчининг статусини текшириш
    user_status = get_user_status(user_id)

    # Инлайн клавиатура тузиш
    keyboard = InlineKeyboardMarkup(inline_keyboard=[], row_width=1)

    # Агар фойдаланувчи биринчи марта кирса, "Мен ҳайдовчиман" ва "Мен йўловчиман" тугмалари кўрсатилади
    if user_status is None  or user_status == "new_user":
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🚕 Мен ҳайдовчиман", callback_data="driver")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🧍 Мен йўловчиман", callback_data="passenger")])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="📞 Админга мурожаат", callback_data="admin_contact")
        ])
    
    # 📋 Йўловчининг жорий буюртмаси тунмаси ва ҳайдовчи учун буюртма қўшиш тугмаси бўладм
    elif user_status == "driver":  # Агар фойдаланувчи ҳайдовчи бўлса
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="📋 Йўналишни киритиш", callback_data="add_d")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="👥 Дўст таклиф қилиш", callback_data="invite_friends")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="📊 Менинг статистикам", callback_data="my_stats")])
        #keyboard.inline_keyboard.append([InlineKeyboardButton(text="👥 Мос йўловчилар", callback_data="show_matching_passengers")])
        #keyboard.inline_keyboard.append([InlineKeyboardButton(text="🧾 Йўловчи буюртмалари", callback_data="view_passenger_orders")])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="📞 Админга мурожаат", callback_data="admin_contact")
        ])

    elif user_status == "passenger" or (user_status and user_status.startswith("location_")):  # Агар фойдаланувчи йўловчи бўлса
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="📍 Манзилни танланг", callback_data="add_p")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="👥 Дўст таклиф қилиш", callback_data="invite_friends")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="📊 Менинг статистикам", callback_data="my_stats")])
        #keyboard.inline_keyboard.append([InlineKeyboardButton(text="📋 Буюртмаларим тарихи", callback_data="view_order_history")])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="📞 Админга мурожаат", callback_data="admin_contact")
        ])

    # Агар фойдаланувчи админ бўлса, "Админ" тугмасини қўшамиз
    if user_id in ADMINS:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Сатусни алмаштириш", callback_data="change_user_status")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🛠️ Админ", callback_data="admin")])

    return keyboard
#        keyboard.inline_keyboard.append([InlineKeyboardButton(text="📋 Буюртма қўшиш", callback_data="add_driver_orders")])
#        keyboard.inline_keyboard.append([InlineKeyboardButton(text="📍 Манзилни танланг", callback_data="choose_location")])
