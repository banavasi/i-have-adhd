from legacy.billing import calc


def build_report(customer, orders):
    out = ""
    out = out + "REPORT FOR " + customer["name"].upper() + "\n"
    out = out + "=" * 30 + "\n"
    grand = 0
    for o in orders:
        tot = calc.calc_total(o["items"], customer["type"])
        out = out + "order %s  %s  %.2f\n" % (o["id"], o["date"], tot)
        grand = grand + tot
    out = out + "-" * 30 + "\n"
    out = out + "TOTAL %.2f\n" % grand
    if calc.last_total() > 500:
        out = out + "* last order over 500, flag for review\n"
    return out
