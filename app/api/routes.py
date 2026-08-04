"""FastAPI routes for WebApp API."""

import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Header, Query, Depends

from app.config import get_settings
from app.database import get_db
from app.metrics.calculator import get_all_categories_metrics, get_category_detail

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


@router.get("/trigger-scrape")
async def trigger_scrape_endpoint():
    import asyncio, json
    from fastapi import Response
    from app.scheduler.jobs import run_daily_scrape
    asyncio.create_task(run_daily_scrape())
    return Response(
        content=json.dumps({"status": "started", "message": "Скрапінг успішно запущено у фоні"}, ensure_ascii=False),
        media_type="application/json; charset=utf-8",
    )
