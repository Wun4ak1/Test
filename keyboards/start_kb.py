# keyboards/start_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from handlers.utils import get_user_status, is_driver_approved
from config import ADMINS

def start_kb(user_id: int) -> InlineKeyboardMarkup:
    user_status = get_user_status(user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[], row_width=1)

    def add_button(text, callback_data):
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    # Агар фойдаланувчи биринчи марта кирса
    if user_status is None or user_status == "new_user":
        add_button("🚕 Мен ҳайдовчиман", "driver")
        add_button("🧍 Мен йўловчиман", "passenger")
    
    # Ҳайдовчи учун тугмалар
    elif user_status == "driver":
        if is_driver_approved(user_id):
            add_button("🗺️ Йўналишни киритиш", "add_d")
            #add_button("👥 Мос йўловчилар", "show_matching_passengers")
            #add_button("🧾 Йўловчи буюртмалари", "view_passenger_orders")
        else:
            add_button("🧾 Маълумот юбориш", "haydovchi")
            add_button("Маълумот ҳолати", "is_driver_approved_check")

    elif user_status == "passenger" or (user_status and user_status.startswith("location_")):
        add_button("📍 Манзилни танланг", "add_p")
    
    # Ҳам driver, ҳам passenger учун умумий тугмалар
    if user_status in ("driver", "passenger") or (user_status and user_status.startswith("location_")):
        add_button("👥 Дўст таклиф қилиш", "invite_friends")
        add_button("📊 Менинг статистикам", "my_stats")
        #add_button("📋 Буюртмаларим тарихи", "view_order_history")
        add_button("♻️ Ролни ўзгартириш", "change_user_status")


    # Барча фойдаланувчилар учун умумий тугма
    add_button("📞 Админга мурожаат", "admin_contact")

    # Агар фойдаланувчи админ бўлса, "Админ" тугмасини қўшамиз
    if user_id in ADMINS:
    #if str(user_id) in ADMINS:
        add_button("🛠️ Админ", "admin")

    return keyboard
