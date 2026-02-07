import pandas as pd
from nsepython import nse_eq_symbols

def get_all_nse_symbols():
    symbols = nse_eq_symbols()
    df = pd.DataFrame(symbols, columns=["symbol"])
    return df
