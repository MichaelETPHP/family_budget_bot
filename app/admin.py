"""Admin tools. Inside Docker:  docker compose exec bot python -m app.admin <command>

  balances                               show every account and its balance
  set-balance <phone> <account> <amount> make an account show exactly <amount>
  start-fresh --yes                      delete all records (keeps people + accounts)
  export [file]                          write the full JSON snapshot (default: stdout)
  import <file> --yes                    replace ALL data with a JSON snapshot
"""
import json
import sys

from . import db, jsonstore
from .config import normalize_phone


def _find(phone: str, name: str):
    owner = normalize_phone(phone)
    for a in db.accounts():
        if a["owner"] == owner and a["name"].lower() == name.lower():
            return a
    sys.exit(f"❌ No account '{name}' for {phone}")


def balances() -> None:
    owner = None
    for a in db.accounts():
        if a["owner"] != owner:
            owner = a["owner"]
            print(f"\n👤 {a['owner_name']}")
        print(f"   {a['icon']} {a['name']:<10} {a['balance']:>12,.2f}")
    print(f"\n🏡 Family total {sum(a['balance'] for a in db.accounts()):>12,.2f}")


def main(argv: list[str]) -> None:
    db.init_db()
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]

    if cmd == "balances":
        balances()
    elif cmd == "set-balance" and len(args) == 3:
        acc = _find(args[0], args[1])
        db.set_balance(acc["id"], float(args[2].replace(",", "")))
        print(f"✅ {acc['owner_name']} · {acc['name']} = {db.get_account(acc['id'])['balance']:,.2f}")
    elif cmd == "start-fresh" and "--yes" in args:
        with db.conn() as c:
            c.executescript("DELETE FROM transactions; DELETE FROM transfers; DELETE FROM memos;")
        print("✅ All transactions, transfers and voice notes deleted (people and accounts kept)")
    elif cmd == "export":
        text = json.dumps(jsonstore.build_snapshot(), ensure_ascii=False, indent=2)
        if args:
            open(args[0], "w", encoding="utf-8").write(text)
            print(f"✅ Exported to {args[0]}")
        else:
            sys.stdout.write(text)
    elif cmd == "import" and args and "--yes" in args:
        path = [a for a in args if a != "--yes"][0]
        data = json.load(sys.stdin if path == "-" else open(path, encoding="utf-8"))
        print("✅ Imported:", jsonstore.import_snapshot(data))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
