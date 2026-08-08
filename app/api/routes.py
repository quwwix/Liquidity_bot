"""FastAPI routes for WebApp API."""

import hashlib
import hmac
import json
import logging
from datetime import date
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Header, Query, Depends
from pydantic import BaseModel

from app.config import get_settings
from app.database import (
    get_db, upsert_category, upsert_listing,
    mark_sold_listings, save_daily_metrics,
    start_scrape_run, finish_scrape_run,
)
from app.metrics.calculator import get_all_categories_metrics, get_category_detail, calculate_category_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def validate_telegram_init_data(init_data: str) -> dict | None:
    settings = get_settings()
    if not init_data:
        return None

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
        calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if calculated != received_hash:
            return None

        user_data = parsed.get("user")
        if user_data:
            return json.loads(user_data)
        return {}
    except Exception as e:
        logger.warning("Init data validation failed: %s", e)
        return None


async def verify_access(x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")):
    settings = get_settings()
    user = validate_telegram_init_data(x_telegram_init_data or "")

    if settings.my_chat_id:
        if not user or user.get("id") != settings.my_chat_id:
            raise HTTPException(status_code=403, detail="Доступ заборонено")
    return user


@router.get("/metrics/top")
async def get_top_liquid(
    period: int = Query(7, ge=1, le=90),
    price_min: int = Query(4000),
    price_max: int = Query(20000),
    search: str = Query(""),
    _user=Depends(verify_access),
):
    db = await get_db()
    try:
        metrics = await get_all_categories_metrics(db, period, price_min, price_max, search)
        metrics.sort(key=lambda x: x["liquidity"], reverse=True)
        return {"categories": metrics, "period": period, "price_min": price_min, "price_max": price_max}
    finally:
        await db.close()


@router.get("/metrics/active")
async def get_active_listings(
    period: int = Query(7, ge=1, le=90),
    price_min: int = Query(4000),
    price_max: int = Query(20000),
    search: str = Query(""),
    _user=Depends(verify_access),
):
    db = await get_db()
    try:
        metrics = await get_all_categories_metrics(db, period, price_min, price_max, search)
        metrics.sort(key=lambda x: x["active_count"], reverse=True)
        return {"categories": metrics, "period": period, "price_min": price_min, "price_max": price_max}
    finally:
        await db.close()


@router.get("/metrics/category/{category_id}")
async def get_category(
    category_id: int,
    period: int = Query(7, ge=1, le=90),
    price_min: int = Query(4000),
    price_max: int = Query(20000),
    _user=Depends(verify_access),
):
    db = await get_db()
    try:
        detail = await get_category_detail(db, category_id, period, price_min, price_max)
        if not detail:
            raise HTTPException(status_code=404, detail="Категорію не знайдено")
        return detail
    finally:
        await db.close()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/reset-db")
async def reset_database():
    import os
    from app.config import get_settings
    settings = get_settings()
    try:
        if os.path.exists(settings.database_path):
            os.remove(settings.database_path)
            return {"status": "success", "message": "Базу даних успішно видалено! Натисніть 'Оновити дані' в боті, щоб зібрати все заново з нуля."}
        else:
            return {"status": "success", "message": "База даних вже була порожньою."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/trigger-scrape")
async def trigger_scrape_endpoint():
    import asyncio
    from fastapi import Response
    from app.scheduler.jobs import run_daily_scrape
    asyncio.create_task(run_daily_scrape())
    return Response(
        content=json.dumps({"status": "started", "message": "Скрапінг успішно запущено у фоні"}, ensure_ascii=False),
        media_type="application/json; charset=utf-8",
    )


class IngestListing(BaseModel):
    olx_id: str
    title: str
    price: float
    url: str
    description: str = ""
    location_city: str = ""
    location_region: str = ""
    location_full: str = ""
    listing_date: str = ""
    images_count: int = 0
    images: list = []


class IngestCategory(BaseModel):
    slug: str
    name: str
    url_path: str
    listings: list[IngestListing]


class IngestPayload(BaseModel):
    categories: list[IngestCategory]


@router.post("/ingest")
async def ingest_data(
    payload: IngestPayload,
    x_ingest_token: str | None = Header(None, alias="X-Ingest-Token"),
):
    settings = get_settings()
    expected_token = getattr(settings, "ingest_token", "")
    if expected_token and x_ingest_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid token")

    db = await get_db()
    snapshot_date = date.today().isoformat()
    run_id = await start_scrape_run(db)
    total_found = 0
    total_sold = 0

    try:
        for cat_data in payload.categories:
            category_id = await upsert_category(db, cat_data.slug, cat_data.name, cat_data.url_path)
            active_ids: set[str] = set()

            for listing in cat_data.listings:
                if not (settings.price_min <= listing.price <= settings.price_max):
                    continue
                await upsert_listing(
                    db,
                    listing.olx_id,
                    category_id,
                    listing.title,
                    listing.price,
                    listing.url,
                    snapshot_date,
                    description=listing.description,
                    location_city=listing.location_city,
                    location_region=listing.location_region,
                    location_full=listing.location_full,
                    listing_date=listing.listing_date,
                    images_count=listing.images_count,
                    images_json=json.dumps(listing.images, ensure_ascii=False),
                )
                active_ids.add(listing.olx_id)
                total_found += 1

            sold = await mark_sold_listings(db, category_id, active_ids, snapshot_date)
            total_sold += sold

            for price_min, price_max, _ in settings.price_ranges:
                metrics = await calculate_category_metrics(db, category_id, 1, price_min, price_max)
                await save_daily_metrics(
                    db, category_id, snapshot_date,
                    price_min, price_max,
                    metrics["total_listed"], metrics["sold_count"],
                    metrics["liquidity"], metrics["speed_days"], metrics["volume"],
                )

            logger.info("Ingested %s: %d active, %d sold", cat_data.name, len(active_ids), sold)

        await finish_scrape_run(db, run_id, total_found, total_sold)
        return {"status": "ok", "listings_saved": total_found, "sold": total_sold}

    except Exception as e:
        logger.exception("Ingest failed")
        await finish_scrape_run(db, run_id, total_found, total_sold, str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()
