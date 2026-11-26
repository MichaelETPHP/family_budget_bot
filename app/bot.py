import html
import logging
import re
import warnings
from datetime import date, datetime, time, timedelta
from functools import wraps
from pathlib import Path
from typing import Callable

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import KeyboardButtonStyle, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
from telegram.warnings import PTBUserWarning

from . import db
from . import ethiopian as et
from .config import (ALLOWED_PHONES, BOT_TOKEN, PEOPLE_NAMES, STATE_PATH, TZ, VOICE_DIR as _VOICE_DIR,
                     normalize_phone)
from .i18n import CATEGORIES, DEFAULT_LANG, DIVIDER, LABEL_TO_ACTION, all_labels, t

warnings.filterwarnings("ignore", category=PTBUserWarning)
log = logging.getLogger(__name__)
HTML = ParseMode.HTML
GREEN, RED, BLUE = KeyboardButtonStyle.SUCCESS, KeyboardButtonStyle.DANGER, KeyboardButtonStyle.PRIMARY
VOICE_DIR = Path(_VOICE_DIR)
ICON = {"expense": "💸", "income": "💰", "transfer": "🔄", "setbal": "✏️"}

(PHONE, NAME, CATEGORY, AMOUNT, CONFIRM, NOTE,
 TR_FROM, TR_TO, TR_AMOUNT, TR_CONFIRM, SB_ACCOUNT, SB_AMOUNT) = range(12)


# ═════════════════════════ small helpers ═════════════════════════

def L(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def esc(s: str | None) -> str:
    return html.escape(s or "")


def short_money(x: float) -> str:
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}"


def money(x: float, lang: str) -> str:
    return f"{'-' if x < 0 else ''}{short_money(abs(x))} {t(lang, 'cur')}"


def today_local() -> date:
    return db.now_local().date()


def day_label(lang: str, d: date) -> str:
    """Always the real (Ethiopian) date: messages stay in the chat, so "Today" would be wrong tomorrow."""
    return et.short_date(d, lang)


def when(lang: str, stamp: str) -> str:
    """'2026-11-26 08:01:00' -> 'Hidar 17 · 08:01'"""
    ts = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    return f"{day_label(lang, ts.date())} · {ts:%H:%M}"


def mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def cat_label(lang: str, kind: str, key: str) -> str:
    pair = CATEGORIES.get(kind, {}).get(key)
    return pair[1 if lang == "am" else 0] if pair else key


def kname(lang: str, kind: str) -> str:
    return t(lang, f"k_{kind}")


def bar(part: float, total: float, width: int = 10) -> str:
    filled = round(width * part / total) if total else 0
    return "▰" * filled + "▱" * (width - filled)


def pct(part: float, total: float) -> str:
    return f"{round(100 * part / total)}%" if total else "0%"


def step_header(lang: str, kind: str, step: int, sub_key: str, total: int) -> str:
    dots = "●" * step + "○" * (total - step)
    return (f"{ICON[kind]} <b>{t(lang, f'kn_{kind}')}</b>\n"
            f"<i>{dots}  {t(lang, 'step', n=step, total=total)} · {t(lang, sub_key)}</i>")


def acc_label(a) -> str:
    return f"{a['icon']} {a['name']}"


def acc_full(a) -> str:
    """Label that also says whose account it is: '🏦 CBE (Partner)'."""
    return f"{a['icon']} {a['name']} ({esc(a['owner_name'])})" if a.get("owner_name") else acc_label(a)


