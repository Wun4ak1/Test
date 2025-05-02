# config.py
import os
import json
from dotenv import load_dotenv

# .env файлини юклаймиз
load_dotenv()

# Атроф-муҳит ўзгарувчиларини оламиз
TOKEN = os.getenv("TOKEN")

ADMINS = json.loads(os.getenv("ADMINS", "[]"))
ADMIN_IDS = set(map(int, ADMINS))

OTHER_SECRET = os.getenv("OTHER_SECRET")
