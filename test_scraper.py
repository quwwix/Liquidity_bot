import asyncio
from app.scraper.olx import scrape_category
from app.scraper.categories import CATEGORIES

async def test():
    cat = next(c for c in CATEGORIES if c['slug'] == 'igrovi-konsoli')
    print(f"Scraping {cat['name']} - {cat['url_path']}")
    listings = scrape_category(cat['url_path'], 4000, 20000, False)
    print(f"Found {len(listings)} listings")
    if listings:
        print(f"First: {listings[0].title} - {listings[0].price} - {listings[0].url}")

if __name__ == "__main__":
    asyncio.run(test())