def me(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Normalized phone of the current user (set by @registered_only)."""
    return context.user_data.get("me", "")


def balance_line(lang: str, a) -> str:
    return t(lang, "balance_line", acc=acc_label(a), amt=money(a["balance"], lang))


def parse_amount(text: str, allow_zero: bool = False) -> float | None:
    try:
        x = float(text.replace(",", "").replace("ብር", "").replace("birr", "").replace("Birr", "").strip())
    except ValueError:
        return None
    if x < 0 or (x == 0 and not allow_zero) or x > 1e10:
        return None
    return x


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    b = lambda key: t(lang, f"btn_{key}")  # noqa: E731
    return ReplyKeyboardMarkup(
        [[b("expense"), b("income")], [b("transfer"), b("accounts")], [b("today"), b("month")],
         [b("history"), b("voice")], [b("undo"), b("help"), b("lang")]],
        resize_keyboard=True, is_persistent=True, input_field_placeholder=t(lang, "menu_placeholder"),
    )


def cancel_button(lang: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="cancel")


def category_keyboard(lang: str, kind: str) -> InlineKeyboardMarkup:
    items = list(CATEGORIES[kind])
    rows = [[InlineKeyboardButton(cat_label(lang, kind, k), callback_data=f"cat:{k}") for k in items[i:i + 2]]
            for i in range(0, len(items), 2)]
    rows.append([cancel_button(lang)])
    return InlineKeyboardMarkup(rows)


def empty_button(a) -> InlineKeyboardButton:
    """Red, unselectable chip for an account without enough money."""
    return InlineKeyboardButton(f"🚫 {a['name']} · {short_money(max(a['balance'], 0))}",
                                callback_data=f"acc_no:{a['id']}", style=RED)


def accounts_keyboard(lang: str, prefix: str, accs: list, viewer: str,
                      need_money: bool = False) -> InlineKeyboardMarkup:
    """Own accounts show their balance; family members' accounts show the owner's name."""
    buttons = []
    for a in accs:
        if need_money and a["balance"] <= 0:
            buttons.append(empty_button(a))
        elif a["owner"] and a["owner"] != viewer:
            buttons.append(InlineKeyboardButton(f"👤 {a['owner_name']} · {a['name']}", callback_data=f"{prefix}:{a['id']}"))
        else:
            buttons.append(InlineKeyboardButton(f"{acc_label(a)} · {short_money(a['balance'])}",
                                                callback_data=f"{prefix}:{a['id']}"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([cancel_button(lang)])
    return InlineKeyboardMarkup(rows)


async def save_voice_copy(bot, file_id: str, prefix: str) -> str | None:
    """Keep a local backup of the voice note (best effort)."""
    try:
        VOICE_DIR.mkdir(exist_ok=True)
        path = VOICE_DIR / f"{prefix}_{db.now_local():%Y%m%d_%H%M%S}.ogg"
        await (await bot.get_file(file_id)).download_to_drive(path)
        return str(path)
    except Exception as e:
        log.warning("Voice backup failed: %s", e)
        return None


# ═════════════════════════ access ═════════════════════════

def is_allowed(phone: str) -> bool:
    return not ALLOWED_PHONES or normalize_phone(phone) in ALLOWED_PHONES


def family():
    return [u for u in db.all_users() if is_allowed(u["phone"])]


def registered_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        user = db.get_user(update.effective_user.id)
        lang = user["lang"] if user else L(context)
        if not user:
            await context.bot.send_message(update.effective_chat.id, t(lang, "press_start"))
            return ConversationHandler.END
        if not is_allowed(user["phone"]):
            await context.bot.send_message(update.effective_chat.id, t(lang, "private"),
                                           reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        context.user_data["lang"] = user["lang"]
        context.user_data["me"] = normalize_phone(user["phone"])
        return await func(update, context, *a, **kw)
    return wrapper


async def notify_others(context: ContextTypes.DEFAULT_TYPE, sender_id: int,
                        build: Callable[[str], str], voice_id: str | None = None,
                        build_for: Callable[[dict], str | None] | None = None) -> list[tuple[int, int]]:
    """build(lang) -> text, so every family member gets it in their own language.
    build_for(user) can return a personal message for a specific member instead.
    Returns the (chat_id, message_id) of every message sent."""
    sent = []
    for u in family():
        if u["telegram_id"] == sender_id:
            continue
        text = (build_for(u) if build_for else None) or build(u["lang"])
        try:
            if voice_id:
                m = await context.bot.send_voice(u["chat_id"], voice_id, caption=text, parse_mode=HTML)
            else:
                m = await context.bot.send_message(u["chat_id"], text, parse_mode=HTML)
            sent.append((u["chat_id"], m.message_id))
        except Exception as e:
            log.warning("Could not notify %s: %s", u["name"], e)
    return sent


# ═════════════════════════ clean chat ═════════════════════════
# • home message: carries the menu keyboard and is never deleted (deleting it would close the menu)
# • view message: the latest report/list; a new view replaces the old one
# • flow message: the form being filled in, edited step by step
# • the user's commands, menu taps and typed answers are deleted after use

async def delete_quietly(message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def delete_id(context: ContextTypes.DEFAULT_TYPE, chat_id: int, msg_id: int | None) -> None:
    if msg_id:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass


async def send_home(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    old = context.user_data.get("home_msg")
    msg = await context.bot.send_message(chat_id, text, parse_mode=HTML, reply_markup=main_menu(L(context)))
    context.user_data["home_msg"] = msg.message_id
    await delete_id(context, chat_id, old)


async def show_view(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, kb=None,
                    kind: str | None = None) -> None:
    """kind = a live view (accounts/today/month/history/voice) that refresh_views() keeps up to date."""
    await delete_id(context, chat_id, context.user_data.pop("view_msg", None))
    msg = await context.bot.send_message(chat_id, text, parse_mode=HTML, reply_markup=kb)
    context.user_data["view_msg"] = msg.message_id
    context.user_data["view_kind"] = kind


async def open_live_view(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> None:
    text, kb = render_view(kind, L(context))
    await show_view(context, update.effective_chat.id, text, kb, kind=kind)


async def refresh_views(context: ContextTypes.DEFAULT_TYPE) -> None:
    """After any change, re-draw every family member's open live view in place."""
    for u in family():
        ud = context.application.user_data.get(u["telegram_id"])
        if not ud or not ud.get("view_msg") or ud.get("view_kind") not in LIVE_VIEWS:
            continue
        text, kb = render_view(ud["view_kind"], u["lang"])
        try:
            await context.bot.edit_message_text(text, u["chat_id"], ud["view_msg"], parse_mode=HTML, reply_markup=kb)
        except Exception as e:
            if "not modified" not in str(e).lower():  # message gone: stop tracking it
                ud.pop("view_msg", None)
                ud.pop("view_kind", None)


async def drop_old_flow(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    await delete_id(context, chat_id, context.user_data.pop("flow_msg", None))
    for key in ("tx", "tr", "sb", "note_tx"):
        context.user_data.pop(key, None)


async def _delete_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, msg_id = context.job.data
    await delete_id(context, chat_id, msg_id)


def delete_later(context: ContextTypes.DEFAULT_TYPE, chat_id: int, msg_id: int, seconds: float) -> None:
    """Short-lived confirmations remove themselves."""
    context.job_queue.run_once(_delete_job, seconds, data=(chat_id, msg_id))


def track(context: ContextTypes.DEFAULT_TYPE, key: str, sent: list[tuple[int, int]]) -> None:
    """Remember the chat messages that show a record (receipt + notifications) so undo can remove them."""
    context.bot_data.setdefault("rec_msgs", {}).setdefault(key, []).extend([list(s) for s in sent])


async def untrack_and_delete(context: ContextTypes.DEFAULT_TYPE, key: str) -> None:
    for chat_id, msg_id in context.bot_data.get("rec_msgs", {}).pop(key, []):
        await delete_id(context, chat_id, msg_id)


async def open_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, kb) -> None:
    """Start a form. Any open report/list (e.g. Account Balances) is cleared first."""
    chat_id = update.effective_chat.id
    await drop_old_flow(context, chat_id)
    await delete_id(context, chat_id, context.user_data.pop("view_msg", None))
    context.user_data.pop("view_kind", None)
    if update.callback_query:
        await update.callback_query.answer()
    msg = await context.bot.send_message(chat_id, text, parse_mode=HTML, reply_markup=kb)
    context.user_data["flow_msg"] = msg.message_id


async def edit_flow(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, kb=None) -> None:
    msg_id = context.user_data.get("flow_msg")
    if not msg_id:
        return
    try:
        await context.bot.edit_message_text(text, chat_id, msg_id, parse_mode=HTML, reply_markup=kb)
    except Exception as e:  # "message is not modified" etc.
        log.debug("edit_flow: %s", e)


async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs after every handler: removes commands, menu taps, shared contacts and
    anything the bot doesn't use (photos, files, stickers, videos, locations…).
    Only text and voice messages are ever kept."""
    msg = update.message
    if not msg:
        return
    if msg.voice:
        return  # voice notes are records
    if not msg.text or msg.text.startswith("/") or msg.text in LABEL_TO_ACTION:
        await delete_quietly(msg)


# ═════════════════════════ registration ═════════════════════════

def intro_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(t(lang, "btn_share_phone"), request_contact=True)],
                                [t(lang, "btn_switch_lang")]], resize_keyboard=True)


async def _reg_send(context, chat_id: int, text: str, kb) -> None:
    msg = await context.bot.send_message(chat_id, text, parse_mode=HTML, reply_markup=kb)
    context.user_data.setdefault("reg_msgs", []).append(msg.message_id)


async def _reg_clear(context, chat_id: int) -> None:
    for mid in context.user_data.pop("reg_msgs", []):
        await delete_id(context, chat_id, mid)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_user(update.effective_user.id)
    if user and is_allowed(user["phone"]):
        context.user_data["lang"] = user["lang"]
        await drop_old_flow(context, chat_id)
        await delete_id(context, chat_id, context.user_data.pop("view_msg", None))
        await send_home(context, chat_id, t(user["lang"], "welcome_back", name=esc(user["name"])))
        return ConversationHandler.END

    lang = L(context)
    await _reg_clear(context, chat_id)
    await _reg_send(context, chat_id, t(lang, "intro"), intro_keyboard(lang))
    return PHONE


async def phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await delete_quietly(update.message)
    await _reg_clear(context, chat_id)
    if update.message.text in all_labels("btn_switch_lang"):
        context.user_data["lang"] = "en" if L(context) == "am" else "am"
        await _reg_send(context, chat_id, t(L(context), "intro"), intro_keyboard(L(context)))
    else:
        await _reg_send(context, chat_id, t(L(context), "phone_needed"), intro_keyboard(L(context)))
    return PHONE


async def got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, lang = update.effective_chat.id, L(context)
    contact = update.message.contact
    await _reg_clear(context, chat_id)
    if contact.user_id != update.effective_user.id:
        await _reg_send(context, chat_id, t(lang, "own_number"), intro_keyboard(lang))
        return PHONE
    if not is_allowed(contact.phone_number):
        await context.bot.send_message(chat_id, t(lang, "private"), reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    context.user_data["phone"] = contact.phone_number
    existing = db.get_user(update.effective_user.id)
    suggested = (existing["name"] if existing else
                 PEOPLE_NAMES.get(normalize_phone(contact.phone_number)) or update.effective_user.first_name) or ""
    kb = (ReplyKeyboardMarkup([[suggested]], resize_keyboard=True, one_time_keyboard=True)
          if suggested else ReplyKeyboardRemove())
    await _reg_send(context, chat_id, t(lang, "ask_name"), kb)
    return NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, lang = update.effective_chat.id, L(context)
    name = update.message.text.strip()[:30]
    await delete_quietly(update.message)
    await _reg_clear(context, chat_id)
    is_new = db.get_user(update.effective_user.id) is None
    db.save_user(update.effective_user.id, chat_id, context.user_data.pop("phone"), name, lang)
    await send_home(context, chat_id, t(lang, "registered", name=esc(name)))
    if is_new:
        await notify_others(context, update.effective_user.id, lambda lg: t(lg, "joined", name=esc(name)))
    return ConversationHandler.END


# ═════════════════════════ language ═════════════════════════

@registered_only
async def lang_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(("✓ " if lang == "en" else "") + "🇬🇧 English", callback_data="lang:en",
                             style=BLUE if lang == "en" else None),
        InlineKeyboardButton(("✓ " if lang == "am" else "") + "🇪🇹 አማርኛ", callback_data="lang:am",
                             style=BLUE if lang == "am" else None),
    ]])
    await show_view(context, update.effective_chat.id, t(lang, "lang_title"), kb)


async def lang_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    new = q.data.split(":")[1]
    await q.answer()
    if db.get_user(update.effective_user.id):
        db.set_lang(update.effective_user.id, new)
    context.user_data["lang"] = new
    await delete_quietly(q.message)
    context.user_data.pop("view_msg", None)
    await send_home(context, update.effective_chat.id, t(new, "lang_set"))


# ═════════════════════════ add expense / income ═════════════════════════

def can_pay(tx: dict, acc) -> bool:
    return tx["kind"] == "income" or acc["balance"] >= tx["amount"]


def pick_default_account(tx: dict, user_id: int) -> int | None:
    """Last used account if it can pay, otherwise the richest one that can. None = nobody can."""
    accs = db.accounts(tx.get("owner"))
    last = db.last_account_for(user_id, tx["kind"])
    for a in accs:
        if a["id"] == last and can_pay(tx, a):
            return a["id"]
    ok = [a for a in accs if can_pay(tx, a)]
    return max(ok, key=lambda a: a["balance"])["id"] if ok else None


def amount_prompt(lang: str, head: str, body: str, error: bool = False) -> str:
    warn = f"\n\n{t(lang, 'bad_amount')}" if error else ""
    return f"{head}\n\n{body}\n\n{t(lang, 'enter_amount')}{warn}"


def tx_confirm_view(lang: str, tx: dict) -> tuple[str, InlineKeyboardMarkup]:
    accs = db.accounts(tx.get("owner"))  # only your own accounts
    acc = next((a for a in accs if a["id"] == tx.get("account_id")), None)
    head = (f"{step_header(lang, tx['kind'], 3, 's_confirm', 3)}\n\n"
            f"📂 {cat_label(lang, tx['kind'], tx['category'])}\n"
            f"💵 <b>{money(tx['amount'], lang)}</b>\n")

    chips = []
    for a in accs:
        if not can_pay(tx, a):
            chips.append(empty_button(a))
        else:
            sel = acc is not None and a["id"] == acc["id"]
            chips.append(InlineKeyboardButton(f"{'✓ ' if sel else ''}{a['name']} · {short_money(a['balance'])}",
                                              callback_data=f"acc:{a['id']}", style=BLUE if sel else None))
    rows = [chips[i:i + 2] for i in range(0, len(chips), 2)]

    if acc is None:
        text = head + "\n" + t(lang, "no_account_money")
        rows.append([InlineKeyboardButton(t(lang, "btn_fix_balance"), callback_data="sb_start")])
    else:
        after = acc["balance"] + (tx["amount"] if tx["kind"] == "income" else -tx["amount"])
        text = (head + f"{acc['icon']} {t(lang, 'dir_' + tx['kind'])} <b>{esc(acc['name'])}</b>\n"
                f"└ <i>{t(lang, 'balance_change', a=money(acc['balance'], lang), b=money(after, lang))}</i>\n\n"
                f"<i>{t(lang, 'change_account')}</i>")
        if tx["kind"] == "expense" and any(not can_pay(tx, a) for a in accs):
            text += f"\n<i>{t(lang, 'red_not_enough')}</i>"
        rows.append([InlineKeyboardButton(t(lang, "btn_save"), callback_data="save", style=GREEN)])
    rows.append([cancel_button(lang)])
    return text, InlineKeyboardMarkup(rows)


def tx_receipt(lang: str, tx_id: int) -> tuple[str, InlineKeyboardMarkup]:
    tr = db.get_tx(tx_id)
    stamp = tr["created_at"]
    acc = db.get_account(tr["account_id"]) if tr["account_id"] else None
    day_total = db.user_day_total_until(tr["user_id"], tr["kind"], stamp, tx_id)
    k = kname(lang, tr["kind"])
    lines = [t(lang, "saved_title", kind=k), DIVIDER,
             f"{ICON[tr['kind']]} <b>{money(tr['amount'], lang)}</b>",
             f"📂 {cat_label(lang, tr['kind'], tr['category'])}"]
    if tr["note"]:
        lines.append(f"📝 {esc(tr['note'])}")
    if tr["voice_file_id"]:
        lines.append(t(lang, "voice_label"))
    lines += [f"🕒 {when(lang, tr['created_at'])}", DIVIDER]
    if acc:
        lines.append(t(lang, "balance_after", acc=acc_label(acc),
                       amt=money(db.balance_as_of(acc["id"], stamp, tx_id=tx_id), lang)))
    day = et.short_date(datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").date(), lang)
    lines.append(f"<i>{t(lang, 'day_total', kind=k.lower() if lang == 'en' else k, date=day, amt=money(day_total, lang))}</i>")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_add_note"), callback_data=f"note:{tx_id}")]])
    return "\n".join(lines), kb


@registered_only
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    kind = LABEL_TO_ACTION.get(update.message.text, "expense")
    await open_flow(update, context, step_header(lang, kind, 1, "s_category", 3), category_keyboard(lang, kind))
    context.user_data["tx"] = {"kind": kind, "owner": me(context)}
    return CATEGORY


async def got_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    await q.answer()
    tx = context.user_data["tx"]
    tx["category"] = q.data.split(":", 1)[1]
    await edit_flow(context, update.effective_chat.id,
                    amount_prompt(lang, step_header(lang, tx["kind"], 2, "s_amount", 3),
                                  f"📂 {cat_label(lang, tx['kind'], tx['category'])}"),
                    InlineKeyboardMarkup([[cancel_button(lang)]]))
    return AMOUNT


async def got_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    await delete_quietly(update.message)
    tx = context.user_data["tx"]
    amount = parse_amount(update.message.text)
    if amount is None:
        await edit_flow(context, update.effective_chat.id,
                        amount_prompt(lang, step_header(lang, tx["kind"], 2, "s_amount", 3),
                                      f"📂 {cat_label(lang, tx['kind'], tx['category'])}", error=True),
                        InlineKeyboardMarkup([[cancel_button(lang)]]))
        return AMOUNT
    tx["amount"] = amount
    tx["account_id"] = pick_default_account(tx, update.effective_user.id)
    await edit_flow(context, update.effective_chat.id, *tx_confirm_view(lang, tx))
    return CONFIRM


async def account_empty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tap on a red account chip."""
    lang = L(context)
    acc = db.get_account(int(update.callback_query.data.split(":")[1]))
    await update.callback_query.answer(
        t(lang, "not_enough_alert", name=acc["name"], amt=money(max(acc["balance"], 0), lang)), show_alert=True)


async def pick_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    tx = context.user_data["tx"]
    acc = db.get_account(int(q.data.split(":")[1]))
    if tx.get("owner") and acc["owner"] not in (tx["owner"], "") or not can_pay(tx, acc):
        return await account_empty(update, context)
    await q.answer()
    tx["account_id"] = acc["id"]
    await edit_flow(context, update.effective_chat.id, *tx_confirm_view(lang, tx))
    return CONFIRM


async def save_tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    tx = context.user_data["tx"]
    acc = db.get_account(tx["account_id"]) if tx.get("account_id") else None
    if acc is None or not can_pay(tx, acc):  # balance changed meanwhile
        await q.answer(t(lang, "not_enough"), show_alert=True)
        tx["account_id"] = pick_default_account(tx, update.effective_user.id)
        await edit_flow(context, update.effective_chat.id, *tx_confirm_view(lang, tx))
        return CONFIRM
    await q.answer(t(lang, "toast_saved"))
    context.user_data.pop("tx")
    context.user_data.pop("flow_msg", None)  # the receipt stays in the chat
    user = db.get_user(update.effective_user.id)
    tx_id = db.add_tx(user["telegram_id"], tx["kind"], tx["amount"], tx["category"], None, None, tx["account_id"])
    text, kb = tx_receipt(lang, tx_id)
    await q.edit_message_text(text, parse_mode=HTML, reply_markup=kb)
    await refresh_views(context)

    acc = db.get_account(tx["account_id"])
    sent = await notify_others(context, user["telegram_id"], lambda lg: (
        f"{t(lg, 'notify_new', new=t(lg, 'kn_' + tx['kind']), name=esc(user['name']))}\n"
        f"{ICON[tx['kind']]} <b>{money(tx['amount'], lg)}</b>  ·  {cat_label(lg, tx['kind'], tx['category'])}\n"
        f"{acc_full(acc)}"))
    track(context, f"tx:{tx_id}", [(update.effective_chat.id, q.message.message_id), *sent])
    return ConversationHandler.END


# ---------- optional note after saving ----------

@registered_only
async def note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    tx_id = int(q.data.split(":")[1])
    row = db.get_tx(tx_id)
    if not row or row["user_id"] != update.effective_user.id:
        await q.answer(t(lang, "note_owner_only"), show_alert=True)
        return ConversationHandler.END
    await q.answer()
    await drop_old_flow(context, update.effective_chat.id)
    context.user_data["note_tx"] = tx_id
    context.user_data["flow_msg"] = q.message.message_id
    text, _ = tx_receipt(lang, tx_id)
    await edit_flow(context, update.effective_chat.id, f"{text}\n\n{t(lang, 'note_prompt')}",
                    InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data=f"note_back:{tx_id}")]]))
    return NOTE


