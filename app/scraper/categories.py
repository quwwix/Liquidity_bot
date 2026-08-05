"""OLX Ukraine category definitions for liquidity tracking."""

OLX_BASE = "https://www.olx.ua"

# Main resale-relevant categories on OLX Ukraine
CATEGORIES = [
    {"slug": "telefony", "name": "Телефони", "url_path": "/uk/elektronika/telefony-i-aksesuary/mobilnye-telefony-smartfony/"},
    {"slug": "noutbuki", "name": "Ноутбуки", "url_path": "/uk/elektronika/noutbuki-i-aksessuary/noutbuki/"},
    {"slug": "planshety", "name": "Планшети", "url_path": "/uk/elektronika/planshety/"},
    {"slug": "kompyutery", "name": "Комп'ютери", "url_path": "/uk/elektronika/kompyutery-i-komplektuyushchie/nastolnye-kompyutery/"},
    {"slug": "igrovi-konsoli", "name": "Ігрові консолі", "url_path": "/uk/elektronika/igry-i-igrovye-pristavki/pristavki/"},
    {"slug": "navushnyky", "name": "Навушники", "url_path": "/uk/elektronika/audiotehnika/naushniki/"},
    {"slug": "smart-godynnyky", "name": "Смарт-годинники", "url_path": "/uk/elektronika/telefony-i-aksesuary/smart-chasy-fitnes-braslety/"},
    {"slug": "fotoaparaty", "name": "Фотоапарати", "url_path": "/uk/elektronika/foto-video/fotoapparaty/"},
    {"slug": "televizory", "name": "Телевізори", "url_path": "/uk/elektronika/tv-videotehnika/televizory/"},
    {"slug": "pylososy", "name": "Пилососи", "url_path": "/uk/elektronika/tehnika-dlya-doma/pylesosy/"},
    {"slug": "mikrokhvyli", "name": "Мікрохвильові печі", "url_path": "/uk/elektronika/tehnika-dlya-kuhni/mikrovolnovye-pechi/"},
    {"slug": "kavovarky", "name": "Кавоварки", "url_path": "/uk/elektronika/tehnika-dlya-kuhni/kavovarki-kavomolki/"},
    {"slug": "velosypedy", "name": "Велосипеди", "url_path": "/uk/sport-vidpochinok/velosipedi/"},
    {"slug": "instrumenty", "name": "Інструменти", "url_path": "/uk/dom-i-sad/instrumenty/"},
    {"slug": "mebel", "name": "Меблі", "url_path": "/uk/dom-i-sad/mebel/"},
    {"slug": "odyag", "name": "Одяг", "url_path": "/uk/moda-i-stil/odezhda/"},
    {"slug": "vzuttia", "name": "Взуття", "url_path": "/uk/moda-i-stil/obuv/"},
    {"slug": "sumky", "name": "Сумки", "url_path": "/uk/moda-i-stil/aksessuary/sumki/"},
    {"slug": "godynnyky", "name": "Годинники", "url_path": "/uk/moda-i-stil/naruchnye-chasy/"},
    {"slug": "dytiachi-kolyaski", "name": "Дитячі коляски", "url_path": "/uk/detskiy-mir/detskie-kolyaski/"},
    {"slug": "avtomobilni-aksesuary", "name": "Автоаксесуари", "url_path": "/uk/zapchasti-dlya-transporta/avtozapchasti-i-aksessuary/"},
    {"slug": "shyny-disky", "name": "Шини та диски", "url_path": "/uk/zapchasti-dlya-transporta/shiny-diski-i-kolesa/"},
    {"slug": "motocykly", "name": "Мотоцикли", "url_path": "/uk/transport/moto/"},
    {"slug": "instrumenty-muzychni", "name": "Музичні інструменти", "url_path": "/uk/hobbi-otdyh-i-sport/muzykalnye-instrumenty/"},
    {"slug": "knyhy", "name": "Книги", "url_path": "/uk/hobbi-otdyh-i-sport/knigi-zhurnaly/"},
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
