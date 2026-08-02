"""OLX Ukraine category definitions for liquidity tracking."""

OLX_BASE = "https://www.olx.ua"

# Main resale-relevant categories on OLX Ukraine
CATEGORIES = [
    {"slug": "telefony", "name": "Телефони", "url_path": "/uk/elektronika/telefony-i-aksesuary/telefony/"},
    {"slug": "noutbuki", "name": "Ноутбуки", "url_path": "/uk/elektronika/noutbuki-i-kompyutery/noutbuki/"},
    {"slug": "planshety", "name": "Планшети", "url_path": "/uk/elektronika/noutbuki-i-kompyutery/planshety/"},
    {"slug": "kompyutery", "name": "Комп'ютери", "url_path": "/uk/elektronika/noutbuki-i-kompyutery/kompyutery/"},
    {"slug": "igrovi-konsoli", "name": "Ігрові консолі", "url_path": "/uk/elektronika/igrovi-pristavki-i-aksesuary/"},
    {"slug": "navushnyky", "name": "Навушники", "url_path": "/uk/elektronika/telefony-i-aksesuary/navushnyky-i-aksesuary/"},
    {"slug": "smart-godynnyky", "name": "Смарт-годинники", "url_path": "/uk/elektronika/telefony-i-aksesuary/smart-godynnyky/"},
    {"slug": "fotoaparaty", "name": "Фотоапарати", "url_path": "/uk/elektronika/foto-video-audio/fotoaparaty/"},
    {"slug": "televizory", "name": "Телевізори", "url_path": "/uk/elektronika/televizory-i-multymedia/televizory/"},
    {"slug": "pylososy", "name": "Пилососи", "url_path": "/uk/dom-i-sad/pobutova-tehnika/pylososy/"},
    {"slug": "mikrokhvyli", "name": "Мікрохвильові печі", "url_path": "/uk/dom-i-sad/pobutova-tehnika/mikrokhvyliovi-pechi/"},
    {"slug": "kavovarky", "name": "Кавоварки", "url_path": "/uk/dom-i-sad/pobutova-tehnika/kavovarky/"},
    {"slug": "velosypedy", "name": "Велосипеди", "url_path": "/uk/sport-i-vidpochynok/velosypedy/"},
    {"slug": "instrumenty", "name": "Інструменти", "url_path": "/uk/dom-i-sad/instrumenty/"},
    {"slug": "mebel", "name": "Меблі", "url_path": "/uk/dom-i-sad/mebli/"},
    {"slug": "odyag", "name": "Одяг", "url_path": "/uk/moda-i-styl/odyag/"},
    {"slug": "vzuttia", "name": "Взуття", "url_path": "/uk/moda-i-styl/vzuttia/"},
    {"slug": "sumky", "name": "Сумки", "url_path": "/uk/moda-i-styl/sumky/"},
    {"slug": "godynnyky", "name": "Годинники", "url_path": "/uk/moda-i-styl/godynnyky/"},
    {"slug": "dytiachi-kolyaski", "name": "Дитячі коляски", "url_path": "/uk/dytiachyi-svit/dytiachi-kolyaski/"},
    {"slug": "avtomobilni-aksesuary", "name": "Автоаксесуари", "url_path": "/uk/transport/avtomobilni-aksesuary/"},
    {"slug": "shyny-disky", "name": "Шини та диски", "url_path": "/uk/transport/shyny-i-disky/"},
    {"slug": "motocykly", "name": "Мотоцикли", "url_path": "/uk/transport/motocykly/"},
    {"slug": "instrumenty-muzychni", "name": "Музичні інструменти", "url_path": "/uk/hobbi-vidpochynok-i-sport/muzychni-instrumenty/"},
    {"slug": "knyhy", "name": "Книги", "url_path": "/uk/hobbi-vidpochynok-i-sport/knyhy/"},
]


def build_search_url(url_path: str, price_min: int, price_max: int) -> str:
    base = f"{OLX_BASE}{url_path}"
    params = (
        f"search%5Bprivate_business%5D=private"
        f"&search%5Bfilter_float_price%3Afrom%5D={price_min}"
        f"&search%5Bfilter_float_price%3Ato%5D={price_max}"
    )
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{params}"
