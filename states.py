# ToshkanTaksi/states.py
from aiogram.fsm.state import State, StatesGroup

class OrderState(StatesGroup):
    choosing_region = State()
    choosing_district = State()
    choosing_date_type = State()
    choosing_time_range = State()
    custom_date = State()
    custom_time = State()
    confirming_location = State()
    select_region = State()
    select_area = State()
    select_date = State()
    select_time = State()
    selecting_exact_time = State()
    choosing_role = State()
    choosing_to_region = State()
    choosing_from_region = State()
    choosing_departure_date = State()
    choosing_time_interval = State()
    confirming_order = State()
    waiting_for_custom_date = State()
    waiting_for_exact_time = State()
    date = State()
    time = State()
    edit_to_region = State()

class DriverOrderState(StatesGroup):
    waiting_for_from_location = State()
    waiting_for_to_location = State()
    waiting_for_date = State()
    waiting_for_custom_date = State()
    waiting_for_time = State()
    waiting_for_exact_time = State()

class DriverInfo(StatesGroup):
    name = State()
    phone = State()
    car_model = State()
    car_number = State()
    seat_count = State()
    confirm = State()

class EditOrder(StatesGroup):
    choosing_field = State()
    editing_from_region = State()
    editing_from_district = State()
    editing_to_region = State()
    editing_to_district = State()
    editing_date = State()
    editing_time = State()
    confirming_update = State() 
    from_region = State()
    from_district = State()
    to_region = State()
    to_district = State()
    date = State()
    day = State()
    time = State()
    confirm_from = State()
    waiting_for_custom_date = State()


# Статуслар ва холатлар
class AdminStates(StatesGroup):
    admin_replying = State()  # Админга жавоб бериш
    awaiting_admin_message = State()  # Админдан хабар ёзиш
