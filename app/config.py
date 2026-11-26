import os
import re
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CURRENCY = os.getenv("CURRENCY", "ብር")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Africa/Addis_Ababa"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Everything the bot stores lives in DATA_DIR (a Docker volume in production).
DATA_DIR = os.getenv("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "expenses.db"))
STATE_PATH = os.path.join(DATA_DIR, "bot_state.pickle")
VOICE_DIR = os.path.join(DATA_DIR, "voice_notes")


def normalize_phone(phone: str) -> str:
    """Keep the last 9 digits so +251911..., 251911... and 0911... all match."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:]


ALLOWED_PHONES = {
    normalize_phone(p) for p in os.getenv("ALLOWED_PHONES", "").split(",") if p.strip()
}


def _parse_accounts(raw: str) -> list[tuple[str, list[str]]]:
    """ "0911111111:Ahadu,CBE;0922222222:CBE" -> [("911111111", ["Ahadu","CBE"]), ...] """
    plan = []
    for part in raw.split(";"):
        if ":" not in part:
            continue
        phone, names = part.split(":", 1)
        names = [n.strip() for n in names.split(",") if n.strip()]
        if normalize_phone(phone) and names:
            plan.append((normalize_phone(phone), names))
    return plan


# Who owns which account. The first person listed is the main earner.
ACCOUNT_PLAN = _parse_accounts(os.getenv(
    "ACCOUNTS", ""))  # empty = one shared set of default accounts

# Display names before someone registers: "0911111111:Partner A,0922222222:Partner B"
PEOPLE_NAMES = {normalize_phone(p.split(":", 1)[0]): p.split(":", 1)[1].strip()
                for p in os.getenv("NAMES", "").split(",") if ":" in p}

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Put it in the .env file.")
