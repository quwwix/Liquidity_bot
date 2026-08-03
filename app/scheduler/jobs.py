"""Scheduled jobs: daily scrape and digest."""

import logging
from datetime import date

from app.config import get_settings
from app.database import (
    get_db,
    upsert_category,
    upsert_listing,
    mark_sold_listings,
    save_daily_metrics,
    start_scrape_run,
    finish_scrape_run,
)
from app.scraper.categories import CATEGORIES
from app.scraper.olx import scrape_category
from app.metrics.calculator import calculate_category_metrics, get_digest_data

logger = logging.getLogger(__name__)


async def run_daily_scrape() -> None:
    settings = get_settings()
    if not settings.scrape_enabled:
        logger.info("Scraping disabled, skipping")
        return

    db = await get_db()
    run_id = await start_scrape_run(db)
    snapshot_date = date.today().isoformat()
    total_found = 0
    total_sold = 0

    try:
        for cat in CATEGORIES:
            category_id = await upsert_category(db, cat["slug"], cat["name"], cat["url_path"])

            listings = scrape_category(cat["url_path"], settings.price_min, settings.price_max)
            active_ids: set[str] = set()

            for listing in listings:
                    if settings.price_min <= listing.price <= settings.price_max:
                        import json
                        await upsert_listing(
                            db,
                            listing.olx_id,
                            category_id,
                            listing.title,
                            listing.price,
                            listing.url,
                            snapshot_date,
                            description=listing.description,
                            seller_name=listing.seller_name,
                            seller_type=listing.seller_type,
                            location_city=listing.location_city,
                            location_region=listing.location_region,
                            location_full=listing.location_full,
                            phone=listing.phone,
                            listing_date=listing.listing_date,
                            category_breadcrumb=listing.category_breadcrumb,
                            condition=listing.condition,
                            delivery_available=listing.delivery_available,
                            safe_deal=listing.safe_deal,
                            negotiable=listing.negotiable,
                            views_count=listing.views_count,
                            images_count=listing.images_count,
                            images_json=json.dumps(listing.images, ensure_ascii=False),
                            params_json=json.dumps(listing.params, ensure_ascii=False),
                        )
                        active_ids.add(listing.olx_id)
                        total_found += 1

            sold = await mark_sold_listings(db, category_id, active_ids, snapshot_date)
            total_sold += sold

            for price_min, price_max, _ in settings.price_ranges:
                metrics = await calculate_category_metrics(db, category_id, 1, price_min, price_max)
                await save_daily_metrics(
                    db,
                    category_id,
                    snapshot_date,
                    price_min,
                    price_max,
                    metrics["total_listed"],
                    metrics["sold_count"],
                    metrics["liquidity"],
                    metrics["speed_days"],
                    metrics["volume"],
                )

            logger.info("Category %s: %d active, %d sold", cat["name"], len(active_ids), sold)

        await finish_scrape_run(db, run_id, total_found, total_sold)
        logger.info("Daily scrape completed: %d found, %d sold", total_found, total_sold)

    except Exception as e:
        logger.exception("Daily scrape failed")
        await finish_scrape_run(db, run_id, total_found, total_sold, str(e))
    finally:
        await db.close()


async def send_daily_digest(bot) -> None:
    settings = get_settings()
    if not settings.my_chat_id:
        return

    db = await get_db()
    try:
        digest = await get_digest_data(db)
        lines = [f"📊 <b>Щоденний дайджест ліквідності OLX</b>", f"📅 {digest['date']}", ""]

        lines.append("<b>🏆 Топ-5 найліквідніших категорій:</b>")
        for i, cat in enumerate(digest["top_liquid"], 1):
            lines.append(
                f"{i}. {cat['name']} — {cat['liquidity']}% "
                f"(⚡ {cat['speed_days']} дн., 📦 {cat['volume']} продажів)"
            )

        if digest["biggest_changes"]:
            lines.append("")
            lines.append("<b>📈 Найбільші зміни vs вчора:</b>")
            for ch in digest["biggest_changes"]:
                sign = "+" if ch["liquidity_change"] >= 0 else ""
                lines.append(f"• {ch['name']}: {sign}{ch['liquidity_change']}% ліквідності")

        if digest["spikes"]:
            lines.append("")
            lines.append("<b>🚨 Різкий стрибок продажів (&gt;20%):</b>")
            for sp in digest["spikes"]:
                lines.append(f"• {sp['name']}: +{sp['liquidity_change']}%")

        text = "\n".join(lines)
        await bot.send_message(chat_id=settings.my_chat_id, text=text, parse_mode="HTML")
    finally:
        await db.close()
