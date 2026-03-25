import requests

def get_session():
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    }

    session.headers.update(headers)

    # 🔥 Warm-up to avoid blocking
    session.get("https://www.nseindia.com")
    session.get("https://www.nseindia.com/market-data/live-equity-market")

    return session


def get_quote(session, symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"

        res = session.get(url, timeout=5)

        if res.status_code != 200:
            return None

        try:
            data = res.json()
        except:
            return None

        if "priceInfo" not in data:
            return None

        price = data["priceInfo"]["lastPrice"]
        open_price = data["priceInfo"]["open"]
        high = data["priceInfo"]["intraDayHighLow"]["max"]

        volume = data.get("securityWiseDP", {}).get("quantityTraded", 0)

        return {
            "price": price,
            "open": open_price,
            "high": high,
            "volume": volume
        }

    except:
        return None