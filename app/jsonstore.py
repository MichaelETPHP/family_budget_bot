"""One live JSON file with everything: people, accounts, balances, transactions, transfers, voice notes.

• Rewritten automatically (atomically) after every change in the database.
• Can be downloaded (GET /api/export) or edited and loaded back (python -m app.admin import <file>).
SQLite stays the engine underneath: it is safe when two people save at the same moment.
"""
import json
import logging
import os
import tempfile
from datetime import datetime

from . import db
from . import ethiopian as et
from .config import DATA_DIR, TZ, normalize_phone

SCHEMA = "family-budget/v1"
JSON_PATH = os.path.join(DATA_DIR, "family_budget.json")
log = logging.getLogger(__name__)
_paused = False


def _eth(stamp: str) -> str:
    d = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").date()
    y, m, day = et.to_ethiopian(d)
    return f"{y:04d}-{m:02d}-{day:02d}"


def build_snapshot() -> dict:
    with db.conn() as c:
        users = [dict(r) for r in c.execute("SELECT * FROM users ORDER BY created_at")]
        txs = [dict(r) for r in c.execute("SELECT * FROM transactions ORDER BY id")]
        trs = [dict(r) for r in c.execute("SELECT * FROM transfers ORDER BY id")]
        memos = [dict(r) for r in c.execute("SELECT * FROM memos ORDER BY id")]
    accounts = db.accounts()
    acc_by_id = {a["id"]: a for a in accounts}
    name_by_uid = {u["telegram_id"]: u["name"] for u in users}

    people = [{"telegram_id": u["telegram_id"], "phone": u["phone"], "name": u["name"],
               "language": u["lang"], "joined_at": u["created_at"]} for u in users]

    acc_out = [{"id": a["id"], "owner_phone": "0" + a["owner"] if a["owner"] else "", "owner": a["owner_name"],
                "name": a["name"], "icon": a["icon"], "opening_balance": round(a["initial"], 2),
                "balance": round(a["balance"], 2)} for a in accounts]

    tx_out = [{"id": t["id"], "type": t["kind"], "amount": t["amount"], "category": t["category"],
               "note": t["note"], "voice_file_id": t["voice_file_id"],
               "account_id": t["account_id"],
               "account": acc_by_id[t["account_id"]]["name"] if t["account_id"] in acc_by_id else None,
               "user_id": t["user_id"], "by": name_by_uid.get(t["user_id"]),
               "created_at": t["created_at"], "ethiopian_date": _eth(t["created_at"])} for t in txs]

    tr_out = []
    for r in trs:
        f, to = acc_by_id.get(r["from_id"]), acc_by_id.get(r["to_id"])
        tr_out.append({"id": r["id"], "amount": r["amount"], "from_account_id": r["from_id"],
                       "to_account_id": r["to_id"],
                       "from": f"{f['name']} ({f['owner_name']})" if f else None,
                       "to": f"{to['name']} ({to['owner_name']})" if to else None,
                       "family_transfer": bool(f and to and f["owner"] != to["owner"]),
                       "note": r.get("note"), "voice_file_id": r.get("voice_file_id"),
                       "user_id": r["user_id"], "by": name_by_uid.get(r["user_id"]),
                       "created_at": r["created_at"], "ethiopian_date": _eth(r["created_at"])})

    memo_out = [{"id": m["id"], "user_id": m["user_id"], "by": name_by_uid.get(m["user_id"]),
                 "file_id": m["file_id"], "duration_sec": m["duration"], "created_at": m["created_at"]}
                for m in memos]

    # ---- summary ----
    today = db.now_local().date()
    m_start, m_end = et.month_range(today)
    per_person = {}
    for a in accounts:
        p = per_person.setdefault(a["owner_name"] or "shared", {"balance": 0.0, "accounts": {}})
        p["balance"] = round(p["balance"] + a["balance"], 2)
        p["accounts"][a["name"]] = round(a["balance"], 2)
    month = db.totals_by_user(m_start.isoformat(), m_end.isoformat())

    return {
        "schema": SCHEMA,
        "generated_at": db.now_local().isoformat(timespec="seconds"),
        "timezone": str(TZ),
        "currency": "ETB",
        "summary": {
            "family_total": round(sum(a["balance"] for a in accounts), 2),
            "people": per_person,
            "this_month": {
                "ethiopian_month": et.month_name(today, "en"),
                "spent": round(sum(r["expense"] for r in month), 2),
                "earned": round(sum(r["income"] for r in month), 2),
                "by_person": {r["name"]: {"spent": r["expense"], "earned": r["income"]} for r in month},
            },
            "counts": {"transactions": len(tx_out), "transfers": len(tr_out), "voice_memos": len(memo_out)},
        },
        "people": people,
        "accounts": acc_out,
        "transactions": tx_out,
        "transfers": tr_out,
        "voice_memos": memo_out,
    }


def write_snapshot() -> None:
    """Atomic write: readers never see a half-written file."""
    if _paused:
        return
    try:
        data = build_snapshot()
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix=".family_budget.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, JSON_PATH)
    except Exception as e:  # never break the bot because of the mirror file
        log.warning("JSON snapshot failed: %s", e)


def import_snapshot(data: dict) -> dict:
    """Replace ALL data with the content of a snapshot (people, accounts, records)."""
    global _paused
    if data.get("schema") != SCHEMA:
        raise ValueError(f"Not a {SCHEMA} file")
    _paused = True
    try:
        with db.conn() as c:
            c.executescript("DELETE FROM transactions; DELETE FROM transfers; DELETE FROM memos; "
                            "DELETE FROM accounts; DELETE FROM users;")
            for p in data.get("people", []):
                c.execute("INSERT INTO users (telegram_id, chat_id, phone, name, lang, created_at) VALUES (?,?,?,?,?,?)",
                          (p["telegram_id"], p["telegram_id"], p["phone"], p["name"], p.get("language", "en"),
                           p["joined_at"]))
            for i, a in enumerate(data.get("accounts", [])):
                c.execute("INSERT INTO accounts (id, owner, name, icon, initial, sort) VALUES (?,?,?,?,?,?)",
                          (a["id"], normalize_phone(a.get("owner_phone", "")), a["name"],
                           a.get("icon") or db.account_icon(a["name"]), a.get("opening_balance", 0), i))
            for t in data.get("transactions", []):
                c.execute("""INSERT INTO transactions (id, user_id, kind, amount, category, note, voice_file_id,
                             account_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                          (t["id"], t["user_id"], t["type"], t["amount"], t["category"], t.get("note"),
                           t.get("voice_file_id"), t.get("account_id"), t["created_at"]))
            for r in data.get("transfers", []):
                c.execute("""INSERT INTO transfers (id, user_id, from_id, to_id, amount, note, voice_file_id, created_at)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (r["id"], r["user_id"], r["from_account_id"], r["to_account_id"], r["amount"],
                           r.get("note"), r.get("voice_file_id"), r["created_at"]))
            for m in data.get("voice_memos", []):
                c.execute("INSERT INTO memos (id, user_id, file_id, duration, created_at) VALUES (?,?,?,?,?)",
                          (m["id"], m["user_id"], m["file_id"], m.get("duration_sec", 0), m["created_at"]))
    finally:
        _paused = False
    write_snapshot()
    return build_snapshot()["summary"]["counts"]
