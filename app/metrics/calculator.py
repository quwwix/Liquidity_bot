"""Metrics calculation for category liquidity."""

from datetime import date, datetime, timedelta
from typing import Any

import aiosqlite


async def calculate_category_metrics(
    db: aiosqlite.Connection,
    category_id: int,
    period_days: int,
    price_min: float,
    price_max: float,
) -> dict[str, Any]:
    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)

    cursor = await db.execute(
        """
        SELECT COUNT(*) as cnt FROM listings
        WHERE category_id = ? AND status = 'active'
        AND price >= ? AND price <= ?
        """,
        (category_id, price_min, price_max),
    )
    active_now = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        """
        SELECT COUNT(*) as cnt FROM listings
        WHERE category_id = ? AND status = 'sold'
        AND price >= ? AND price <= ?
        AND sold_date >= ? AND sold_date <= ?
        """,
        (category_id, price_min, price_max, start_date.isoformat(), end_date.isoformat()),
    )
    sold_in_period = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        """
        SELECT COUNT(DISTINCT l.id) as cnt FROM listings l
        JOIN listing_snapshots s ON l.id = s.listing_id
        WHERE l.category_id = ? AND l.price >= ? AND l.price <= ?
        AND s.snapshot_date >= ? AND s.snapshot_date <= ?
        """,
        (category_id, price_min, price_max, start_date.isoformat(), end_date.isoformat()),
    )
    total_listed = (await cursor.fetchone())["cnt"]

    if total_listed == 0:
        total_listed = active_now + sold_in_period

    liquidity = (sold_in_period / total_listed * 100) if total_listed > 0 else 0.0

    cursor = await db.execute(
        """
        SELECT AVG(
            julianday(sold_date) - julianday(first_seen)
        ) as avg_days
        FROM listings
        WHERE category_id = ? AND status = 'sold'
        AND price >= ? AND price <= ?
        AND sold_date >= ? AND sold_date <= ?
        AND sold_date IS NOT NULL
        """,
        (category_id, price_min, price_max, start_date.isoformat(), end_date.isoformat()),
    )
    row = await cursor.fetchone()
    avg_speed = round(row["avg_days"] or 0, 1)

    return {
        "active_count": active_now,
        "total_listed": total_listed,
        "sold_count": sold_in_period,
        "liquidity": round(liquidity, 1),
        "speed_days": avg_speed,
        "volume": sold_in_period,
    }


async def get_all_categories_metrics(
    db: aiosqlite.Connection,
    period_days: int,
    price_min: float,
    price_max: float,
    search: str = "",
) -> list[dict[str, Any]]:
    cursor = await db.execute("SELECT * FROM categories ORDER BY name")
    categories = await cursor.fetchall()
    results = []

    for cat in categories:
        if search and search.lower() not in cat["name"].lower():
            continue

        metrics = await calculate_category_metrics(db, cat["id"], period_days, price_min, price_max)
        results.append(
            {
                "id": cat["id"],
                "slug": cat["slug"],
                "name": cat["name"],
                **metrics,
            }
        )

    return results


async def get_category_detail(
    db: aiosqlite.Connection,
    category_id: int,
    period_days: int,
    price_min: float,
    price_max: float,
) -> dict[str, Any]:
    cursor = await db.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    cat = await cursor.fetchone()
    if not cat:
        return {}

    metrics = await calculate_category_metrics(db, category_id, period_days, price_min, price_max)

    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)

    cursor = await db.execute(
        """
        SELECT metric_date, liquidity, volume, total_listed
        FROM daily_category_metrics
        WHERE category_id = ? AND price_min = ? AND price_max = ?
        AND metric_date >= ?
        ORDER BY metric_date
        """,
        (category_id, price_min, price_max, start_date.isoformat()),
    )
    history = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        """
        SELECT title, price, url, sold_date, first_seen
        FROM listings
        WHERE category_id = ? AND status = 'sold'
        AND price >= ? AND price <= ?
        AND sold_date >= ?
        ORDER BY sold_date DESC
        LIMIT 10
        """,
        (category_id, price_min, price_max, start_date.isoformat()),
    )
    sold_examples = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        """
        SELECT
            CASE
                WHEN price < 8000 THEN '4000-8000'
                WHEN price < 12000 THEN '8000-12000'
                WHEN price < 16000 THEN '12000-16000'
                ELSE '16000-20000'
            END as price_range,
            COUNT(*) as count
        FROM listings
        WHERE category_id = ? AND status IN ('active', 'sold')
        AND price >= ? AND price <= ?
        GROUP BY price_range
        """,
        (category_id, price_min, price_max),
    )
    price_distribution = [dict(r) for r in await cursor.fetchall()]

    return {
        "category": dict(cat),
        **metrics,
        "liquidity_history": history,
        "sold_examples": sold_examples,
        "price_distribution": price_distribution,
    }


async def get_digest_data(db: aiosqlite.Connection) -> dict[str, Any]:
    """Data for daily Telegram digest."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    metrics_today = await get_all_categories_metrics(db, 1, 4000, 20000)
    metrics_yesterday = []

    for cat in metrics_today:
        cursor = await db.execute(
            """
            SELECT liquidity, volume, total_listed FROM daily_category_metrics
            WHERE category_id = ? AND metric_date = ? AND price_min = 4000 AND price_max = 20000
            """,
            (cat["id"], yesterday.isoformat()),
        )
        row = await cursor.fetchone()
        if row:
            metrics_yesterday.append({"id": cat["id"], **dict(row)})

    top_liquid = sorted(metrics_today, key=lambda x: x["liquidity"], reverse=True)[:5]

    changes = []
    yesterday_map = {m["id"]: m for m in metrics_yesterday}
    for cat in metrics_today:
        prev = yesterday_map.get(cat["id"])
        if prev:
            liq_change = cat["liquidity"] - prev["liquidity"]
            vol_change = cat["volume"] - prev["volume"]
            if abs(liq_change) >= 1 or vol_change != 0:
                changes.append(
                    {
                        "name": cat["name"],
                        "liquidity_change": round(liq_change, 1),
                        "volume_change": vol_change,
                    }
                )

    spikes = [
        c for c in changes if c["liquidity_change"] >= 20 or (c["volume_change"] > 0 and c["liquidity_change"] >= 20)
    ]

    changes.sort(key=lambda x: abs(x["liquidity_change"]), reverse=True)

    return {
        "top_liquid": top_liquid,
        "biggest_changes": changes[:5],
        "spikes": spikes,
        "date": today.isoformat(),
    }
