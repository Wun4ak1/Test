# config.py
import os
import json
from dotenv import load_dotenv

# .env файлини юклаймиз
load_dotenv()

# Атроф-муҳит ўзгарувчиларини оламиз
TOKEN = os.getenv("TOKEN")

ADMINS_RAW = os.getenv("ADMINS")

try:
    if isinstance(ADMINS_RAW, str):
        parsed = json.loads(ADMINS_RAW)
        if isinstance(parsed, dict):
            ADMINS = set(map(int, parsed.keys()))
        elif isinstance(parsed, list):
            ADMINS = set(map(int, parsed))
        elif isinstance(parsed, int):
            ADMINS = {parsed}
        else:
            ADMINS = set()
    elif isinstance(ADMINS_RAW, int):
        ADMINS = {ADMINS_RAW}
    else:
        ADMINS = set()
except Exception as e:
    print(f"ADMINS парслашда хатолик: {e}")
    ADMINS = set()

OTHER_SECRET = os.getenv("OTHER_SECRET")
