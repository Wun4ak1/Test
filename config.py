# config.py
import os
import json
from dotenv import load_dotenv

# .env файлини юклаймиз
load_dotenv()

# Атроф-муҳит ўзгарувчиларини оламиз
TOKEN = os.getenv("TOKEN")
ADMINS_RAW = os.getenv("ADMINS", "[]")
try:
    ADMINS = [int(admin_id) for admin_id in json.loads(ADMINS_RAW)]
except (json.JSONDecodeError, TypeError, ValueError):
    ADMINS = []
OTHER_SECRET = os.getenv("OTHER_SECRET")
