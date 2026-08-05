import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx

from app.scraper.categories import OLX_BASE, CATEGORIES, build_search_url

logger = logging.getLogger(__name__)

MAX_PAGES = 25
PAGE_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
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
    value = float(cleaned)
    if value < 100:
        return None
    return value


def _parse_price_from_json(price_data: Any) -> float | None:
    if isinstance(price_data, dict):
        value = price_data.get("regularPrice", {}).get("value")
        if value is None:
            value = price_data.get("displayValue")
        if value is not None:
            if isinstance(value, (int, float)):
                return float(value) if value >= 100 else None
            if isinstance(value, str):
                return _parse_price(value)

        display = price_data.get("displayValue", "")
        if display:
            return _parse_price(display)
    if isinstance(price_data, (int, float)):
        return float(price_data) if price_data >= 100 else None
    if isinstance(price_data, str):
        return _parse_price(price_data)
    return None


def _fetch_html(url: str) -> str | None:
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


def _parse_listings_from_next_data(data: dict) -> list[ScrapedListing]:
    listings: list[ScrapedListing] = []
    seen_ids: set[str] = set()

    try:
        props = data.get("props", {}).get("pageProps", {})

        ads = props.get("ads", [])
        if not ads:
            listing_data = props.get("data", {})
            ads = listing_data.get("ads", [])
        if not ads:
            ads = props.get("listingData", {}).get("listing", [])
        if not ads:
            search_data = props.get("searchData", {})
            ads = search_data.get("ads", [])
        if not ads:
            initial_data = props.get("initialData", {})
            ads = initial_data.get("ads", [])
            if not ads:
                ads = initial_data.get("listing", [])
        if not ads:
            for key, val in props.items():
                if isinstance(val, dict):
                    candidate = val.get("ads", [])
                    if isinstance(candidate, list) and len(candidate) > 5:
                        ads = candidate
                        break

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

            promotion = ad.get("promotion", {})
            if isinstance(promotion, dict) and promotion.get("highlighted"):
                pass

            title = ad.get("title", "").strip()
            if not title:
                continue

            price = None
            price_data = ad.get("price", {})
            price = _parse_price_from_json(price_data)
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

    pattern = re.compile(r'href="([^"]*?/d/[^"]*?ID[A-Za-z0-9]+\.html[^"]*?)"')
    matches = pattern.findall(html)

    for href in matches:
        url = urljoin(OLX_BASE, href.split("#")[0])
        olx_id = _extract_olx_id(url)
        if not olx_id or olx_id in seen_ids:
            continue

        title_match = re.search(
            rf'href="{re.escape(href)}"[^>]*?title="([^"]+)"',
            html,
        )
        title = title_match.group(1).strip() if title_match else ""
        if not title:
            continue

        seen_ids.add(olx_id)
        listings.append(ScrapedListing(olx_id=olx_id, title=title, price=0, url=url))

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
