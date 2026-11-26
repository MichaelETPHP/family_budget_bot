import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from telegram import Update

from . import db, jsonstore
from .bot import build_application, setup_profile, today_local
from .config import TZ, WEBHOOK_SECRET, WEBHOOK_URL

# Log timestamps in Addis Ababa time (the container clock is UTC)
logging.Formatter.converter = lambda *_: datetime.now(TZ).timetuple()
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("budget-bot")

tg_app = build_application()


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    jsonstore.write_snapshot()
    await tg_app.initialize()
    await tg_app.start()  # also starts the nightly 00:00 job

    if WEBHOOK_URL:
        await tg_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook", secret_token=WEBHOOK_SECRET or None,
                                     drop_pending_updates=True)
        log.info("🌐 Webhook mode: %s/webhook", WEBHOOK_URL)
    else:
        await tg_app.bot.delete_webhook()
        await tg_app.updater.start_polling(drop_pending_updates=True)
        log.info("🔄 Polling mode (no WEBHOOK_URL set)")

    try:
        await setup_profile(tg_app)
    except Exception as e:  # profile is cosmetic; never block startup
        log.warning("Could not set bot profile: %s", e)

    me = await tg_app.bot.get_me()
    log.info("🤖 Bot @%s is running", me.username)
    yield

    if tg_app.updater.running:
        await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()


app = FastAPI(title="Family Budget Bot", lifespan=lifespan)


@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="bad secret")
    await tg_app.process_update(Update.de_json(await request.json(), tg_app.bot))
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok", "users": len(db.all_users())}


@app.get("/api/export")
async def export_json():
    """The live JSON file with everything (only reachable from the server itself)."""
    jsonstore.write_snapshot()
    return FileResponse(jsonstore.JSON_PATH, media_type="application/json", filename="family_budget.json")


@app.get("/api/summary/today")
async def summary_today():
    d = today_local()
    rows = db.totals_by_user(d.isoformat(), (d + timedelta(days=1)).isoformat())
    return {"date": d.isoformat(), "people": [dict(r) for r in rows]}
