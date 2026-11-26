"""Telegram Mini App support: the amount screen that opens the phone's number keyboard.

The page sends Telegram's signed `initData` with the amount. We verify the signature
(HMAC with the bot token, as documented by Telegram), so nobody can submit for someone else.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, urlencode

from .config import BOT_TOKEN, PUBLIC_URL

MAX_AGE_SECONDS = 24 * 3600


def verify_init_data(init_data: str) -> dict | None:
    """Returns the Telegram user ({id, first_name, ...}) if the data is genuine and fresh, else None."""
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received = pairs.pop("hash", "")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(expected, received):
        return None
    if time.time() - int(pairs.get("auth_date", "0")) > MAX_AGE_SECONDS:
        return None
    try:
        return json.loads(pairs.get("user", "{}")) or None
    except ValueError:
        return None


def enabled() -> bool:
    return PUBLIC_URL.startswith("https://")


def amount_url(lang: str, title: str, currency: str, max_amount: float | None = None,
               allow_zero: bool = False) -> str:
    params = {"lang": lang, "title": title, "cur": currency}
    if max_amount is not None:
        params["max"] = f"{max_amount:.2f}"
    if allow_zero:
        params["zero"] = "1"
    return f"{PUBLIC_URL}/app/amount?{urlencode(params)}"
