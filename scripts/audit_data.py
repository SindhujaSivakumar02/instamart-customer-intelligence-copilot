
import csv
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def read_csv(filename):
    with open(RAW / filename, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def audit_customers():
    customers = read_csv("customers.csv")

    blank_ages = sum(not row["age"].strip() for row in customers)

    invalid_ages = 0
    for row in customers:
        try:
            age = int(row["age"])
            if age < 10 or age > 100:
                invalid_ages += 1
        except ValueError:
            if row["age"].strip():
                invalid_ages += 1

    cities = {
        row["city"].strip()
        for row in customers
        if row["city"].strip()
    }

    genders = {
        row["gender"].strip()
        for row in customers
        if row["gender"].strip()
    }

    blank_genders = sum(not row["gender"].strip() for row in customers)

    print("\nCUSTOMER AUDIT")
    print("-" * 40)
    print("Total customers:", len(customers))
    print("Blank ages:", blank_ages)
    print("Invalid ages:", invalid_ages)
    print("Distinct city spellings:", len(cities))
    print("Distinct nonblank gender spellings:", len(genders))
    print("Blank genders:", blank_genders)


def audit_orders():
    orders = read_csv("orders.csv")

    duplicate_count = len(orders) - len({
        tuple(row.values()) for row in orders
    })

    pending = sum(
        row["status"].strip().lower() == "pending"
        for row in orders
    )

    unique_order_ids = len({
        row["order_id"] for row in orders
    })

    nonnumeric_amounts = 0
    for row in orders:
        try:
            float(row["order_amount"])
        except ValueError:
            nonnumeric_amounts += 1

    negative_delivery = 0
    blank_delivery = 0

    for row in orders:
        value = row["delivery_minutes"].strip()

        if not value:
            blank_delivery += 1
        else:
            try:
                if float(value) < 0:
                    negative_delivery += 1
            except ValueError:
                pass

    print("\nORDER AUDIT")
    print("-" * 40)
    print("Total raw orders:", len(orders))
    print("Exact duplicate rows:", duplicate_count)
    print("Pending rows:", pending)
    print("Distinct order IDs:", unique_order_ids)
    print("Nonnumeric order amounts:", nonnumeric_amounts)
    print("Negative delivery times:", negative_delivery)
    print("Blank delivery times:", blank_delivery)


if __name__ == "__main__":
    audit_customers()
    audit_orders()
