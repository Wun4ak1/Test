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
    parsed = json.loads(ADMINS_RAW)
    if isinstance(parsed, dict):
        # Railway варианти: {"209550763": true}
        ADMINS = [int(k) for k in parsed.keys()]
    elif isinstance(parsed, list):
        # Локал варианти: [209550763]
        ADMINS = [int(i) for i in parsed]
    else:
        ADMINS = []
except (json.JSONDecodeError, ValueError, TypeError):
    ADMINS = []

OTHER_SECRET = os.getenv("OTHER_SECRET")
