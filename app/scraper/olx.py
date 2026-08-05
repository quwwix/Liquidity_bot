import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from app.scraper.categories import OLX_BASE, CATEGORIES, build_search_url

logger = logging.getLogger(__name__)

MAX_PAGES = 25
PAGE_DELAY = 1.0


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


def _extract_olx_id(url: str) -> str | None:
    match = re.search(r"ID([A-Za-z0-9]+)\.html", url)
    if match:
        return match.group(1)
    match = re.search(r"ID([A-Za-z0-9]+)", url)
    return match.group(1) if match else None


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text.replace("\xa0", "").replace(" ", ""))
    if not cleaned:
        return None
    try:
        value = float(cleaned)
        return value if value > 0 else None
    except ValueError:
        return None


def _parse_price_from_json(price_data: Any) -> float | None:
    if isinstance(price_data, dict):
        val = price_data.get("value")
        if val is not None and isinstance(val, (int, float)) and val > 0:
            return float(val)
        
        reg = price_data.get("regularPrice", {})
        if isinstance(reg, dict):
            val = reg.get("value")
            if val is not None and isinstance(val, (int, float)) and val > 0:
                return float(val)

        display = price_data.get("displayValue", "")
        if display:
            return _parse_price(str(display))
            
    elif isinstance(price_data, (int, float)) and price_data > 0:
        return float(price_data)
    elif isinstance(price_data, str):
        return _parse_price(price_data)
    return None


def _fetch_html(url: str) -> str | None:
    import logging as _logging
    import warnings
    _logging.getLogger("scrapling").setLevel(_logging.ERROR)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            from scrapling import Fetcher
            fetcher = Fetcher()
            response = fetcher.get(url, headers={"Referer": "https://www.google.com/"})
            if response.status == 200:
                return response.text
            logger.warning("HTTP %d for %s", response.status, url)
            return None
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return None


def _extract_next_data(html: str) -> dict | None:
    match = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse __NEXT_DATA__ JSON: %s", e)
    return None


def _find_ads_recursive(obj: Any) -> list:
    if isinstance(obj, dict):
        if "ads" in obj and isinstance(obj["ads"], list) and len(obj["ads"]) > 0:
            first = obj["ads"][0]
            if isinstance(first, dict) and ("id" in first or "title" in first):
                return obj["ads"]
        for k, v in obj.items():
            if k in ("tracking", "seo"):
                continue
            res = _find_ads_recursive(v)
            if res:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = _find_ads_recursive(item)
            if res:
                return res
    return []


def _parse_listings_from_next_data(data: dict) -> list[ScrapedListing]:
    listings: list[ScrapedListing] = []
    seen_ids: set[str] = set()

    try:
        props = data.get("props", {}).get("pageProps", {})
        ads = _find_ads_recursive(props)

        logger.info("Found %d ads in __NEXT_DATA__", len(ads))

        for ad in ads:
            if not isinstance(ad, dict):
                continue

            ad_id = str(ad.get("id", ""))
            if not ad_id or ad_id in seen_ids:
                continue

            is_business = ad.get("isBusiness", False) or ad.get("business", False)
            if is_business:
                continue

            title = ad.get("title", "").strip()
            if not title:
                continue

            price = _parse_price_from_json(ad.get("price"))
            if price is None:
                continue

            url_str = ad.get("url", "")
            if not url_str:
                slug = ad.get("slug", "")
                if slug and ad_id:
                    url_str = f"{OLX_BASE}/d/uk/obyavlennya/{slug}-ID{ad_id}.html"
            if not url_str.startswith("http"):
                url_str = urljoin(OLX_BASE, url_str)

            olx_id = _extract_olx_id(url_str) or ad_id

            location = ad.get("location", {})
            city_name = ""
            region_name = ""
            location_full = ""
            if isinstance(location, dict):
                city_obj = location.get("city", {})
                region_obj = location.get("region", {})
                if isinstance(city_obj, dict):
                    city_name = city_obj.get("name", "")
                elif isinstance(city_obj, str):
                    city_name = city_obj
                if isinstance(region_obj, dict):
                    region_name = region_obj.get("name", "")
                elif isinstance(region_obj, str):
                    region_name = region_obj
                location_full = location.get("pathName", "")
                if not location_full and city_name:
                    location_full = f"{city_name}, {region_name}" if region_name else city_name

            photos = ad.get("photos", []) or ad.get("images", [])
            images_list = []
            if isinstance(photos, list):
                for photo in photos:
                    if isinstance(photo, dict):
                        img_url = photo.get("link", "") or photo.get("url", "")
                        if img_url:
                            images_list.append(img_url)
                    elif isinstance(photo, str):
                        images_list.append(photo)

            params_dict = {}
            ad_params = ad.get("params", [])
            if isinstance(ad_params, list):
                for p in ad_params:
                    if isinstance(p, dict):
                        key = p.get("key", "") or p.get("name", "")
                        val_obj = p.get("value", {})
                        if isinstance(val_obj, dict):
                            val_str = val_obj.get("label", "") or val_obj.get("key", "")
                        else:
                            val_str = str(val_obj) if val_obj else ""
                        if key and val_str:
                            params_dict[key] = val_str

            description = ad.get("description", "")
            created_time = ad.get("createdTime", "") or ad.get("created_time", "") or ad.get("lastRefreshTime", "")

            seen_ids.add(olx_id)
            listing = ScrapedListing(
                olx_id=olx_id,
                title=title,
                price=price,
                url=url_str,
                is_business=is_business,
                description=description[:500] if description else "",
                location_city=city_name,
                location_region=region_name,
                location_full=location_full,
                listing_date=created_time,
                images_count=len(images_list),
                images=images_list[:5],
                params=params_dict,
            )
            listings.append(listing)

    except Exception as e:
        logger.exception("Error parsing __NEXT_DATA__ ads: %s", e)

    return listings