async def note_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang, msg = L(context), update.message
    tx_id = context.user_data.pop("note_tx")
    uid = update.effective_user.id
    voice_id = msg.voice.file_id if msg.voice else None
    note = None if voice_id else msg.text.strip()[:120]
    db.set_tx_note(tx_id, uid, note=note, voice_file_id=voice_id)
    if voice_id:
        await save_voice_copy(context.bot, voice_id, f"tx_{uid}")
    await delete_quietly(msg)
    await edit_flow(context, update.effective_chat.id, *tx_receipt(lang, tx_id))
    context.user_data.pop("flow_msg", None)
    await refresh_views(context)

    row, user = db.get_tx(tx_id), db.get_user(uid)
    sent = await notify_others(context, uid, lambda lg: (
        f"{t(lg, 'notify_note', name=esc(user['name']))}\n"
        f"{ICON[row['kind']]} <b>{money(row['amount'], lg)}</b>  ·  {cat_label(lg, row['kind'], row['category'])}"
        + (f"\n📝 {esc(note)}" if note else "")), voice_id=voice_id)
    track(context, f"tx:{tx_id}", sent)
    return ConversationHandler.END


async def note_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    await q.answer()
    tx_id = int(q.data.split(":")[1])
    if context.user_data.get("flow_msg") == q.message.message_id:
        context.user_data.pop("note_tx", None)
        context.user_data.pop("flow_msg", None)
    text, kb = tx_receipt(lang, tx_id)
    await q.edit_message_text(text, parse_mode=HTML, reply_markup=kb)
    return ConversationHandler.END


