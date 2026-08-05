import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

from app.scraper.categories import OLX_BASE, CATEGORIES, build_search_url

logger = logging.getLogger(__name__)

MAX_PAGES = 25
PAGE_DELAY = 2.0


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
    raw_html: str = ""


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


def _safe_text(elements, default="") -> str:
    try:
        return elements[0].text.strip() if elements else default
    except Exception:
        return default


def _fetch_page(url: str):
    try:
        from scrapling.fetchers import StealthyFetcher
        return StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            wait_selector='[data-cy="l-card"], [data-testid="l-card"], a[href*="ID"]',
            timeout=60000,
        )
    except Exception as e:
        logger.warning("StealthyFetcher failed for %s: %s, trying DynamicFetcher", url, e)
        try:
            from scrapling.fetchers import DynamicFetcher
            return DynamicFetcher.fetch(
                url,
                headless=True,
                network_idle=True,
                wait_selector='a[href*="ID"]',
                timeout=60000,
            )
        except Exception as e2:
            logger.warning("DynamicFetcher failed for %s: %s, trying HTTP Fetcher", url, e2)
            from scrapling.fetchers import Fetcher
            return Fetcher.get(url)


def _fetch_detail_page(url: str):
    try:
        from scrapling.fetchers import StealthyFetcher
        return StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=45000,
        )
    except Exception as e:
        logger.warning("Detail fetch failed for %s: %s, trying HTTP Fetcher", url, e)
        try:
            from scrapling.fetchers import Fetcher
            return Fetcher.get(url)
        except Exception as e2:
            logger.error("HTTP Fetcher detail failed for %s: %s", url, e2)
            return None


def _enrich_listing_from_detail(listing: ScrapedListing) -> None:
    page = _fetch_detail_page(listing.url)
    if page is None:
        return

    try:
        desc_el = page.css('[data-cy="ad_description"] div, [data-testid="ad-description"] div, .css-bgzo2k')
        listing.description = _safe_text(desc_el)

        seller_el = page.css('[data-testid="user-profile-link"] h4, .css-1lcorn2 h4, [data-cy="seller-card"] h4')
        listing.seller_name = _safe_text(seller_el)

        seller_type_el = page.css('[data-testid="seller-type"], .css-1oa3r68')
        listing.seller_type = _safe_text(seller_type_el)

        loc_el = page.css('[data-testid="location-breadcrumb"], [data-cy="location-breadcrumb"], .css-7wz4ol')
        listing.location_full = _safe_text(loc_el)
        if listing.location_full:
            parts = [p.strip() for p in listing.location_full.split(",")]
            if len(parts) >= 2:
                listing.location_city = parts[0]
                listing.location_region = parts[-1]
            elif len(parts) == 1:
                listing.location_city = parts[0]

        date_el = page.css('[data-cy="ad-posted-at"], span[data-testid="ad-posted-at"], .css-19yf5eus')
        listing.listing_date = _safe_text(date_el)

        breadcrumb_el = page.css('[data-testid="breadcrumb"], nav[aria-label="Breadcrumb"] a, .css-1itdiow a')
        listing.category_breadcrumb = " > ".join(
            el.text.strip() for el in breadcrumb_el if el.text.strip()
        )

        condition_el = page.css('[data-testid="ad-param-state"] .css-1c4ggqp, li[data-testid="dom-value"]:first-child')
        listing.condition = _safe_text(condition_el)

        delivery_el = page.css('[data-testid="couriers-delivery-badge"], [data-cy="delivery-badge"]')
        listing.delivery_available = bool(delivery_el)

        safe_el = page.css('[data-testid="safe-deal-badge"], [data-cy="safe-deal-badge"]')
        listing.safe_deal = bool(safe_el)

        neg_el = page.css('[data-testid="negotiable-badge"], [data-cy="negotiable-badge"]')
        listing.negotiable = bool(neg_el)

        views_el = page.css('[data-testid="ad-statistics-views"], .css-19c04p3')
        views_text = _safe_text(views_el)
        if views_text:
            nums = re.findall(r"\d+", views_text.replace(" ", ""))
            if nums:
                listing.views_count = int(nums[0])

        imgs = page.css('img[data-testid="ad-photo"], div[data-testid="ad-photo-gallery"] img, .css-1ytkscc img')
        listing.images_count = len(imgs)
        listing.images = [img.attrib.get("src", "") for img in imgs if img.attrib.get("src")]

        params: dict = {}
        param_items = page.css('li[data-testid="dom-value"], ul.css-sfcl1s li, div.css-171flfm li')
        for item in param_items:
            label_el = item.css('p.css-b5m1rv, p[data-testid="param-label"], span')
            value_el = item.css('p.css-1c4ggqp, a.css-11rb0qj, p[data-testid="param-value"]')
            label = _safe_text(label_el)
            value = _safe_text(value_el)
            if label and value:
                params[label] = value
        listing.params = params

        phone_el = page.css('[data-testid="call-link"], a[href^="tel:"]')
        if phone_el:
            href = phone_el[0].attrib.get("href", "")
            listing.phone = href.replace("tel:", "").strip()

    except Exception as e:
        logger.warning("Error enriching listing %s: %s", listing.olx_id, e)


