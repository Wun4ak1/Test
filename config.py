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
    ADMINS = json.loads(ADMINS_RAW)
except json.JSONDecodeError:
    ADMINS = []  # Агар бир нечта бўлса, list қилиб ҳам олиш мумкин
OTHER_SECRET = os.getenv("OTHER_SECRET")
