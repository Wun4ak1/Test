import os
from dotenv import load_dotenv

# .env файлини юклаймиз
load_dotenv()

# Атроф-муҳит ўзгарувчиларини оламиз
TOKEN = os.getenv("TOKEN")
ADMINS = os.getenv("ADMINS")  # Агар бир нечта бўлса, list қилиб ҳам олиш мумкин
OTHER_SECRET = os.getenv("OTHER_SECRET")