def _parse_listings_from_html(html: str) -> list[ScrapedListing]:
    listings: list[ScrapedListing] = []
    seen_ids: set[str] = set()

    try:
        from scrapling import Adaptor
        page = Adaptor(html)
        cards = page.css('[data-cy="l-card"], [data-testid="l-card"], div[data-id]')
        for card in cards:
            link_el = card.css('a[href*="/d/"], a[href*="obyavlenie"], a[href*="ID"]')
            if not link_el:
                continue
            href = link_el[0].attrib.get("href", "")
            if not href:
                continue
            url = urljoin(OLX_BASE, href.split("#")[0])
            olx_id = _extract_olx_id(url)
            if not olx_id or olx_id in seen_ids:
                continue

            title_el = card.css('[data-cy="ad-card-title"], h6, h4, p[data-testid="ad-title"]')
            title = title_el[0].text.strip() if title_el else link_el[0].attrib.get("title", "").strip()
            if not title:
                continue

            price_el = card.css('[data-testid="ad-price"], p[data-testid="ad-price"], .css-10b0gli')
            price_text = price_el[0].text.strip() if price_el else ""
            price = _parse_price(price_text)
            if price is None:
                continue

            seen_ids.add(olx_id)
            listings.append(ScrapedListing(olx_id=olx_id, title=title, price=price, url=url))
    except Exception as e:
        logger.warning("Scrapling HTML card parse failed: %s", e)

    return listings


def scrape_category(url_path: str, price_min: int, price_max: int, enrich_details: bool = False) -> list[ScrapedListing]:
    all_listings: list[ScrapedListing] = []
    seen_ids: set[str] = set()

    for page_num in range(1, MAX_PAGES + 1):
        url = build_search_url(url_path, price_min, price_max)
        if page_num > 1:
            url += f"&page={page_num}"

        logger.info("Scraping %s (page %d)", url, page_num)

        html = _fetch_html(url)
        if html is None:
            logger.error("No HTML for %s, stopping", url)
            break

        page_listings: list[ScrapedListing] = []

        next_data = _extract_next_data(html)
        if next_data:
            page_listings = _parse_listings_from_next_data(next_data)
            logger.info("Parsed %d listings from __NEXT_DATA__", len(page_listings))

        if not page_listings:
            page_listings = _parse_listings_from_html(html)
            logger.info("Parsed %d listings from HTML fallback", len(page_listings))

        if not page_listings:
            logger.info("No listings on page %d, stopping", page_num)
            break

        new_count = 0
        for listing in page_listings:
            if listing.olx_id not in seen_ids:
                seen_ids.add(listing.olx_id)
                all_listings.append(listing)
                new_count += 1

        if new_count == 0:
            break

        if page_num < MAX_PAGES:
            time.sleep(PAGE_DELAY)

    logger.info("Found %d listings for %s", len(all_listings), url_path)
    return all_listings


def get_categories() -> list[dict]:
    return CATEGORIES
