from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot

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

async def invite_actions_kb(bot: Bot, user_id: str) -> InlineKeyboardMarkup:
    bot_username = (await bot.me()).username
    invite_link = f"https://t.me/{bot_username}?start={user_id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📨 Дўстни таклиф қилиш", switch_inline_query=invite_link)
        ],
        [
            InlineKeyboardButton(text="📋 Менинг таклифларим", callback_data="my_invites")
        ]
    ])
    return keyboard

#def invite_actions_kb(bot_username: str, user_id: str):
#    invite_link = f"https://t.me/{bot_username}?start={user_id}"
#
#    return InlineKeyboardMarkup(inline_keyboard=[
#        [
#            InlineKeyboardButton(text="📨 Таклиф қилиш", switch_inline_query=invite_link)
#        ],
#        [
#            InlineKeyboardButton(text="📋 Менинг таклифларим", callback_data="my_invites")
#        ]
#    ])