# ═════════════════════════ transfers ═════════════════════════

@registered_only
async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    viewer = me(context)
    await open_flow(update, context,
                    f"{step_header(lang, 'transfer', 1, 's_from', 4)}\n\n{t(lang, 'tr_from_q')}\n"
                    f"<i>{t(lang, 'red_empty')}</i>",
                    accounts_keyboard(lang, "tr_from", db.accounts(viewer), viewer, need_money=True))
    context.user_data["tr"] = {}
    return TR_FROM


def tr_label(a, viewer: str) -> str:
    """Your own account: '🏦 CBE'. Someone else's: '🏦 CBE (Partner)'."""
    return acc_full(a) if a["owner"] and a["owner"] != viewer else acc_label(a)


async def transfer_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang, viewer = update.callback_query, L(context), me(context)
    src = db.get_account(int(q.data.split(":")[1]))
    if src["balance"] <= 0 or (viewer and src["owner"] not in (viewer, "")):
        return await account_empty(update, context)
    await q.answer()
    context.user_data["tr"] = {"from": src["id"]}
    targets = [a for a in db.accounts() if a["id"] != src["id"]]  # yours + family members'
    await edit_flow(context, update.effective_chat.id,
                    f"{step_header(lang, 'transfer', 2, 's_to', 4)}\n\n"
                    f"📤 {balance_line(lang, src)}\n\n{t(lang, 'tr_to_q')}",
                    accounts_keyboard(lang, "tr_to", targets, viewer))
    return TR_TO


