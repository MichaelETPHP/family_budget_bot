import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .config import ACCOUNT_PLAN, DB_PATH, PEOPLE_NAMES, TZ, normalize_phone

DEFAULT_ACCOUNTS = ["Ahadu", "Awash", "CBE", "telebirr", "Dashen"]


def account_icon(name: str) -> str:
    n = name.lower()
    return "📱" if "telebirr" in n or "mpesa" in n else "💵" if "cash" in n else "🏦"


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    changed = False
    try:
        yield c
        c.commit()
        changed = c.total_changes > 0
    finally:
        c.close()
    if changed:  # keep the live JSON mirror (data/family_budget.json) in sync
        from . import jsonstore
        jsonstore.write_snapshot()


def init_db() -> None:
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                chat_id     INTEGER NOT NULL,
                phone       TEXT NOT NULL,
                name        TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(telegram_id),
                kind       TEXT NOT NULL CHECK (kind IN ('expense', 'income')),
                amount     REAL NOT NULL,
                category   TEXT NOT NULL,
                note       TEXT,
                created_at TEXT NOT NULL   -- local time, 'YYYY-MM-DD HH:MM:SS'
            );
            CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(created_at);
            CREATE TABLE IF NOT EXISTS memos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(telegram_id),
                file_id    TEXT NOT NULL,
                duration   INTEGER NOT NULL DEFAULT 0,
                local_path TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                owner   TEXT NOT NULL DEFAULT '',   -- normalized phone of the owner ('' = shared)
                name    TEXT NOT NULL,
                icon    TEXT NOT NULL,
                initial REAL NOT NULL DEFAULT 0,
                sort    INTEGER NOT NULL DEFAULT 0,
                UNIQUE (owner, name)
            );
            CREATE TABLE IF NOT EXISTS transfers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(telegram_id),
                from_id    INTEGER NOT NULL REFERENCES accounts(id),
                to_id      INTEGER NOT NULL REFERENCES accounts(id),
                amount     REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        ucols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
        if "lang" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'en'")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(transactions)")}
        if "voice_file_id" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN voice_file_id TEXT")
        if "account_id" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN account_id INTEGER REFERENCES accounts(id)")
        tcols = {r["name"] for r in c.execute("PRAGMA table_info(transfers)")}
        if "note" not in tcols:
            c.execute("ALTER TABLE transfers ADD COLUMN note TEXT")
        if "voice_file_id" not in tcols:
            c.execute("ALTER TABLE transfers ADD COLUMN voice_file_id TEXT")

        acols = {r["name"] for r in c.execute("PRAGMA table_info(accounts)")}
        if "owner" not in acols:
            # Old shared accounts -> they belong to the main earner (first person in ACCOUNT_PLAN).
            main = ACCOUNT_PLAN[0][0] if ACCOUNT_PLAN else ""
            c.executescript(
                """
                CREATE TABLE accounts_new (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner   TEXT NOT NULL DEFAULT '',
                    name    TEXT NOT NULL,
                    icon    TEXT NOT NULL,
                    initial REAL NOT NULL DEFAULT 0,
                    sort    INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (owner, name)
                );
                """
            )
            c.execute("INSERT INTO accounts_new (id, owner, name, icon, initial, sort) "
                      "SELECT id, ?, name, icon, initial, sort FROM accounts", (main,))
            c.executescript("DROP TABLE accounts; ALTER TABLE accounts_new RENAME TO accounts;")

        # Make sure every account in the plan exists (new ones start at 0).
        for owner, names in ACCOUNT_PLAN:
            for i, name in enumerate(names):
                c.execute("INSERT OR IGNORE INTO accounts (owner, name, icon, initial, sort) VALUES (?, ?, ?, 0, ?)",
                          (owner, name, account_icon(name), i))
        if not ACCOUNT_PLAN and c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
            c.executemany("INSERT INTO accounts (owner, name, icon, initial, sort) VALUES ('', ?, ?, 0, ?)",
                          [(n, account_icon(n), i) for i, n in enumerate(DEFAULT_ACCOUNTS)])


