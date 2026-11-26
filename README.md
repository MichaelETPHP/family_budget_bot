# 🏡 Family Budget Bot

A family budget bot for Telegram, built with Python, FastAPI and python-telegram-bot. It works in English and Amharic, and dates use the Ethiopian calendar.

## ✨ Features
- 💸 **Expenses** and 💰 **income**: pick a category, type the amount, and tap the green **Save**. You can add a note or 🎙️ voice note afterwards.
- 🏦 **Accounts**: Ahadu, Awash, CBE, telebirr and Dashen. An account without enough money turns red and can't be picked.
- 🔄 **Transfers** between accounts.
- 📊 **Reports**: today, this Ethiopian month, and history. 🌙 A summary goes to everyone at **midnight**.
- 🔔 **Notifications**: your partner gets a message in their own language whenever you record something.
- 🧹 **Clean chat**: commands, typed amounts, photos and files are deleted, and the menu always stays open.
- 🔒 **Family only**: only the numbers listed in `ALLOWED_PHONES` can use the bot.

---

## ☁️ Deploy with Coolify (or Dokploy / Portainer)
1. **Source:** this repository, branch `main`. **Build pack:** Docker Compose. **Compose file:** `/docker-compose.yml`.
2. **Environment variables:** set `BOT_TOKEN`, `ALLOWED_PHONES`, `ACCOUNTS`, `NAMES` and `TIMEZONE` (see `.env.example`). Mark `BOT_TOKEN` as secret.
3. **No domain or port is needed.** The bot polls Telegram, so leave the domain empty.
4. **Stop every other copy of the bot first** (your PC, another server). Telegram allows only one per token.
5. Deploy. Wait for the status to show healthy, and check that the logs say `🤖 Bot @… is running`.
6. **Bring your data:** see "Move data into a hosted container" below.

### Move data into a hosted container
On the server (SSH), with `expenses.db` from `./deploy/backup.sh` uploaded to `/root/`:
```bash
C=$(docker ps --filter "label=com.docker.compose.service=bot" --format '{{.Names}}' | head -1)
docker exec -i "$C" sh -c 'cat > /app/data/expenses.db.new' < /root/expenses.db
docker exec "$C" sh -c 'mv /app/data/expenses.db.new /app/data/expenses.db && rm -f /app/data/bot_state.pickle'
docker restart "$C"
```

## 🚀 Deploy to a VPS (plain Docker)
On a plain VPS, add the local override to get the `127.0.0.1:8000` API port and the optional Caddy webhook:
`docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build`

Works on any Ubuntu or Debian VPS. 1 vCPU and 512 MB RAM is enough.

### 1. Install Docker (one time)
```bash
curl -fsSL https://get.docker.com | sh
```

### 2. Get the code
```bash
git clone https://github.com/MichaelETPHP/family_budget_bot.git /opt/family-budget-bot
cd /opt/family-budget-bot
```
The repository has **no secrets and no personal data**. Your `.env` and data never go to Git, so you add them by hand (steps 3 and 6).

### 3. Configure
```bash
cp .env.example .env
nano .env                 # BOT_TOKEN, ALLOWED_PHONES, ACCOUNTS, NAMES
chmod 600 .env
chmod +x deploy/*.sh
```
Or copy your own `.env` from the PC: `scp .env root@YOUR_VPS_IP:/opt/family-budget-bot/`

To update later: `git pull && docker compose up -d --build`

### 4. ⚠️ Stop the bot on your PC
Telegram allows only **one** running copy per token. Close the local `uvicorn` before the next step.

### 5. Start
```bash
docker compose up -d --build
docker compose ps            # STATUS should be "healthy" after ~20 s
docker compose logs -f bot   # look for "🤖 Bot @<your_bot> is running"
```

### 6. Bring your data
The live data is in Docker on your PC, **not** in the project's `expenses.db`, which is old test data. On the PC:
```powershell
bash ./deploy/backup.sh          # creates backups/<date>/expenses.db
docker compose down              # stop the PC copy (only one may run)
scp backups\<date>\expenses.db root@YOUR_VPS_IP:/opt/family-budget-bot/
```
Then on the VPS:
```bash
./deploy/restore.sh expenses.db
```

### 7. Nightly backups
```bash
crontab -e
# add this line: backup every night at 03:00, keeps the last 14
0 3 * * * cd /opt/family-budget-bot && ./deploy/backup.sh >> backups/backup.log 2>&1
```
To restore a backup: `./deploy/restore.sh backups/<date>/expenses.db`

---

## 🔧 Everyday commands
| Task | Command |
|---|---|
| Status | `docker compose ps` |
| Live logs | `docker compose logs -f bot` |
| Restart | `docker compose restart bot` |
| Update after code changes | `docker compose up -d --build` |
| Stop | `docker compose down` (your data stays in the `bot_data` volume) |
| Health | `curl -s localhost:8000/health` |

## 📄 Live JSON file
Everything (people, accounts, balances, transactions, transfers, voice notes and a summary) is mirrored to **`/app/data/family_budget.json`**.
It is rewritten atomically after every change.

| Task | Command |
|---|---|
| Open or download it | `curl -s localhost:8000/api/export -o family_budget.json`, or open http://localhost:8000/api/export in a browser on the server or PC |
| Copy it out of Docker | `docker compose cp bot:/app/data/family_budget.json .` |
| Edit it, then load it back | `docker compose exec -T bot python -m app.admin import - --yes < family_budget.json` |

The file starts with `"schema": "family-budget/v1"`. `opening_balance` is the starting amount, and `balance` is calculated from it.

## 🛠️ Admin tools
```bash
docker compose exec bot python -m app.admin balances
docker compose exec bot python -m app.admin set-balance 0911111111 CBE 1500
docker compose exec bot python -m app.admin start-fresh --yes     # delete all records, keep people + accounts
docker compose exec bot python -m app.admin export > family_budget.json
```

## 🌐 Webhook mode (optional)
The default is **polling**. It needs no domain and no open ports, and is the right choice for a family bot.
If you have a domain and prefer webhooks:
1. Point the domain's DNS **A record** at the VPS IP.
2. In `.env`, set `DOMAIN=bot.example.com`, `WEBHOOK_URL=https://bot.example.com` and a long random `WEBHOOK_SECRET`.
3. Open ports 80 and 443, then run `docker compose -f docker-compose.yml -f docker-compose.local.yml --profile webhook up -d --build`.

Caddy gets the HTTPS certificate automatically. Only `/webhook` is public, and the bot checks Telegram's secret token on every request.

## 🛡️ Security
- The container runs as a **non-root** user with a **read-only** filesystem, `no-new-privileges` and a 256 MB memory limit.
- Port 8000 only listens on `127.0.0.1`, so it can't be reached from the internet.
- `.env` is never copied into the image. Keep it `chmod 600`.
- If the bot token has ever been shared, rotate it in @BotFather with `/revoke`, update `.env`, then run `docker compose up -d`.

## 💻 Run locally (development)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
