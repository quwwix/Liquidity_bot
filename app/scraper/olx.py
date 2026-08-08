import logging
import time
from dataclasses import dataclass, field

from app.scraper.categories import CATEGORIES

logger = logging.getLogger(__name__)

OLX_API = "https://www.olx.ua/api/v1/offers/"
MAX_PAGES = 5
PAGE_DELAY = 0.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Referer": "https://www.olx.ua/",
    "Origin": "https://www.olx.ua",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


@dataclass
class ScrapedListing:
    olx_id: str
    title: str
    price: float
    url: str
    is_business: bool = False
    description: str = ""
    seller_name: str = ""
    seller_type: str = ""
    location_city: str = ""
    location_region: str = ""
    location_full: str = ""
    phone: str = ""
    listing_date: str = ""
    category_breadcrumb: str = ""
    condition: str = ""
    delivery_available: bool = False
    safe_deal: bool = False
    negotiable: bool = False
    views_count: int = 0
    images_count: int = 0
    images: list = field(default_factory=list)
    params: dict = field(default_factory=dict)


def scrape_category(url_path: str, price_min: int, price_max: int, enrich_details: bool = False) -> list[ScrapedListing]:
    import httpx

    cat = next((c for c in CATEGORIES if c["url_path"] == url_path), None)
    query = cat["name"] if cat else url_path.strip("/").split("/")[-1].replace("-", " ")

    all_listings: list[ScrapedListing] = []
    seen_ids: set[str] = set()

    try:
        with httpx.Client(verify=False, timeout=15.0, follow_redirects=True) as client:
            for page in range(MAX_PAGES):
                offset = page * 40
                params = {
                    "offset": offset,
                    "limit": 40,
                    "query": query,
                    "filter_float_price:from": price_min,
                    "filter_float_price:to": price_max,
                }

                logger.info("Scraping API for %s (page %d)", query, page + 1)
                res = client.get(OLX_API, headers=HEADERS, params=params)

                if res.status_code != 200:
                    logger.warning("API returned HTTP %d for %s", res.status_code, query)
                    break

                ads = res.json().get("data", [])
                if not ads:
                    break

                for ad in ads:
                    ad_id = str(ad.get("id", ""))
                    if not ad_id or ad_id in seen_ids:
                        continue
                    seen_ids.add(ad_id)

                    price = None
                    params_dict = {}
                    for p in ad.get("params", []):
                        key = p.get("key", "") or p.get("name", "")
                        val_obj = p.get("value", {})
                        if key == "price":
                            if isinstance(val_obj, dict):
                                price = val_obj.get("value")
                        else:
                            val = val_obj.get("label", "") if isinstance(val_obj, dict) else str(val_obj)
                            if key and val:
                                params_dict[key] = val

                    if price is None:
                        continue

                    location = ad.get("location", {})
                    city = location.get("city", {}).get("name", "")
                    region = location.get("region", {}).get("name", "")
                    photos = ad.get("photos", [])

                    all_listings.append(ScrapedListing(
                        olx_id=ad_id,
                        title=ad.get("title", ""),
                        price=float(price),
                        url=ad.get("url", ""),
                        description=ad.get("description", "")[:500],
                        location_city=city,
                        location_region=region,
                        location_full=f"{city}, {region}" if region else city,
                        listing_date=ad.get("created_time", ""),
                        images_count=len(photos),
                        images=[p.get("link") for p in photos if p.get("link")][:5],
                        params=params_dict,
                    ))

                time.sleep(PAGE_DELAY)

    except Exception as e:
        logger.exception("Error scraping %s: %s", url_path, e)

    logger.info("Category %s: %d listings found", query, len(all_listings))
    return all_listings


def get_categories() -> list[dict]:
    return CATEGORIES
