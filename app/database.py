import aiosqlite
from pathlib import Path
from datetime import date, datetime
from typing import Any

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    url_path TEXT NOT NULL,
    parent_slug TEXT
);

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    olx_id TEXT UNIQUE NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    title TEXT NOT NULL,
    price REAL NOT NULL,
    url TEXT NOT NULL,
    is_business INTEGER DEFAULT 0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    sold_date TEXT,
    status TEXT DEFAULT 'active',
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS listing_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL REFERENCES listings(id),
    snapshot_date TEXT NOT NULL,
    price REAL NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(listing_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS daily_category_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    metric_date TEXT NOT NULL,
    price_min REAL NOT NULL,
    price_max REAL NOT NULL,
    total_listed INTEGER DEFAULT 0,
    total_sold INTEGER DEFAULT 0,
    liquidity REAL DEFAULT 0,
    avg_speed_days REAL DEFAULT 0,
    volume INTEGER DEFAULT 0,
    UNIQUE(category_id, metric_date, price_min, price_max)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT DEFAULT 'running',
    listings_found INTEGER DEFAULT 0,
    listings_sold INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category_id);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_listings_olx_id ON listings(olx_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON listing_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON daily_category_metrics(metric_date);
"""


async def get_db() -> aiosqlite.Connection:
    settings = get_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    await db.commit()
    return db


async def upsert_category(db: aiosqlite.Connection, slug: str, name: str, url_path: str, parent_slug: str | None = None) -> int:
    await db.execute(
        """
        INSERT INTO categories (slug, name, url_path, parent_slug)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET name=excluded.name, url_path=excluded.url_path
        """,
        (slug, name, url_path, parent_slug),
    )
    await db.commit()
    cursor = await db.execute("SELECT id FROM categories WHERE slug = ?", (slug,))
    row = await cursor.fetchone()
    return row["id"]


async def get_all_categories(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    cursor = await db.execute("SELECT * FROM categories ORDER BY name")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def upsert_listing(
    db: aiosqlite.Connection,
    olx_id: str,
    category_id: int,
    title: str,
    price: float,
    url: str,
    snapshot_date: str,
) -> int:
    cursor = await db.execute("SELECT id, first_seen FROM listings WHERE olx_id = ?", (olx_id,))
    existing = await cursor.fetchone()

    if existing:
        listing_id = existing["id"]
        await db.execute(
            """
            UPDATE listings SET title=?, price=?, url=?, last_seen=?, status='active', sold_date=NULL
            WHERE id=?
            """,
            (title, price, url, snapshot_date, listing_id),
        )
    else:
        cursor = await db.execute(
            """
            INSERT INTO listings (olx_id, category_id, title, price, url, first_seen, last_seen, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (olx_id, category_id, title, price, url, snapshot_date, snapshot_date),
        )
        listing_id = cursor.lastrowid

    await db.execute(
        """
        INSERT INTO listing_snapshots (listing_id, snapshot_date, price, status)
        VALUES (?, ?, ?, 'active')
        ON CONFLICT(listing_id, snapshot_date) DO UPDATE SET price=excluded.price, status='active'
        """,
        (listing_id, snapshot_date, price),
    )
    await db.commit()
    return listing_id


async def mark_sold_listings(db: aiosqlite.Connection, category_id: int, active_olx_ids: set[str], snapshot_date: str) -> int:
    if not active_olx_ids:
        return 0

    placeholders = ",".join("?" * len(active_olx_ids))
    cursor = await db.execute(
        f"""
        SELECT olx_id, id FROM listings
        WHERE category_id = ? AND status = 'active' AND olx_id NOT IN ({placeholders})
        """,
        (category_id, *active_olx_ids),
    )
    sold_rows = await cursor.fetchall()
    count = 0

    for row in sold_rows:
        await db.execute(
            "UPDATE listings SET status='sold', sold_date=? WHERE id=?",
            (snapshot_date, row["id"]),
        )
        await db.execute(
            """
            INSERT INTO listing_snapshots (listing_id, snapshot_date, price, status)
            SELECT id, ?, price, 'sold' FROM listings WHERE id=?
            ON CONFLICT(listing_id, snapshot_date) DO UPDATE SET status='sold'
            """,
            (snapshot_date, row["id"]),
        )
        count += 1

    await db.commit()
    return count


async def save_daily_metrics(
    db: aiosqlite.Connection,
    category_id: int,
    metric_date: str,
    price_min: float,
    price_max: float,
    total_listed: int,
    total_sold: int,
    liquidity: float,
    avg_speed_days: float,
    volume: int,
) -> None:
    await db.execute(
        """
        INSERT INTO daily_category_metrics
        (category_id, metric_date, price_min, price_max, total_listed, total_sold, liquidity, avg_speed_days, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(category_id, metric_date, price_min, price_max) DO UPDATE SET
            total_listed=excluded.total_listed,
            total_sold=excluded.total_sold,
            liquidity=excluded.liquidity,
            avg_speed_days=excluded.avg_speed_days,
            volume=excluded.volume
        """,
        (category_id, metric_date, price_min, price_max, total_listed, total_sold, liquidity, avg_speed_days, volume),
    )
    await db.commit()


async def start_scrape_run(db: aiosqlite.Connection) -> int:
    cursor = await db.execute(
        "INSERT INTO scrape_runs (started_at, status) VALUES (?, 'running')",
        (datetime.utcnow().isoformat(),),
    )
    await db.commit()
    return cursor.lastrowid


async def finish_scrape_run(db: aiosqlite.Connection, run_id: int, listings_found: int, listings_sold: int, error: str | None = None) -> None:
    status = "error" if error else "completed"
    await db.execute(
        """
        UPDATE scrape_runs SET finished_at=?, status=?, listings_found=?, listings_sold=?, error_message=?
        WHERE id=?
        """,
        (datetime.utcnow().isoformat(), status, listings_found, listings_sold, error, run_id),
    )
    await db.commit()
