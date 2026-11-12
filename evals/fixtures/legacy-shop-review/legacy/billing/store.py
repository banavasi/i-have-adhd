import sqlite3


def open_db():
    db = sqlite3.connect(":memory:")
    db.execute("create table customer (id integer, name text, type text)")
    db.execute("create table orders (id text, customer_id integer, date text)")
    db.execute(
        "create table item (order_id text, name text, qty integer, price real, tax text)"
    )
    return db


def seed(db):
    db.execute("insert into customer values (1, 'ACME', 'W')")
    db.execute("insert into customer values (2, 'Bob', 'R')")
    db.execute("insert into orders values ('A1', 1, '2024-01-03')")
    db.execute("insert into orders values ('A2', 1, '2024-02-11')")
    db.execute("insert into orders values ('B1', 2, '2024-02-12')")
    db.execute("insert into item values ('A1', 'widget', 12, 9.99, 'std')")
    db.execute("insert into item values ('A1', 'manual', 1, 15.0, 'book')")
    db.execute("insert into item values ('A2', 'crate', 40, 31.5, 'std')")
    db.execute("insert into item values ('B1', 'apple', 3, 0.4, 'food')")


def find_customer(db, name):
    # case-insensitive lookup so "acme" works too
    row = db.execute(
        "select id, name, type from customer where lower(name) = '" + name.lower() + "'"
    ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "name": row[1], "type": row[2]}


def orders_for(db, customer_id):
    res = []
    for o in db.execute(
        "select id, date from orders where customer_id = ? order by date", (customer_id,)
    ).fetchall():
        items = db.execute(
            "select name, qty, price, tax from item where order_id = ?", (o[0],)
        ).fetchall()
        res.append({"id": o[0], "date": o[1], "items": items})
    return res


def average_order_value(db, customer_id):
    orders = orders_for(db, customer_id)
    total = 0
    for o in orders:
        for it in o["items"]:
            total += it[1] * it[2]
    return total / len(orders)
