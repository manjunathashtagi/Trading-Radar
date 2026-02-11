import pandas as pd
import requests


def fetch_bulk_snapshot():
    url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers, timeout=5)
    response = session.get(url, headers=headers, timeout=10)

    data = response.json()
    df = pd.DataFrame(data["data"])

    return df


def scan_bulk(stage1_symbols):
    try:
        df = fetch_bulk_snapshot()

        # Filter only Stage-1 shortlisted stocks
        df = df[df["symbol"].isin(stage1_symbols)]

        signals = []

        for _, row in df.iterrows():

            symbol = row["symbol"]
            last_price = float(row["lastPrice"])
            prev_close = float(row["previousClose"])
            pchange = float(row["pChange"])
            sector = row.get("industry", "Unknown")

            # --- Simple Gap Continuation Logic ---
            if pchange > 0 and last_price > prev_close:
                action = "BUY"
            elif pchange < 0 and last_price < prev_close:
                action = "SELL"
            else:
                continue

            # --- Risk Model (1% stop, 1:2 RR) ---
            sl_percent = 1.0
            sl_distance = last_price * (sl_percent / 100)

            if action == "BUY":
                sl = last_price - sl_distance
                tp = last_price + (2 * sl_distance)
            else:
                sl = last_price + sl_distance
                tp = last_price - (2 * sl_distance)

            rr = 2.0
            gap_tag = "Gap Up" if pchange > 0 else "Gap Down"

            confidence = 70
            if abs(pchange) >= 2:
                confidence += 10
            if abs(pchange) >= 3:
                confidence += 5

            signals.append({
                "symbol": symbol,
                "action": action,
                "entry": last_price,
                "sl": sl,
                "tp": tp,
                "rr": rr,
                "sl_percent": sl_percent,
                "gap": round(pchange, 2),
                "gap_tag": gap_tag,
                "sector": sector,
                "confidence": min(confidence, 95)
            })

        return signals

    except Exception as e:
        print("Bulk scan error:", e)
        return []