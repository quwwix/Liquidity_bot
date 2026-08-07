import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from telegram import Update
from telegram.ext import Application

from app.config import get_settings
from app.api.routes import router as api_router
from app.bot.telegram_bot import create_bot_application, setup_bot_menu
from app.scheduler.jobs import run_daily_scrape
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


async def check_and_run_initial_scrape():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM listings")
        row = await cursor.fetchone()
        listing_count = row["cnt"] if row else 0
        
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT category_id) as cats FROM listings"
        )
        row = await cursor.fetchone()
        cat_count = row["cats"] if row else 0
        
        if listing_count == 0 or cat_count < 5:
            logger.info("Database has only %d listings in %d categories — triggering initial scrape...", listing_count, cat_count)
            await run_daily_scrape()
        else:
            logger.info("Database has %d listings in %d categories — skipping initial scrape", listing_count, cat_count)
    except Exception as e:
        logger.warning("Error checking initial scrape: %s", e)
    finally:
        await db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app
    settings = get_settings()

    await init_categories()
    asyncio.create_task(check_and_run_initial_scrape())

    scheduler.add_job(
        scheduled_scrape,
        CronTrigger(hour=8, minute=0, timezone="Europe/Kyiv"),
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()

    if settings.telegram_bot_token:
        bot_app = create_bot_application()
        await bot_app.initialize()
        await bot_app.start()
        await setup_bot_menu(bot_app)

        webhook_url = settings.webapp_url.rstrip("/") + "/webhook"
        if webhook_url.startswith("https://"):
            await bot_app.bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
            )
            logger.info("Webhook set to %s", webhook_url)
        else:
            await bot_app.updater.start_polling(drop_pending_updates=True)
            logger.info("Polling mode started")

    yield

    scheduler.shutdown(wait=False)
    if bot_app:
        if bot_app.updater and bot_app.updater.running:
            await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


app = FastAPI(title="OLX Liquidity Tracker", lifespan=lifespan)
app.include_router(api_router)

webapp_dir = Path(__file__).parent.parent / "webapp"
app.mount("/static", StaticFiles(directory=webapp_dir), name="static")


@app.post("/webhook")
async def telegram_webhook(request: Request):
    if bot_app is None:
        return Response(status_code=503)
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return Response(status_code=200)


@app.get("/")
async def webapp_index():
    return FileResponse(webapp_dir / "index.html")