def now_local() -> datetime:
    return datetime.now(TZ)


# ---------- users ----------

def get_user(telegram_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()


def save_user(telegram_id: int, chat_id: int, phone: str, name: str, lang: str = "en") -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO users (telegram_id, chat_id, phone, name, lang, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                 chat_id = excluded.chat_id, phone = excluded.phone, name = excluded.name,
                 lang = excluded.lang""",
            (telegram_id, chat_id, phone, name, lang, now_local().strftime("%Y-%m-%d %H:%M:%S")),
        )


def set_lang(telegram_id: int, lang: str) -> None:
    with conn() as c:
        c.execute("UPDATE users SET lang = ? WHERE telegram_id = ?", (lang, telegram_id))


def all_users():
    with conn() as c:
        return c.execute("SELECT * FROM users ORDER BY created_at").fetchall()


# ---------- transactions ----------

def _stamp() -> str:
    return now_local().strftime("%Y-%m-%d %H:%M:%S")


def add_tx(user_id: int, kind: str, amount: float, category: str, note: str | None,
           voice_file_id: str | None = None, account_id: int | None = None) -> int:
    with conn() as c:
        cur = c.execute(
            """INSERT INTO transactions
                 (user_id, kind, amount, category, note, voice_file_id, account_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, kind, amount, category, note, voice_file_id, account_id, _stamp()),
        )
        return cur.lastrowid


# ---------- accounts & transfers ----------

_BALANCE_SQL = """
    SELECT a.*,
           a.initial
         + COALESCE((SELECT SUM(CASE t.kind WHEN 'income' THEN t.amount ELSE -t.amount END)
                     FROM transactions t WHERE t.account_id = a.id), 0)
         + COALESCE((SELECT SUM(amount) FROM transfers WHERE to_id = a.id), 0)
         - COALESCE((SELECT SUM(amount) FROM transfers WHERE from_id = a.id), 0) AS balance
    FROM accounts a
"""


def owner_names() -> dict[str, str]:
    """normalized phone -> name (the registered name wins over the one in .env NAMES)."""
    return {**PEOPLE_NAMES, **{normalize_phone(u["phone"]): u["name"] for u in all_users()}}


def _owner_rank(owner: str) -> int:
    order = [o for o, _ in ACCOUNT_PLAN]
    return order.index(owner) if owner in order else len(order)


def _enrich(rows) -> list[dict]:
    names = owner_names()
    out = []
    for r in rows:
        d = dict(r)
        d["owner_name"] = names.get(d["owner"], "0" + d["owner"] if d["owner"] else "")
        out.append(d)
    return out


def accounts(owner: str | None = None) -> list[dict]:
    """All accounts, or only those a person can use (theirs + shared)."""
    with conn() as c:
        if owner is None:
            rows = c.execute(_BALANCE_SQL).fetchall()
        else:
            rows = c.execute(_BALANCE_SQL + " WHERE a.owner IN (?, '')", (owner,)).fetchall()
    return sorted(_enrich(rows), key=lambda a: (_owner_rank(a["owner"]), a["sort"], a["id"]))


def get_account(account_id: int) -> dict | None:
    with conn() as c:
        row = c.execute(_BALANCE_SQL + " WHERE a.id = ?", (account_id,)).fetchone()
    return _enrich([row])[0] if row else None


def family_transfers(start: str, end: str) -> dict[str, dict[str, float]]:
    """Money moved between different people in [start, end): owner -> {'sent': x, 'received': y}."""
    with conn() as c:
        rows = c.execute(
            """SELECT fa.owner AS f, ta.owner AS t, SUM(tr.amount) AS s FROM transfers tr
               JOIN accounts fa ON fa.id = tr.from_id JOIN accounts ta ON ta.id = tr.to_id
               WHERE fa.owner != ta.owner AND tr.created_at >= ? AND tr.created_at < ?
               GROUP BY fa.owner, ta.owner""", (start, end)).fetchall()
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        out.setdefault(r["f"], {"sent": 0, "received": 0})["sent"] += r["s"]
        out.setdefault(r["t"], {"sent": 0, "received": 0})["received"] += r["s"]
    return out


_BIG = 1 << 62


def balance_as_of(account_id: int, stamp: str, tx_id: int | None = None, tr_id: int | None = None) -> float:
    """Balance of an account right after a given record (receipts stay accurate later).
    Records in the same second are ordered by their id within each table."""
    tx_cut, tr_cut = (tx_id if tx_id is not None else _BIG), (tr_id if tr_id is not None else _BIG)
    upto = "(created_at < ? OR (created_at = ? AND id <= ?))"
    with conn() as c:
        row = c.execute(
            f"""SELECT a.initial
                 + COALESCE((SELECT SUM(CASE kind WHEN 'income' THEN amount ELSE -amount END)
                             FROM transactions WHERE account_id = a.id AND {upto}), 0)
                 + COALESCE((SELECT SUM(amount) FROM transfers WHERE to_id = a.id AND {upto}), 0)
                 - COALESCE((SELECT SUM(amount) FROM transfers WHERE from_id = a.id AND {upto}), 0)
               FROM accounts a WHERE a.id = ?""",
            (stamp, stamp, tx_cut, stamp, stamp, tr_cut, stamp, stamp, tr_cut, account_id),
        ).fetchone()
        return row[0]


def user_day_total_until(user_id: int, kind: str, stamp: str, tx_id: int) -> float:
    """Total of that day up to and including the given record."""
    with conn() as c:
        return c.execute(
            """SELECT COALESCE(SUM(amount), 0) FROM transactions
               WHERE user_id = ? AND kind = ? AND substr(created_at, 1, 10) = ?
                 AND (created_at < ? OR (created_at = ? AND id <= ?))""",
            (user_id, kind, stamp[:10], stamp, stamp, tx_id),
        ).fetchone()[0]


def get_transfer(transfer_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM transfers WHERE id = ?", (transfer_id,)).fetchone()


def set_balance(account_id: int, target: float) -> None:
    """Adjust the opening amount so the current balance equals `target`."""
    acc = get_account(account_id)
    movements = acc["balance"] - acc["initial"]
    with conn() as c:
        c.execute("UPDATE accounts SET initial = ? WHERE id = ?", (target - movements, account_id))


def add_transfer(user_id: int, from_id: int, to_id: int, amount: float,
                 note: str | None = None, voice_file_id: str | None = None) -> int:
    with conn() as c:
        cur = c.execute(
            """INSERT INTO transfers (user_id, from_id, to_id, amount, note, voice_file_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, from_id, to_id, amount, note, voice_file_id, _stamp()),
        )
        return cur.lastrowid


_TRANSFER_SQL = """
    SELECT tr.*, u.name, fa.name AS from_name, fa.icon AS from_icon, fa.owner AS from_owner,
           ta.name AS to_name, ta.icon AS to_icon, ta.owner AS to_owner
    FROM transfers tr
    JOIN users u ON u.telegram_id = tr.user_id
    JOIN accounts fa ON fa.id = tr.from_id
    JOIN accounts ta ON ta.id = tr.to_id
"""


def recent_transfers(limit: int = 15):
    with conn() as c:
        return c.execute(_TRANSFER_SQL + " ORDER BY tr.id DESC LIMIT ?", (limit,)).fetchall()


def last_transfer(user_id: int):
    with conn() as c:
        return c.execute(_TRANSFER_SQL + " WHERE tr.user_id = ? ORDER BY tr.id DESC LIMIT 1",
                         (user_id,)).fetchone()


def delete_transfer(transfer_id: int, user_id: int) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM transfers WHERE id = ? AND user_id = ?",
                         (transfer_id, user_id)).rowcount > 0


def set_tx_note(tx_id: int, user_id: int, note: str | None = None, voice_file_id: str | None = None) -> bool:
    with conn() as c:
        if voice_file_id:
            cur = c.execute("UPDATE transactions SET voice_file_id = ? WHERE id = ? AND user_id = ?",
                            (voice_file_id, tx_id, user_id))
        else:
            cur = c.execute("UPDATE transactions SET note = ? WHERE id = ? AND user_id = ?",
                            (note, tx_id, user_id))
        return cur.rowcount > 0


def last_account_for(user_id: int, kind: str) -> int | None:
    with conn() as c:
        row = c.execute(
            """SELECT account_id FROM transactions WHERE user_id = ? AND kind = ? AND account_id IS NOT NULL
               ORDER BY id DESC LIMIT 1""", (user_id, kind)).fetchone()
        return row["account_id"] if row else None


def get_tx(tx_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()


# ---------- voice memos ----------

def add_memo(user_id: int, file_id: str, duration: int, local_path: str | None) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO memos (user_id, file_id, duration, local_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, file_id, duration, local_path, _stamp()),
        )
        return cur.lastrowid


def get_memo(memo_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM memos WHERE id = ?", (memo_id,)).fetchone()


def recent_memos(limit: int = 10):
    with conn() as c:
        return c.execute(
            """SELECT m.*, u.name FROM memos m JOIN users u ON u.telegram_id = m.user_id
               ORDER BY m.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def count_memos(start: str, end: str) -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM memos WHERE created_at >= ? AND created_at < ?",
                         (start, end)).fetchone()[0]


def last_tx(user_id: int):
    with conn() as c:
        return c.execute(
            """SELECT t.*, a.name AS account_name, a.icon AS account_icon FROM transactions t
               LEFT JOIN accounts a ON a.id = t.account_id
               WHERE t.user_id = ? ORDER BY t.id DESC LIMIT 1""", (user_id,)
        ).fetchone()


def delete_tx(tx_id: int, user_id: int) -> bool:
    with conn() as c:
        cur = c.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id))
        return cur.rowcount > 0