def transfer_amount_view(lang: str, tr: dict, viewer: str, error: bool = False, too_much: bool = False) -> str:
    src, dst = db.get_account(tr["from"]), db.get_account(tr["to"])
    family_note = f"\n{t(lang, 'tr_family')}" if src["owner"] != dst["owner"] else ""
    text = amount_prompt(lang, step_header(lang, "transfer", 3, "s_amount", 4),
                         f"{acc_label(src)}  ➜  {tr_label(dst, viewer)}{family_note}\n"
                         f"<i>{t(lang, 'available', name=esc(src['name']), amt=money(src['balance'], lang))}</i>",
                         error)
    if too_much:
        text += "\n\n" + t(lang, "tr_too_much", amt=money(src["balance"], lang), name=esc(src["name"]))
    return text


async def transfer_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    await q.answer()
    tr = context.user_data["tr"]
    tr["to"] = int(q.data.split(":")[1])
    await edit_flow(context, update.effective_chat.id, transfer_amount_view(lang, tr, me(context)),
                    InlineKeyboardMarkup([[cancel_button(lang)]]))
    return TR_AMOUNT


async def transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang, viewer = L(context), me(context)
    await delete_quietly(update.message)
    tr = context.user_data["tr"]
    amount = parse_amount(update.message.text)
    cancel_kb = InlineKeyboardMarkup([[cancel_button(lang)]])
    if amount is None:
        await edit_flow(context, update.effective_chat.id, transfer_amount_view(lang, tr, viewer, error=True), cancel_kb)
        return TR_AMOUNT
    src, dst = db.get_account(tr["from"]), db.get_account(tr["to"])
    if amount > src["balance"]:
        await edit_flow(context, update.effective_chat.id, transfer_amount_view(lang, tr, viewer, too_much=True),
                        cancel_kb)
        return TR_AMOUNT
    tr["amount"] = amount
    family_note = f"\n{t(lang, 'tr_family')}" if src["owner"] != dst["owner"] else ""
    await edit_flow(context, update.effective_chat.id,
                    f"{step_header(lang, 'transfer', 4, 's_confirm', 4)}\n\n"
                    f"{acc_label(src)}  ➜  {tr_label(dst, viewer)}{family_note}\n"
                    f"💵 <b>{money(amount, lang)}</b>\n"
                    f"├ <i>{acc_label(src)}: {money(src['balance'], lang)} ➜ {money(src['balance'] - amount, lang)}</i>\n"
                    f"└ <i>{tr_label(dst, viewer)}: {money(dst['balance'], lang)} ➜ {money(dst['balance'] + amount, lang)}</i>",
                    InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_save"), callback_data="tr_save", style=GREEN)],
                                          [cancel_button(lang)]]))
    return TR_CONFIRM


async def transfer_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    tr = context.user_data["tr"]
    if db.get_account(tr["from"])["balance"] < tr["amount"]:  # balance changed meanwhile
        await q.answer(t(lang, "not_enough"), show_alert=True)
        await edit_flow(context, update.effective_chat.id, transfer_amount_view(lang, tr, me(context), too_much=True),
                        InlineKeyboardMarkup([[cancel_button(lang)]]))
        return TR_AMOUNT
    await q.answer(t(lang, "toast_saved"))
    context.user_data.pop("tr")
    context.user_data.pop("flow_msg", None)
    user, viewer = db.get_user(update.effective_user.id), me(context)
    tr_id = db.add_transfer(user["telegram_id"], tr["from"], tr["to"], tr["amount"])
    stamp = db.get_transfer(tr_id)["created_at"]
    src, dst = db.get_account(tr["from"]), db.get_account(tr["to"])
    bal = lambda a: db.balance_as_of(a["id"], stamp, tr_id=tr_id)  # noqa: E731
    family = src["owner"] != dst["owner"]
    await q.edit_message_text(
        f"{t(lang, 'tr_saved')}\n{DIVIDER}\n"
        f"🔄 <b>{money(tr['amount'], lang)}</b>\n"
        f"{acc_label(src)}  ➜  {tr_label(dst, viewer)}" + (f"\n{t(lang, 'tr_family')}" if family else "") + "\n"
        f"🕒 {when(lang, stamp)}\n{DIVIDER}\n"
        f"📤 {t(lang, 'balance_after', acc=acc_label(src), amt=money(bal(src), lang))}"
        + ("" if family else f"\n📥 {t(lang, 'balance_after', acc=acc_label(dst), amt=money(bal(dst), lang))}"),
        parse_mode=HTML,
    )
    await refresh_views(context)

    def personal(u) -> str | None:
        """The person who received the money gets a 'sent you' message."""
        if family and normalize_phone(u["phone"]) == dst["owner"]:
            return t(u["lang"], "notify_sent_you", name=esc(user["name"]), amt=money(tr["amount"], u["lang"]),
                     acc=acc_label(dst), bal=money(bal(dst), u["lang"]))
        return None

    sent = await notify_others(context, user["telegram_id"], lambda lg: (
        f"{t(lg, 'notify_transfer', name=esc(user['name']))}\n"
        f"🔄 <b>{money(tr['amount'], lg)}</b>  ·  {acc_full(src)} ➜ {acc_full(dst)}"), build_for=personal)
    track(context, f"tr:{tr_id}", [(update.effective_chat.id, q.message.message_id), *sent])
    return ConversationHandler.END


# ═════════════════════════ accounts & balance correction ═════════════════════════

def accounts_lines(lang: str) -> list[str]:
    """Balances grouped by person, each with a subtotal, then the family total."""
    accs = db.accounts()
    groups: dict[str, list] = {}
    for a in accs:
        groups.setdefault(a["owner"], []).append(a)
    lines = []
    for owner, items in groups.items():
        if owner:
            lines.append(f"👤 <b>{esc(items[0]['owner_name'])}</b> · <b>{money(sum(a['balance'] for a in items), lang)}</b>")
        lines += [f"{'└' if i == len(items) - 1 else '├'} {acc_label(a)} · {money(a['balance'], lang)}"
                  for i, a in enumerate(items)]
        lines.append("")
    label = t(lang, "family_total") if len(groups) > 1 else t(lang, "total")
    lines.append(f"🏡 <b>{label}</b> · <b>{money(sum(a['balance'] for a in accs), lang)}</b>")
    return lines


def updated_line(lang: str) -> str:
    return f"<i>{t(lang, 'updated', time=db.now_local().strftime('%H:%M'))}</i>"


def render_accounts(lang: str):
    lines = accounts_lines(lang)
    text = (f"{t(lang, 'acc_title')}\n<i>{et.long_date(today_local(), lang)}</i>\n\n"
            + "\n".join(lines[:-1]).rstrip() + f"\n{DIVIDER}\n" + lines[-1] + f"\n\n{updated_line(lang)}")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_transfer"), callback_data="tr_start"),
                                InlineKeyboardButton(t(lang, "btn_fix_balance"), callback_data="sb_start")]])
    return text, kb


@registered_only
async def accounts_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_live_view(update, context, "accounts")


@registered_only
async def setbal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang, viewer = L(context), me(context)
    await open_flow(update, context, f"{step_header(lang, 'setbal', 1, 's_account', 2)}\n\n{t(lang, 'sb_which')}",
                    accounts_keyboard(lang, "sb_acc", db.accounts(viewer), viewer))  # only your own
    return SB_ACCOUNT


