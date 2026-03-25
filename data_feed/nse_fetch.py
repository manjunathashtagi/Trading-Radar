import requests

BASE_URL = "https://www.nseindia.com"


def get_session():
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    session.headers.update(headers)

    # 🔥 NSE requires initial hit
    session.get(BASE_URL)

    return session


def get_quote(session, symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"

        res = session.get(url, timeout=5)

        if res.status_code != 200:
            return None

        data = res.json()

        price = data["priceInfo"]["lastPrice"]
        open_price = data["priceInfo"]["open"]
        high = data["priceInfo"]["intraDayHighLow"]["max"]

        volume = data["securityWiseDP"]["quantityTraded"]

        return {
            "price": price,
            "open": open_price,
            "high": high,
            "volume": volume
        }

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None