from nsepython import equity_history
from datetime import datetime, timedelta
import pandas as pd

def fetch_nse_ohlc(symbol: str):
    try:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)

        df = equity_history(
            symbol=symbol,
            series="EQ",
            start_date=from_date.strftime("%d-%m-%Y"),
            end_date=to_date.strftime("%d-%m-%Y")
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df["DATETIME"] = pd.to_datetime(df["TIMESTAMP"] + " " + df["TIME"])
        df = df.sort_values("DATETIME")

        df = df.rename(columns={
            "OPEN": "open",
            "HIGH": "high",
            "LOW": "low",
            "CLOSE": "close",
            "VOLUME": "volume"
        })

        return df[["open", "high", "low", "close", "volume"]]

    except Exception:
        return pd.DataFrame()
