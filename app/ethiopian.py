"""Gregorian <-> Ethiopian calendar conversion (Julian Day Number method)."""
from datetime import date

EPOCH = 1723856            # JDN of 1 Meskerem 1 (Amete Mihret)
GREG_TO_JDN = 1721425      # date.toordinal() + this = JDN

MONTHS = {
    "am": ["መስከረም", "ጥቅምት", "ኅዳር", "ታኅሣሥ", "ጥር", "የካቲት",
           "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ"],
    "en": ["Meskerem", "Tikimt", "Hidar", "Tahsas", "Tir", "Yekatit",
           "Megabit", "Miyazya", "Ginbot", "Sene", "Hamle", "Nehase", "Pagume"],
}
WEEKDAYS = {
    "am": ["ሰኞ", "ማክሰኞ", "ረቡዕ", "ሐሙስ", "ዓርብ", "ቅዳሜ", "እሑድ"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}


def to_ethiopian(d: date) -> tuple[int, int, int]:
    jdn = d.toordinal() + GREG_TO_JDN
    r = (jdn - EPOCH) % 1461
    n = r % 365 + 365 * (r // 1460)
    year = 4 * ((jdn - EPOCH) // 1461) + r // 365 - r // 1460
    return year, n // 30 + 1, n % 30 + 1


def from_ethiopian(year: int, month: int, day: int) -> date:
    jdn = EPOCH + 365 + 365 * (year - 1) + year // 4 + 30 * month + day - 31
    return date.fromordinal(jdn - GREG_TO_JDN)


def month_range(d: date) -> tuple[date, date]:
    """Gregorian [start, end) of the Ethiopian month that contains d."""
    y, m, _ = to_ethiopian(d)
    start = from_ethiopian(y, m, 1)
    end = from_ethiopian(y + 1, 1, 1) if m == 13 else from_ethiopian(y, m + 1, 1)
    return start, end


def _l(lang: str) -> str:
    return "am" if lang == "am" else "en"


def month_only(d: date, lang: str = "en") -> str:
    return MONTHS[_l(lang)][to_ethiopian(d)[1] - 1]


def month_name(d: date, lang: str = "en") -> str:
    """ኅዳር 2019 ዓ.ም  /  Hidar 2019 E.C."""
    y, m, _ = to_ethiopian(d)
    return f"{MONTHS[_l(lang)][m - 1]} {y} {'ዓ.ም' if lang == 'am' else 'E.C.'}"


def long_date(d: date, lang: str = "en") -> str:
    """ሐሙስ፣ ኅዳር 17 ቀን 2019 ዓ.ም  /  Thursday, Hidar 17, 2019 E.C."""
    y, m, day = to_ethiopian(d)
    L = _l(lang)
    if L == "am":
        return f"{WEEKDAYS[L][d.weekday()]}፣ {MONTHS[L][m - 1]} {day} ቀን {y} ዓ.ም"
    return f"{WEEKDAYS[L][d.weekday()]}, {MONTHS[L][m - 1]} {day}, {y} E.C."


def short_date(d: date, lang: str = "en") -> str:
    """ኅዳር 17  /  Hidar 17"""
    _, m, day = to_ethiopian(d)
    return f"{MONTHS[_l(lang)][m - 1]} {day}"
