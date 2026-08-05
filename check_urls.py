import logging
from scrapling import Fetcher
import warnings

warnings.simplefilter("ignore")

urls = [
    "/uk/elektronika/noutbuki-i-aksesuary/noutbuki/",
    "/uk/elektronika/planshety-el-knigi-i-aksessuary/planshetnye-kompyutery/",
    "/uk/elektronika/kompyutery-i-komplektuyuschie/nastolnye-kompyutery/",
    "/uk/elektronika/tehnika-dlya-kuhni/melkaya-bytovaya-tehnika/kofevarki-kofemolki/",
    "/uk/moda-i-stil/q-%D0%B2%D0%B7%D1%83%D1%82%D1%82%D1%8F/"
]

def check_all():
    fetcher = Fetcher()
    for u in urls:
        url = f"https://www.olx.ua{u}?search%5Bprivate_business%5D=private&search%5Bfilter_float_price%3Afrom%5D=4000&search%5Bfilter_float_price%3Ato%5D=20000"
        try:
            res = fetcher.get(url, headers={"Referer": "https://www.google.com/"})
            print(f"[{res.status}] {u}")
        except Exception as e:
            print(f"[ERROR] {u}: {e}")
        
if __name__ == "__main__":
    check_all()
