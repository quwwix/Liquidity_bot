import re
import warnings
warnings.simplefilter("ignore")

from scrapling import Fetcher

def dump_html(url_path):
    base = "https://www.olx.ua"
    url = f"{base}{url_path}?search%5Bprivate_business%5D=private&search%5Bfilter_float_price%3Afrom%5D=4000&search%5Bfilter_float_price%3Ato%5D=20000"
    
    fetcher = Fetcher()
    res = fetcher.get(url, headers={"Referer": "https://www.google.com/"})
    html = res.text
    
    print(f"HTML length: {len(html)}")
    print(f"Has __NEXT_DATA__: {'__NEXT_DATA__' in html}")
    print(f"Has 'id=\"listing': {'id=\"listing' in html}")
    print(f"Has 'data-cy': {'data-cy' in html}")
    print(f"Has 'l-card': {'l-card' in html}")
    print(f"Has 'advert': {'advert' in html.lower()}")
    print(f"Has 'price': {'price' in html.lower()}")
    
    # Save first 5000 chars
    with open("/tmp/olx_page.html", "w") as f:
        f.write(html)
    print("\nSaved to /tmp/olx_page.html")
    
    # Find all script src
    scripts = re.findall(r'<script[^>]*src="([^"]*)"', html)
    print(f"\nExternal scripts: {scripts[:5]}")
    
    # Any JSON-looking inline scripts
    inline = re.findall(r'<script>(.{50,200})</script>', html, re.DOTALL)
    for sc in inline[:3]:
        print(f"Inline script: {sc[:150].strip()}")

if __name__ == "__main__":
    dump_html("/uk/elektronika/igry-i-igrovye-pristavki/pristavki/")
