from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def order_status_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🧐 Буюртмамни кўриш",
                callback_data="view_my_order"
            )
        ]
    ])
    return keyboard
