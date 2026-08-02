"""Main FastAPI application with Telegram bot and scheduler."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from telegram.ext import Application

from app.config import get_settings
from app.api.routes import router as api_router
from app.bot.telegram_bot import create_bot_application, setup_bot_menu
from app.scheduler.jobs import run_daily_scrape, send_daily_digest
from app.database import get_db, upsert_category
from app.scraper.categories import CATEGORIES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")
bot_app: Application | None = None


async def init_categories():
    db = await get_db()
    try:
        for cat in CATEGORIES:
            await upsert_category(db, cat["slug"], cat["name"], cat["url_path"])
        logger.info("Initialized %d categories", len(CATEGORIES))
    finally:
        await db.close()


async def scheduled_scrape():
    logger.info("Starting scheduled scrape...")
    await run_daily_scrape()
    if bot_app:
        await send_daily_digest(bot_app.bot)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app
    settings = get_settings()

    await init_categories()

    scheduler.add_job(
        scheduled_scrape,
        CronTrigger(hour=8, minute=0, timezone="Europe/Kyiv"),
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: daily scrape at 8:00 Kyiv time")

    if settings.telegram_bot_token:
        bot_app = create_bot_application()
        await bot_app.initialize()
        await bot_app.start()
        await setup_bot_menu(bot_app)
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started")

    yield

    scheduler.shutdown(wait=False)
    if bot_app:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
        logger.info("Telegram bot stopped")


app = FastAPI(title="OLX Liquidity Tracker", lifespan=lifespan)
app.include_router(api_router)

webapp_dir = Path(__file__).parent.parent / "webapp"
app.mount("/static", StaticFiles(directory=webapp_dir), name="static")


@app.get("/")
async def webapp_index():
    return FileResponse(webapp_dir / "index.html")
