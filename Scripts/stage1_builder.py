import pandas as pd
import yfinance as yf


class Stage1DataBuilder:
    def __init__(self, symbol="^NSEI", interval="5m", period="5d"):
        self.symbol = symbol
        self.interval = interval
        self.period = period
        self.df = None

    def fetch_data(self):
        print(f"[INFO] Fetching data for {self.symbol}")
        self.df = yf.download(
            tickers=self.symbol,
            interval=self.interval,
            period=self.period,
            progress=False
        )

        if self.df.empty:
            raise ValueError("No data fetched!")

        self.df.reset_index(inplace=True)
        return self.df

    def clean_data(self):
        print("[INFO] Cleaning data")
        self.df.dropna(inplace=True)
        return self.df

    def save(self, path="stage1_output.csv"):
        print(f"[INFO] Saving to {path}")
        self.df.to_csv(path, index=False)


if __name__ == "__main__":
    builder = Stage1DataBuilder(symbol="^NSEI")
    df = builder.fetch_data()
    df = builder.clean_data()
    builder.save()