def setbal_view(lang: str, acc, error: bool = False) -> str:
    warn = f"\n\n{t(lang, 'bad_amount')}" if error else ""
    return (f"{step_header(lang, 'setbal', 2, 's_amount', 2)}\n\n"
            f"{t(lang, 'sb_now', acc=acc_label(acc), amt=money(acc['balance'], lang))}\n\n"
            f"{t(lang, 'sb_enter')}{warn}")


async def setbal_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    acc = db.get_account(int(q.data.split(":")[1]))
    if me(context) and acc["owner"] not in (me(context), ""):
        await q.answer("⛔")
        return SB_ACCOUNT
    await q.answer()
    context.user_data["sb"] = acc["id"]
    await edit_flow(context, update.effective_chat.id, setbal_view(lang, acc),
                    InlineKeyboardMarkup([[cancel_button(lang)]]))
    return SB_AMOUNT


async def setbal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    await delete_quietly(update.message)
    acc_id = context.user_data["sb"]
    amount = parse_amount(update.message.text, allow_zero=True)
    if amount is None:
        await edit_flow(context, update.effective_chat.id, setbal_view(lang, db.get_account(acc_id), error=True),
                        InlineKeyboardMarkup([[cancel_button(lang)]]))
        return SB_AMOUNT
    before = db.get_account(acc_id)["balance"]
    db.set_balance(acc_id, amount)
    acc = db.get_account(acc_id)
    await edit_flow(context, update.effective_chat.id,
                    f"{t(lang, 'sb_done')}\n{DIVIDER}\n{acc_label(acc)}\n"
                    f"├ {t(lang, 'before')} · {money(before, lang)}\n└ {t(lang, 'now')} · <b>{money(acc['balance'], lang)}</b>\n"
                    f"🕒 {when(lang, db._stamp())}")
    context.user_data.pop("sb", None)
    delete_later(context, update.effective_chat.id, context.user_data.pop("flow_msg"), 6)  # a short confirmation
    await refresh_views(context)
    user = db.get_user(update.effective_user.id)
    sent = await notify_others(context, user["telegram_id"], lambda lg: t(
        lg, "notify_sb", name=esc(user["name"]), acc=acc_full(acc), amt=money(acc["balance"], lg)))
    for chat_id, msg_id in sent:  # the family member's notice also clears itself after a while
        delete_later(context, chat_id, msg_id, 10 * 60)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel = the form simply disappears."""
    if update.callback_query:
        q = update.callback_query
        await q.answer(t(L(context), "toast_cancelled"))
        await delete_quietly(q.message)
        if context.user_data.get("flow_msg") != q.message.message_id:
            return None  # an old, stale form: keep the current one going
        context.user_data.pop("flow_msg", None)
    await drop_old_flow(context, update.effective_chat.id)
    return ConversationHandler.END


# ═════════════════════════ reports ═════════════════════════

def build_report(lang: str, title: str, subtitle: str, start: date, end: date) -> str:
    s, e = start.isoformat(), end.isoformat()
    rows = db.totals_by_user(s, e)
    total_exp = sum(r["expense"] for r in rows)
    total_inc = sum(r["income"] for r in rows)
    balance = total_inc - total_exp

    moved = db.family_transfers(s, e)  # money given between family members

    out = [f"{title}\n<i>{subtitle}</i>\n"]
    if total_exp == 0 and total_inc == 0 and not moved:
        out.append(t(lang, "nothing_yet"))
        return "\n".join(out)

    show_share = total_exp and len(rows) > 1
    for r in rows:
        items = [f"💸 {t(lang, 'spent')} · <b>{money(r['expense'], lang)}</b>",
                 f"💰 {t(lang, 'earned')} · <b>{money(r['income'], lang)}</b>"]
        m = moved.get(normalize_phone(r["phone"]), {})
        if m.get("sent"):
            items.append(f"🤝 {t(lang, 'given')} · <b>{money(m['sent'], lang)}</b>")
        if m.get("received"):
            items.append(f"💝 {t(lang, 'received')} · <b>{money(m['received'], lang)}</b>")
        if show_share:
            items.append(f"<code>{bar(r['expense'], total_exp)}</code> {pct(r['expense'], total_exp)}")
        body = "\n".join(f"{'└' if i == len(items) - 1 else '├'} {x}" for i, x in enumerate(items))
        out.append(f"👤 <b>{esc(r['name'])}</b>\n{body}\n")

    out.append(f"{DIVIDER}\n🏡 <b>{t(lang, 'total')}</b>\n"
               f"├ 💸 {t(lang, 'spent')} · <b>{money(total_exp, lang)}</b>\n"
               f"├ 💰 {t(lang, 'earned')} · <b>{money(total_inc, lang)}</b>\n"
               f"└ {'🟢' if balance >= 0 else '🔴'} {t(lang, 'left')} · <b>{money(balance, lang)}</b>")

    cats = db.totals_by_category(s, e)
    if cats:
        out.append(f"{DIVIDER}\n{t(lang, 'top_spending')}")
        for c in cats[:5]:
            out.append(f"{cat_label(lang, 'expense', c['category'])} · <b>{money(c['total'], lang)}</b>\n"
                       f"└ <code>{bar(c['total'], total_exp)}</code> {pct(c['total'], total_exp)}")
    return "\n".join(out)


def render_today(lang: str):
    d = today_local()
    return (build_report(lang, t(lang, "today_title"), et.long_date(d, lang), d, d + timedelta(days=1))
            + f"\n\n{updated_line(lang)}", None)


def render_month(lang: str):
    d = today_local()
    start, end = et.month_range(d)
    return (build_report(lang, t(lang, "month_title"), et.month_name(d, lang), start, end)
            + f"\n\n{updated_line(lang)}", None)


@registered_only
async def report_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_live_view(update, context, "today")


@registered_only
async def report_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_live_view(update, context, "month")


def transfer_route(r) -> str:
    """'🏦 CBE ➜ 📱 telebirr', or with names when money moves between people."""
    if r["from_owner"] == r["to_owner"]:
        return f"{r['from_icon']} {esc(r['from_name'])} ➜ {r['to_icon']} {esc(r['to_name'])}"
    names = db.owner_names()
    return (f"{r['from_icon']} {esc(r['from_name'])} ({esc(names.get(r['from_owner'], ''))}) ➜ "
            f"{r['to_icon']} {esc(r['to_name'])} ({esc(names.get(r['to_owner'], ''))})")


@registered_only
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_live_view(update, context, "history")


def render_history(lang: str):
    items = [("tx", r) for r in db.recent_tx(15)] + [("tr", r) for r in db.recent_transfers(15)]
    items.sort(key=lambda it: it[1]["created_at"], reverse=True)
    items = items[:15]
    if not items:
        return t(lang, "no_records"), None

    out, play, current_day = [t(lang, "history_title")], [], None
    for typ, r in items:
        ts = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
        if ts.date() != current_day:
            current_day = ts.date()
            out.append(f"\n<b>— {day_label(lang, current_day)} —</b>")
        if typ == "tr":
            icon = "🤝" if r["from_owner"] != r["to_owner"] else "🔄"
            out.append(f"{icon} <b>{money(r['amount'], lang)}</b> · {transfer_route(r)}\n"
                       f"└ <i>{esc(r['name'])} · {ts:%H:%M}</i>")
            continue
        note = f" · <i>{esc(r['note'])}</i>" if r["note"] else " · 🎙️" if r["voice_file_id"] else ""
        acc = f" · {r['account_icon']} {esc(r['account_name'])}" if r["account_name"] else ""
        label = cat_label(lang, r["kind"], r["category"])
        out.append(f"{ICON[r['kind']]} <b>{money(r['amount'], lang)}</b> · {label}\n"
                   f"└ <i>{esc(r['name'])} · {ts:%H:%M}{acc}</i>{note}")
        if r["voice_file_id"]:
            play.append(InlineKeyboardButton(f"▶️ {money(r['amount'], lang)} · {label}", callback_data=f"play:tx:{r['id']}"))
    if play:
        out.append(f"\n{DIVIDER}\n{t(lang, 'play_hint')}")
    out.append(f"\n{updated_line(lang)}")
    return "\n".join(out), (InlineKeyboardMarkup([[b] for b in play[:8]]) if play else None)


@registered_only
async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang, uid = L(context), update.effective_user.id
    tx, tr = db.last_tx(uid), db.last_transfer(uid)
    if not tx and not tr:
        await show_view(context, update.effective_chat.id, t(lang, "undo_nothing"))
        return
    if tr and (not tx or tr["created_at"] >= tx["created_at"]):
        target = f"tr:{tr['id']}"
        body = (f"🔄 <b>{money(tr['amount'], lang)}</b>\n{transfer_route(tr)}\n"
                f"🕒 {when(lang, tr['created_at'])}")
    else:
        target = f"tx:{tx['id']}"
        note = f"\n📝 {esc(tx['note'])}" if tx["note"] else f"\n{t(lang, 'voice_label')}" if tx["voice_file_id"] else ""
        acc = f"\n{tx['account_icon']} {esc(tx['account_name'])}" if tx["account_name"] else ""
        body = (f"{ICON[tx['kind']]} <b>{money(tx['amount'], lang)}</b>\n"
                f"📂 {cat_label(lang, tx['kind'], tx['category'])}{acc}{note}\n"
                f"🕒 {when(lang, tx['created_at'])}")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_undo_yes"), callback_data=f"undo:{target}", style=RED),
                                InlineKeyboardButton(t(lang, "btn_back"), callback_data="undo:no")]])
    await show_view(context, update.effective_chat.id, f"{t(lang, 'undo_q')}\n{DIVIDER}\n{body}", kb)


async def undo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, lang = update.callback_query, L(context)
    parts = q.data.split(":")
    if parts[1] == "no":
        await q.answer("👌")
        await delete_quietly(q.message)
        return
    delete = db.delete_transfer if parts[1] == "tr" else db.delete_tx
    if delete(int(parts[2]), update.effective_user.id):
        await q.answer(t(lang, "toast_deleted"))
        await untrack_and_delete(context, f"{parts[1]}:{parts[2]}")  # its receipt + notifications go too
        await q.edit_message_text(t(lang, "deleted"), parse_mode=HTML)
        context.user_data.pop("view_msg", None)
        delete_later(context, update.effective_chat.id, q.message.message_id, 4)
        await refresh_views(context)
    else:
        await q.answer(t(lang, "already_deleted"))
        await delete_quietly(q.message)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    lang = user["lang"] if user else L(context)
    lines = [t(lang, "help_title"), DIVIDER]
    for key in ("expense", "income", "transfer", "accounts", "today", "month", "history", "voice", "undo", "lang"):
        lines.append(f"{t(lang, 'btn_' + key)}\n└ <i>{t(lang, 'h_' + key)}</i>")
    lines += [DIVIDER, t(lang, "h_footer")]
    await show_view(context, update.effective_chat.id, "\n".join(lines))


@registered_only
async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_quietly(update.message)
    await show_view(context, update.effective_chat.id, t(L(context), "use_menu"))


# ═════════════════════════ voice memos ═════════════════════════

@registered_only
async def voice_memo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang, v = L(context), update.message.voice
    user = db.get_user(update.effective_user.id)
    path = await save_voice_copy(context.bot, v.file_id, f"memo_{user['telegram_id']}")
    db.add_memo(user["telegram_id"], v.file_id, v.duration or 0, path)
    await show_view(context, update.effective_chat.id,
                    f"{t(lang, 'memo_saved')}\n└ <i>{mmss(v.duration or 0)} · {when(lang, db._stamp())}</i>\n\n"
                    + t(lang, "memo_hint", btn=t(lang, "btn_voice")))
    await refresh_views(context)
    await notify_others(context, user["telegram_id"], lambda lg: t(lg, "notify_memo", name=esc(user["name"])),
                        voice_id=v.file_id)


@registered_only
async def memos_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_live_view(update, context, "voice")


def render_memos(lang: str):
    rows = db.recent_memos(10)
    if not rows:
        return f"{t(lang, 'memos_title')}\n{DIVIDER}\n{t(lang, 'memos_empty')}", None
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"▶️ {r['name']} · {when(lang, r['created_at'])} · {mmss(r['duration'])}",
                              callback_data=f"play:memo:{r['id']}")] for r in rows])
    return (f"{t(lang, 'memos_title')}\n{t(lang, 'memos_sub', n=len(rows))}\n\n{t(lang, 'memos_rec')}"
            f"\n\n{updated_line(lang)}", kb)


LIVE_VIEWS = {"accounts": render_accounts, "today": render_today, "month": render_month,
              "history": render_history, "voice": render_memos}


def render_view(kind: str, lang: str):
    return LIVE_VIEWS[kind](lang)


async def play_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = db.get_user(update.effective_user.id)
    if not user or not is_allowed(user["phone"]):
        await q.answer("⛔")
        return
    lang = user["lang"]
    _, what, ident = q.data.split(":")
    if what == "memo":
        row = db.get_memo(int(ident))
        file_id = row["file_id"] if row else None
        caption = f"🎙️ <i>{when(lang, row['created_at'])}</i>" if row else ""
    else:
        row = db.get_tx(int(ident))
        file_id = row["voice_file_id"] if row else None
        caption = (f"{ICON[row['kind']]} <b>{money(row['amount'], lang)}</b> · "
                   f"{cat_label(lang, row['kind'], row['category'])}\n🕒 <i>{when(lang, row['created_at'])}</i>") if row else ""
    if not file_id:
        await q.answer(t(lang, "not_found"))
        return
    await q.answer("▶️")
    await context.bot.send_voice(update.effective_chat.id, file_id, caption=caption, parse_mode=HTML)


# ═════════════════════════ nightly summary (00:00) ═════════════════════════

async def nightly_summary(context: ContextTypes.DEFAULT_TYPE):
    today = today_local()
    yesterday = today - timedelta(days=1)
    month_start, _ = et.month_range(yesterday)
    month_spent = sum(r["expense"] for r in db.totals_by_user(month_start.isoformat(), today.isoformat()))
    memos = db.count_memos(yesterday.isoformat(), today.isoformat())

    for u in family():
        lang = u["lang"]
        text = build_report(lang, t(lang, "nightly_title"), et.long_date(yesterday, lang), yesterday, today)
        text += f"\n{DIVIDER}\n" + t(lang, "month_so_far", month=et.month_only(yesterday, lang),
                                     amt=money(month_spent, lang))
        if memos:
            text += "\n" + t(lang, "memos_yesterday", n=memos)
        text += f"\n{DIVIDER}\n{t(lang, 'acc_title')}\n" + "\n".join(accounts_lines(lang))
        text += f"\n\n{t(lang, 'good_night')}"
        try:
            await context.bot.send_message(u["chat_id"], text, parse_mode=HTML)
        except Exception as e:
            log.warning("Nightly summary to %s failed: %s", u["name"], e)


# ═════════════════════════ bot profile ═════════════════════════

COMMANDS = [
    ("start", "🏡 Start", "🏡 ጀምር"),
    ("today", "📊 Today's report", "📊 የዛሬ ሪፖርት"),
    ("month", "📅 Monthly report", "📅 የወሩ ሪፖርት"),
    ("accounts", "🏦 Account balances", "🏦 የሂሳብ ቀሪዎች"),
    ("transfer", "🔄 Transfer", "🔄 ዝውውር"),
    ("history", "🧾 Recent records", "🧾 የቅርብ መዝገቦች"),
    ("voice", "🎙️ Voice notes", "🎙️ የድምፅ ማስታወሻዎች"),
    ("undo", "↩️ Undo last", "↩️ የመጨረሻውን አጥፋ"),
    ("language", "🌐 Language", "🌐 ቋንቋ"),
    ("cancel", "✖️ Cancel", "✖️ አቋርጥ"),
    ("help", "ℹ️ Help", "ℹ️ እገዛ"),
]


async def setup_profile(app: Application) -> None:
    await app.bot.set_my_commands([BotCommand(c, en) for c, en, _ in COMMANDS])
    await app.bot.set_my_commands([BotCommand(c, am) for c, _, am in COMMANDS], language_code="am")
    await app.bot.set_my_short_description("🏡 Family budget · 💸 expenses, 💰 income, 🏦 accounts")
    await app.bot.set_my_short_description("🏡 የቤተሰብ የገንዘብ መዝገብ · 💸 ወጪ እና 💰 ገቢ", language_code="am")
    await app.bot.set_my_description(
        "🏡 Family Budget\n\n💸 Track expenses and 💰 income together\n🔄 Record transfers between accounts\n"
        "🔔 Get notified when your family records something\n🌙 Daily summary every midnight\n\nPress «Start» 👇")
    await app.bot.set_my_description(
        "🏡 የቤተሰብ የገንዘብ መዝገብ\n\n💸 ወጪ እና 💰 ገቢዎን በቀላሉ ይመዝግቡ\n🔄 በሂሳቦች መካከል ዝውውር ይመዝግቡ\n"
        "🔔 የቤተሰብ አባል ሲመዘግብ ይነገርዎታል\n🌙 በየቀኑ እኩለ ሌሊት ማጠቃለያ\n\nለመጀመር «Start» ይጫኑ 👇",
        language_code="am")


# ═════════════════════════ wiring ═════════════════════════

def build_application() -> Application:
    persistence = PicklePersistence(filepath=STATE_PATH)
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

    def labels(*actions: str) -> filters.Regex:
        opts = [lbl for a in actions for lbl in all_labels(f"btn_{a}")]
        return filters.Regex("^(" + "|".join(re.escape(x) for x in opts) + ")$")

    menu_buttons = filters.Regex("^(" + "|".join(re.escape(x) for x in LABEL_TO_ACTION) + ")$")
    text_input = filters.TEXT & ~filters.COMMAND & ~menu_buttons
    cancel_handlers = [CommandHandler("cancel", cancel), CallbackQueryHandler(cancel, pattern="^cancel$")]

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, got_phone), MessageHandler(text_input, phone_text)],
            NAME: [MessageHandler(text_input, got_name)],
        },
        fallbacks=cancel_handlers,
        allow_reentry=True,
        name="register", persistent=True,
    ))

    # One conversation for every form, so starting a new form always replaces an unfinished one.
    app.add_handler(ConversationHandler(
        entry_points=[
            MessageHandler(labels("expense", "income"), add_start),
            MessageHandler(labels("transfer"), transfer_start),
            CommandHandler("transfer", transfer_start),
            CallbackQueryHandler(transfer_start, pattern="^tr_start$"),
            CallbackQueryHandler(setbal_start, pattern="^sb_start$"),
            CallbackQueryHandler(note_start, pattern=r"^note:\d+$"),
        ],
        states={
            CATEGORY: [CallbackQueryHandler(got_category, pattern=r"^cat:\w+$")],
            AMOUNT: [MessageHandler(text_input, got_amount)],
            CONFIRM: [CallbackQueryHandler(pick_account, pattern=r"^acc:\d+$"),
                      CallbackQueryHandler(save_tx, pattern="^save$")],
            NOTE: [MessageHandler(text_input | filters.VOICE, note_save),
                   CallbackQueryHandler(note_back, pattern=r"^note_back:\d+$")],
            TR_FROM: [CallbackQueryHandler(transfer_from, pattern=r"^tr_from:\d+$")],
            TR_TO: [CallbackQueryHandler(transfer_to, pattern=r"^tr_to:\d+$")],
            TR_AMOUNT: [MessageHandler(text_input, transfer_amount)],
            TR_CONFIRM: [CallbackQueryHandler(transfer_save, pattern="^tr_save$")],
            SB_ACCOUNT: [CallbackQueryHandler(setbal_account, pattern=r"^sb_acc:\d+$")],
            SB_AMOUNT: [MessageHandler(text_input, setbal_amount)],
        },
        fallbacks=cancel_handlers,
        allow_reentry=True,
        name="flows", persistent=True,
    ))

    for cmd, action, fn in [("today", "today", report_today), ("month", "month", report_month),
                            ("accounts", "accounts", accounts_view), ("history", "history", history),
                            ("undo", "undo", undo), ("voice", "voice", memos_list),
                            ("language", "lang", lang_menu), ("help", "help", help_cmd)]:
        app.add_handler(CommandHandler(cmd, fn))
        app.add_handler(MessageHandler(labels(action), fn))

    app.add_handler(MessageHandler(filters.VOICE, voice_memo))
    app.add_handler(CallbackQueryHandler(play_voice, pattern=r"^play:(memo|tx):\d+$"))
    app.add_handler(CallbackQueryHandler(undo_confirm, pattern=r"^undo:(no|tx:\d+|tr:\d+)$"))
    app.add_handler(CallbackQueryHandler(lang_pick, pattern=r"^lang:(en|am)$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))  # stale cancel buttons
    app.add_handler(CallbackQueryHandler(note_back, pattern=r"^note_back:\d+$"))
    app.add_handler(CallbackQueryHandler(account_empty, pattern=r"^acc_no:\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))

    app.add_handler(MessageHandler(filters.ALL, cleanup), group=1)  # runs after the handlers above

    app.job_queue.run_daily(nightly_summary, time=time(0, 0, tzinfo=TZ), name="nightly_summary")
    return app
