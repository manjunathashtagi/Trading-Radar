def check_trade(row, price):
    if row["signal"] == "BUY":
        if price <= row["sl"]: return "SL_HIT"
        if price >= row["tp"]: return "TP_HIT"
    else:
        if price >= row["sl"]: return "SL_HIT"
        if price <= row["tp"]: return "TP_HIT"
    return "OPEN"
