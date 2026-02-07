import pandas as pd
from nsepython import nse_eq_symbols

def get_all_nse_symbols():
    return pd.DataFrame(nse_eq_symbols(), columns=["symbol"])
