# config.py
import os
import json
from dotenv import load_dotenv

# .env файлини юклаймиз
load_dotenv()

# Атроф-муҳит ўзгарувчиларини оламиз
TOKEN = os.getenv("TOKEN")

ADMINS_RAW = os.getenv("ADMINS", "{}")  # 🔁 default: dict кўринишида

try:
    ADMINS = json.loads(ADMINS_RAW)
except json.JSONDecodeError:
    ADMINS = {}

# Фақат ID лардан иборат set ёки рўйхат ҳам тузиш мумкин:
ADMIN_IDS = set(map(int, ADMINS.keys()))  # Agar kerak bo‘lsa

OTHER_SECRET = os.getenv("OTHER_SECRET")
