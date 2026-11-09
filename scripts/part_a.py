import csv
import sqlite3
import statistics
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)

def read_csv(name):
    with open(RAW / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def save_csv(name, rows):
    if not rows:
        return
    with open(CLEAN / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

# CUSTOMERS
customers = read_csv("customers.csv")
for c in customers:
    c["city"] = c["city"].strip().title()
    gender = (c.get("gender") or "").strip().lower()
    c["gender"] = "male" if gender in ("m", "male") else (
        "female" if gender in ("f", "female") else "unknown"
    )
    try:
        age = float(c["age"])
        if not 10 <= age <= 100:
            age = None
    except (ValueError, TypeError):
        age = None
    c["_age"] = age

city_medians = {}
for city in set(c["city"] for c in customers):
    ages = [c["_age"] for c in customers if c["city"] == city and c["_age"] is not None]
    city_medians[city] = statistics.median(ages) if ages else 30

for c in customers:
    if c["_age"] is None:
        c["_age"] = city_medians[c["city"]]
    c["age"] = str(int(round(c["_age"])))
    c.pop("_age")
    try:
        c["signup_date"] = datetime.strptime(
            c["signup_date"], "%Y-%m-%d"
        ).strftime("%Y-%m-%d")
    except Exception:
        pass

# PRODUCTS
products = read_csv("products.csv")
product_map = {p["product_id"]: p for p in products}

# ORDERS
raw_orders = read_csv("orders.csv")
seen = set()
unique = []
for r in raw_orders:
    key = tuple(r.items())
    if key not in seen:
        seen.add(key)
        unique.append(r)

def parse_date(value):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass
    return datetime.min

unique.sort(key=lambda r: parse_date(r["order_ts"]))
latest = {}
for r in unique:
    latest[r["order_id"]] = r

orders = list(latest.values())
for r in orders:
    p = product_map.get(r["product_id"], {})
    try:
        qty = float(r["quantity"])
    except Exception:
        qty = 0
    try:
        discount = float(r["discount_pct"] or 0)
    except Exception:
        discount = 0
    try:
        amount = float(r["order_amount"])
    except Exception:
        amount = None
    if amount is None:
        amount = float(p.get("price_inr", 0)) * qty * (1 - discount / 100)
    r["order_amount"] = f"{amount:.2f}"
    r["discount_pct"] = str(discount)
    r["quantity"] = str(qty)
    r["category"] = p.get("category", "Unknown")
    try:
        delivery = float(r["delivery_minutes"])
        if delivery < 0:
            delivery = None
    except Exception:
        delivery = None
    r["_delivery"] = delivery

# Fill missing completed delivery times with category median
medians = {}
for category in set(r["category"] for r in orders):
    vals = [
        r["_delivery"] for r in orders
        if r["category"] == category
        and r["status"].lower() == "completed"
        and r["_delivery"] is not None
    ]
    if vals:
        medians[category] = statistics.median(vals)

for r in orders:
    if r["status"].lower() == "pending":
        continue
    if r["status"].lower() == "completed" and r["_delivery"] is None:
        r["_delivery"] = medians.get(r["category"])
    r["delivery_minutes"] = (
        "" if r["_delivery"] is None else str(round(r["_delivery"], 2))
    )
    r.pop("_delivery")
    r.pop("category")

orders = [r for r in orders if r["status"].lower() != "pending"]

# SAVE FILES
save_csv("customers.csv", customers)
save_csv("products.csv", products)
save_csv("orders.csv", orders)

# SQLITE
db = ROOT / "data" / "instamart.db"
with sqlite3.connect(db) as conn:
    for table, rows in [
        ("customers", customers), ("products", products), ("orders", orders)
    ]:
        columns = list(rows[0].keys())
        definitions = ", ".join(f'"{c}" TEXT' for c in columns)
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute(f'CREATE TABLE "{table}" ({definitions})')
        placeholders = ",".join("?" for _ in columns)
        conn.executemany(
            f'INSERT INTO "{table}" VALUES ({placeholders})',
            [[r.get(c, "") for c in columns] for r in rows]
        )

    checks = {
        "customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "pending": conn.execute("SELECT COUNT(*) FROM orders WHERE lower(status)='pending'").fetchone()[0],
        "completed": conn.execute("SELECT COUNT(*) FROM orders WHERE lower(status)='completed'").fetchone()[0],
        "cancelled": conn.execute("SELECT COUNT(*) FROM orders WHERE lower(status)='cancelled'").fetchone()[0],
        "missing_amount": conn.execute("SELECT COUNT(*) FROM orders WHERE order_amount IS NULL OR order_amount=''").fetchone()[0],
        "missing_completed_delivery": conn.execute(
            "SELECT COUNT(*) FROM orders WHERE lower(status)='completed' AND (delivery_minutes IS NULL OR delivery_minutes='')"
        ).fetchone()[0]
    }

print("PART A CHECKPOINTS")
for k, v in checks.items():
    print(k, ":", v)

assert checks["customers"] == 1200
assert checks["products"] == 40
assert checks["orders"] == 12309
assert checks["pending"] == 0
assert checks["completed"] == 11110
assert checks["cancelled"] == 1199
assert checks["missing_amount"] == 0
assert checks["missing_completed_delivery"] == 0

revenue = conn.execute if False else None
with sqlite3.connect(db) as conn:
    revenue = conn.execute(
        "SELECT SUM(CAST(order_amount AS REAL)) FROM orders WHERE lower(status)='completed'"
    ).fetchone()[0]

print(f"Completed revenue: INR {revenue:,.2f}")
print("ALL CHECKPOINTS PASSED")