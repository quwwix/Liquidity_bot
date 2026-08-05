import logging
from scrapling import Fetcher
import json
import warnings

warnings.simplefilter("ignore")

queries = ["ноутбуки", "планшети", "комп'ютери", "кавоварки", "взуття"]

def find_categories():
    fetcher = Fetcher()
    for q in queries:
        try:
            url = f"https://www.olx.ua/uk/list/q-{q}/"
            res = fetcher.get(url, headers={"Referer": "https://www.google.com/"})
            # extract category links
            from scrapling import Selector
            page = Selector(res.text)
            links = page.css('a[href*="/uk/elektronika/"], a[href*="/uk/moda-i-stil/"]')
            cats = set()
            for link in links:
                href = link.attrib.get('href', '')
                if href and href.count('/') >= 4 and 'q-' not in href:
                    cats.add(href.split('?')[0])
            print(f"[{q}] Potential categories: {cats}")
        except Exception as e:
            print(f"[ERROR] {q}: {e}")
        
if __name__ == "__main__":
    find_categories()
