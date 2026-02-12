import pandas as pd
import requests
import time


def fetch_bulk_snapshot():
    url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    session = requests.Session()

    # Warmup request
    session.get("https://www.nseindia.com", headers=headers, timeout=20)
    time.sleep(1)

    for attempt in range(3):
        try:
            response = session.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data["data"])
            return df
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(2)

    print("Bulk quote fetch failed.")
    return pd.DataFrame()


def scan_bulk(stage1_symbols):
    try:
        df = fetch_bulk_snapshot()

        if df.empty:
            return []

        df = df[df["symbol"].isin(stage1_symbols)]

        signals = []

        for _, row in df.iterrows():

            symbol = row["symbol"]
            last_price = float(row["lastPrice"])
            prev_close = float(row["previousClose"])
            pchange = float(row["pChange"])
            high = float(row["dayHigh"])
            low = float(row["dayLow"])
            volume = float(row.get("totalTradedVolume", 0))
            sector = row.get("industry", "Unknown")

            # Strong continuation logic
            if pchange >= 1.2 and last_price >= high * 0.995:
                action = "BUY"
            elif pchange <= -1.2 and last_price <= low * 1.005:
                action = "SELL"
            else:
                continue

            sl_percent = 1.0
            sl_distance = last_price * (sl_percent / 100)

            if action == "BUY":
                sl = last_price - sl_distance
                tp = last_price + (2 * sl_distance)
            else:
                sl = last_price + sl_distance
                tp = last_price - (2 * sl_distance)

            confidence = 70
            if abs(pchange) >= 2:
                confidence += 10
            if volume > 500000:
                confidence += 5

            signals.append({
                "symbol": symbol,
                "action": action,
                "entry": last_price,
                "sl": sl,
                "tp": tp,
                "rr": 2,
                "sl_percent": sl_percent,
                "gap": round(pchange, 2),
                "gap_tag": "Gap Up" if pchange > 0 else "Gap Down",
                "sector": sector,
                "confidence": min(confidence, 95)
            })

        return signals

    except Exception as e:
        print("Bulk scan error:", e)
        return []