"""
Scrapes all OLX categories and sends results to Render API.
Runs on GitHub Actions (IP not blocked by OLX).
"""

import json
import os
import time
import httpx

OLX_API = "https://www.olx.ua/api/v1/offers/"
RENDER_URL = os.environ["RENDER_URL"].rstrip("/")
INGEST_TOKEN = os.environ["INGEST_TOKEN"]

HEADERS_OLX = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, */*",
    "Accept-Language": "uk-UA,uk;q=0.9",
    "Referer": "https://www.olx.ua/",
}

CATEGORIES = [
    {"slug": "telefony", "name": "Телефони", "url_path": "/uk/elektronika/telefony-i-aksesuary/mobilnye-telefony-smartfony/"},
    {"slug": "noutbuki", "name": "Ноутбуки", "url_path": "/uk/elektronika/noutbuki-i-aksesuary/noutbuki/"},
    {"slug": "planshety", "name": "Планшети", "url_path": "/uk/elektronika/planshety-el-knigi-i-aksessuary/planshetnye-kompyutery/"},
    {"slug": "kompyutery", "name": "Комп'ютери", "url_path": "/uk/elektronika/kompyutery-i-komplektuyuschie/nastolnye-kompyutery/"},
    {"slug": "igrovi-konsoli", "name": "Ігрові консолі", "url_path": "/uk/elektronika/igry-i-igrovye-pristavki/pristavki/"},
    {"slug": "navushnyky", "name": "Навушники", "url_path": "/uk/elektronika/audiotehnika/naushniki/"},
    {"slug": "smart-godynnyky", "name": "Смарт-годинники", "url_path": "/uk/elektronika/telefony-i-aksesuary/smart-chasy-fitnes-braslety/"},
    {"slug": "fotoaparaty", "name": "Фотоапарати", "url_path": "/uk/elektronika/foto-video/tsifrovye-fotoapparaty/"},
    {"slug": "televizory", "name": "Телевізори", "url_path": "/uk/elektronika/tv-videotehnika/televizory/"},
    {"slug": "pylososy", "name": "Пилососи", "url_path": "/uk/elektronika/tehnika-dlya-doma/pylesosy/"},
    {"slug": "mikrokhvyli", "name": "Мікрохвильові печі", "url_path": "/uk/elektronika/tehnika-dlya-kuhni/mikrovolnovye-pechi/"},
    {"slug": "kavovarky", "name": "Кавоварки", "url_path": "/uk/elektronika/tehnika-dlya-kuhni/melkaya-bytovaya-tehnika/kofevarki-kofemolki/"},
    {"slug": "velosypedy", "name": "Велосипеди", "url_path": "/uk/hobbi-otdyh-i-sport/velo/velosipedy/"},
    {"slug": "instrumenty", "name": "Інструменти", "url_path": "/uk/dom-i-sad/instrumenty/"},
    {"slug": "mebel", "name": "Меблі", "url_path": "/uk/dom-i-sad/mebel/"},
    {"slug": "odyag", "name": "Одяг", "url_path": "/uk/moda-i-stil/odezhda/"},
    {"slug": "vzuttia", "name": "Взуття", "url_path": "/uk/moda-i-stil/q-%D0%B2%D0%B7%D1%83%D1%82%D1%82%D1%8F/"},
    {"slug": "sumky", "name": "Сумки", "url_path": "/uk/moda-i-stil/aksessuary/sumki/"},
    {"slug": "godynnyky", "name": "Годинники", "url_path": "/uk/moda-i-stil/naruchnye-chasy/"},
    {"slug": "dytiachi-kolyaski", "name": "Дитячі коляски", "url_path": "/uk/detskiy-mir/detskie-kolyaski/"},
    {"slug": "avtomobilni-aksesuary", "name": "Автоаксесуари", "url_path": "/uk/zapchasti-dlya-transporta/avtozapchasti-i-aksessuary/"},
    {"slug": "shyny-disky", "name": "Шини та диски", "url_path": "/uk/zapchasti-dlya-transporta/shiny-diski-i-kolesa/"},
    {"slug": "motocykly", "name": "Мотоцикли", "url_path": "/uk/transport/moto/"},
    {"slug": "instrumenty-muzychni", "name": "Музичні інструменти", "url_path": "/uk/hobbi-otdyh-i-sport/muzykalnye-instrumenty/"},
    {"slug": "knyhy", "name": "Книги", "url_path": "/uk/hobbi-otdyh-i-sport/knigi-zhurnaly/"},
]

PRICE_MIN = 4000
PRICE_MAX = 20000
MAX_PAGES = 5
PAGE_DELAY = 1.0
CATEGORY_DELAY = 3.0


def scrape_category(client: httpx.Client, cat: dict) -> list[dict]:
    listings = []
    seen_ids = set()
    query = cat["name"]

    for page in range(MAX_PAGES):
        params = {
            "offset": page * 40,
            "limit": 40,
            "query": query,
            "filter_float_price:from": PRICE_MIN,
            "filter_float_price:to": PRICE_MAX,
        }
        try:
            res = client.get(OLX_API, headers=HEADERS_OLX, params=params, timeout=15)
        except Exception as e:
            print(f"  Request error: {e}")
            break

        print(f"  Page {page+1}: HTTP {res.status_code}", end=" ")
        if res.status_code != 200:
            print(f"— blocked!")
            break

        ads = res.json().get("data", [])
        print(f"— {len(ads)} ads")
        if not ads:
            break

        for ad in ads:
            ad_id = str(ad.get("id", ""))
            if not ad_id or ad_id in seen_ids:
                continue
            seen_ids.add(ad_id)

            price = None
            for p in ad.get("params", []):
                if p.get("key") == "price":
                    val = p.get("value", {})
                    if isinstance(val, dict):
                        price = val.get("value")
                    break

            if price is None:
                continue

            location = ad.get("location", {})
            city = location.get("city", {}).get("name", "")
            region = location.get("region", {}).get("name", "")
            photos = ad.get("photos", [])

            listings.append({
                "olx_id": ad_id,
                "title": ad.get("title", ""),
                "price": float(price),
                "url": ad.get("url", ""),
                "description": ad.get("description", "")[:500],
                "location_city": city,
                "location_region": region,
                "location_full": f"{city}, {region}" if region else city,
                "listing_date": ad.get("created_time", ""),
                "images_count": len(photos),
                "images": [p.get("link") for p in photos if p.get("link")][:5],
            })

        time.sleep(PAGE_DELAY)

    return listings


def main():
    print(f"Starting scrape of {len(CATEGORIES)} categories...")
    all_data = []

    with httpx.Client(verify=False, follow_redirects=True) as client:
        for i, cat in enumerate(CATEGORIES):
            print(f"[{i+1}/{len(CATEGORIES)}] {cat['name']}...", end=" ", flush=True)
            listings = scrape_category(client, cat)
            print(f"{len(listings)} listings")

            all_data.append({
                "slug": cat["slug"],
                "name": cat["name"],
                "url_path": cat["url_path"],
                "listings": listings,
            })

            if i < len(CATEGORIES) - 1:
                time.sleep(CATEGORY_DELAY)

    total = sum(len(c["listings"]) for c in all_data)
    print(f"\nTotal: {total} listings. Sending to Render...")

    with httpx.Client(timeout=60) as client:
        r = client.post(
            f"{RENDER_URL}/api/ingest",
            json={"categories": all_data},
            headers={"X-Ingest-Token": INGEST_TOKEN},
        )
        print(f"Ingest response: {r.status_code} — {r.text}")


if __name__ == "__main__":
    main()
