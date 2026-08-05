import httpx
import json

def test_api():
    query = "Ігрові консолі"
    url = "https://www.olx.ua/api/v1/offers/"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
    }
    params = {
        'offset': 0,
        'limit': 5,
        'query': query,
        'filter_float_price:from': 4000,
        'filter_float_price:to': 20000,
        'private_business': 'private'
    }
    with httpx.Client(verify=False, timeout=10.0) as client:
        res = client.get(url, headers=headers, params=params)
        print("Status:", res.status_code)
        data = res.json()
        ads = data.get('data', [])
        print("Found", len(ads), "ads")
        for ad in ads:
            print("-", ad.get('title'), ad.get('price', {}).get('value', {}).get('value'))

if __name__ == "__main__":
    test_api()
