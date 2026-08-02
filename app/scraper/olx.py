"""OLX Ukraine scraper using Scrapling browser fetcher."""

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin

from app.scraper.categories import OLX_BASE, CATEGORIES, build_search_url

logger = logging.getLogger(__name__)

MAX_PAGES = 3
PAGE_DELAY = 2.0


@dataclass
class ScrapedListing:
    olx_id: str
    title: str
    price: float
    url: str
    is_business: bool = False


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

        seen_ids.add(olx_id)
        listings.append(ScrapedListing(olx_id=olx_id, title=title, price=price, url=url))

    if not listings:
        listings = _fallback_parse(page)

    return listings


def _fallback_parse(page) -> list[ScrapedListing]:
    """Fallback parser for alternate OLX markup."""
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


def _fetch_page(url: str):
    """Fetch page using Scrapling with fallback fetchers."""
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
        from scrapling.fetchers import DynamicFetcher

        return DynamicFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            wait_selector='a[href*="ID"]',
            timeout=60000,
        )


def scrape_category(url_path: str, price_min: int, price_max: int) -> list[ScrapedListing]:
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