def user_day_total(user_id: int, kind: str, day: str) -> float:
    with conn() as c:
        row = c.execute(
            """SELECT COALESCE(SUM(amount), 0) AS s FROM transactions
               WHERE user_id = ? AND kind = ? AND substr(created_at, 1, 10) = ?""",
            (user_id, kind, day),
        ).fetchone()
        return row["s"]


def totals_by_user(start: str, end: str):
    """Per-user income/expense between [start, end) date strings 'YYYY-MM-DD'."""
    with conn() as c:
        return c.execute(
            """SELECT u.name, u.phone,
                      COALESCE(SUM(CASE WHEN t.kind='expense' THEN t.amount END), 0) AS expense,
                      COALESCE(SUM(CASE WHEN t.kind='income'  THEN t.amount END), 0) AS income,
                      COUNT(t.id) AS n
               FROM users u
               LEFT JOIN transactions t
                 ON t.user_id = u.telegram_id AND t.created_at >= ? AND t.created_at < ?
               GROUP BY u.telegram_id ORDER BY u.created_at""",
            (start, end),
        ).fetchall()


def totals_by_category(start: str, end: str, kind: str = "expense"):
    with conn() as c:
        return c.execute(
            """SELECT category, SUM(amount) AS total FROM transactions
               WHERE kind = ? AND created_at >= ? AND created_at < ?
               GROUP BY category ORDER BY total DESC""",
            (kind, start, end),
        ).fetchall()


def recent_tx(limit: int = 10):
    with conn() as c:
        return c.execute(
            """SELECT t.*, u.name, a.name AS account_name, a.icon AS account_icon
               FROM transactions t JOIN users u ON u.telegram_id = t.user_id
               LEFT JOIN accounts a ON a.id = t.account_id
               ORDER BY t.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
