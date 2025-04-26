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
from states import AdminStates
from keyboards.start_kb import start_kb
from utils import (
    recommend_multiple_drivers_to_passenger,
    get_driver_order, save_passenger_order, send_or_edit_text,
    load_drivers, is_driver_approved, USER_STATUS_PATH, PASSENGER_PATH, DRIVER_PATH
)
bot = Bot(token=TOKEN)

router = Router()

@router.message(Command("админга_мурожаат"))
async def contact_admin(message: Message, state: FSMContext):
    await message.answer(
        "Админ билан боғланиш учун мурожаатингизни ёзиб қолдиринг. У тез орада жавоб беради. ✍️"
    )
    await state.set_state(AdminStates.awaiting_admin_message)

@router.callback_query(lambda c: c.data == "admin_contact")
async def handle_admin_contact(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer(
        "Админ билан боғланиш учун мурожаатингизни ёзинг. ✍️"
    )
    await state.set_state(AdminStates.awaiting_admin_message)

# Админга мурожаат юбориш
@router.message(StateFilter(AdminStates.awaiting_admin_message))
async def forward_to_admin(message: Message, state: FSMContext):
    logging.info(f"Обрабатываю сообщение с состоянием: {AdminStates.admin_replying}")
    # Логика обработки

    user = message.from_user

    text = (
        f"📩 <b>Янги мурожаат:</b>\n"
        f"<b>Фойдаланувчи:</b> {user.full_name} (@{user.username or 'йўқ'})\n"
        f"<b>ID:</b> <code>{user.id}</code>\n\n"
        f"<b>Хабар:</b>\n{message.text}"
    )

    # Админларга хабар юбориш
    for admin_id in ADMINS:
        try:
            await message.bot.send_message(
                admin_id,
                text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✍️ Жавоб бериш", callback_data=f"reply_to_{user.id}")]
                ])
            )
        except Exception as e:
            logging.error(f"Админга хабар юбориб бўлмади: {e}")

    # Жавоб
    await message.answer("✅ Мурожаатингиз админга юборилди. Илтимос, жавобни кутинг.")

    # Мурожаатга жавоб бериш учун холатни аниқлаймиз
    await state.update_data(reply_to_user_id=user.id)  # User ID сақлаш
    await state.set_state(AdminStates.awaiting_admin_message)

@router.callback_query(lambda c: c.data.startswith("reply_to_") and str(c.from_user.id) in map(str, ADMINS))
async def handle_admin_reply_button(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.data.split("_")[-1]
    await state.update_data(reply_to_user_id=int(user_id))
    await callback_query.message.answer("✍️ Жавоб матнини киритинг:")
    await state.set_state(AdminStates.admin_replying)

# Админнинг жавобини юбориш
@router.message(StateFilter(AdminStates.admin_replying))
async def send_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()  # Холатдан маълумот олиш
    user_id = data.get("reply_to_user_id")  # Жавоб бериладиган фойдаланувчи ID

    if user_id:
        try:
            await message.bot.send_message(
                user_id,
                f"📩 Админдан жавоб:\n\n{message.text}"
            )
            await message.answer("✅ Жавоб юборилди.")
        except Exception as e:
            await message.answer(f"❌ Хатолик юборишда: {e}")
    else:
        await message.answer("❌ Жавоб юбориш учун фойдаланувчи ID топилмади.")

    await state.clear()  # Холатни тозалаш