def _parse_listings_from_page(page) -> list[ScrapedListing]:
    listings: list[ScrapedListing] = []
    seen_ids: set[str] = set()

    cards = page.css('[data-cy="l-card"], [data-testid="l-card"], div[data-id]')
    if not cards:
        cards = page.css('div[data-testid="listing-grid"] > div, li.css-1sw7q4x')

    for card in cards:
        link_el = card.css('a[href*="/d/"], a[href*="obyavlenie"], a[href*="ID"]')
        if not link_el:
            link_el = card.css("a[href]")
        if not link_el:
            continue

        href = link_el[0].attrib.get("href", "")
        if not href or "/d/" not in href and "ID" not in href:
            continue

        url = urljoin(OLX_BASE, href.split("#")[0])
        olx_id = _extract_olx_id(url)
        if not olx_id or olx_id in seen_ids:
            continue

        business_badge = card.css('[data-testid="business-badge"], .css-1wws9er, [data-cy="ad-business-badge"]')
        if business_badge:
            continue

        title_el = card.css('[data-cy="ad-card-title"], h6, h4, p[data-testid="ad-title"]')
        title = title_el[0].text.strip() if title_el else ""
        if not title:
            title = link_el[0].attrib.get("title", "").strip()
        if not title:
            continue

        price_el = card.css('[data-testid="ad-price"], p[data-testid="ad-price"], .css-10b0gli')
        price_text = price_el[0].text.strip() if price_el else ""
        price = _parse_price(price_text)
        if price is None:
            continue

        location_el = card.css('[data-testid="location-date"], p.css-1mwdrlh')
        location_raw = _safe_text(location_el)
        city = ""
        if location_raw:
            city = location_raw.split("-")[0].strip().split(",")[0].strip()

        seen_ids.add(olx_id)
        listing = ScrapedListing(
            olx_id=olx_id,
            title=title,
            price=price,
            url=url,
            location_city=city,
        )
        listings.append(listing)

    if not listings:
        listings = _fallback_parse(page)

    return listings


def _fallback_parse(page) -> list[ScrapedListing]:
    listings: list[ScrapedListing] = []
    seen: set[str] = set()

    for link in page.css('a[href*="ID"]'):
        href = link.attrib.get("href", "")
        url = urljoin(OLX_BASE, href.split("#")[0])
        olx_id = _extract_olx_id(url)
        if not olx_id or olx_id in seen:
            continue

        parent = link.parent
        price_text = ""
        title = link.text.strip() or link.attrib.get("title", "")

        for _ in range(5):
            if parent is None:
                break
            price_el = parent.css('[data-testid="ad-price"], .css-10b0gli, p:contains("грн")')
            if price_el:
                price_text = price_el[0].text.strip()
            if not title:
                title_el = parent.css("h6, h4")
                if title_el:
                    title = title_el[0].text.strip()
            if price_text and title:
                break
            parent = getattr(parent, "parent", None)

        price = _parse_price(price_text)
        if price and title:
            seen.add(olx_id)
            listings.append(ScrapedListing(olx_id=olx_id, title=title, price=price, url=url))

    return listings


def scrape_category(url_path: str, price_min: int, price_max: int, enrich_details: bool = False) -> list[ScrapedListing]:
    all_listings: list[ScrapedListing] = []
    seen_ids: set[str] = set()

    for page_num in range(1, MAX_PAGES + 1):
        url = build_search_url(url_path, price_min, price_max)
        if page_num > 1:
            url += f"&page={page_num}"

        logger.info("Scraping %s (page %d)", url, page_num)

        try:
            page = _fetch_page(url)
        except Exception as e:
            logger.error("Failed to scrape %s: %s", url, e)
            break

        page_listings = _parse_listings_from_page(page)
        if not page_listings:
            logger.info("No listings on page %d, stopping", page_num)
            break

        new_count = 0
        for listing in page_listings:
            if listing.olx_id not in seen_ids:
                seen_ids.add(listing.olx_id)
                if enrich_details:
                    _enrich_listing_from_detail(listing)
                    time.sleep(1.0)
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
