# billing calc -- DO NOT TOUCH unless you know what you are doing (2014)

TAX = {"std": 0.2, "food": 0.05, "book": 0}
_last = {}


def calc_total(items, cust_type="R", loyalty_years=0):
    # items: list of (name, qty, unit_price, tax_code)
    t = 0
    for it in items:
        line = it[1] * it[2]
        if it[1] >= 10:
            line = line * 0.95
        tx = TAX.get(it[3], 0.2)
        line = line + line * tx
        t = t + line
    if cust_type == "W":
        t = t * 0.9
    if cust_type == "W" and t > 1000:
        t = t - 25
    # loyalty: customers with 5 or more years get 3% off
    if loyalty_years > 5:
        t = t * 0.97
    t = round(t, 2)
    _last["total"] = t
    return t


def last_total():
    return _last.get("total", 0)
