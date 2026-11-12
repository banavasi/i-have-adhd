"""Command line entry point for legacy-shop."""

import sys

from legacy.billing import report, store


def main(argv):
    if len(argv) < 3 or argv[1] != "report":
        print("usage: python app.py report <customer>")
        return 2
    db = store.open_db()
    store.seed(db)
    customer = store.find_customer(db, argv[2])
    if customer is None:
        print("unknown customer: " + argv[2])
        return 1
    orders = store.orders_for(db, customer["id"])
    print(report.build_report(customer, orders))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
