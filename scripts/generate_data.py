"""
generate_data.py
-----------------
Generates a synthetic, but realistic, raw e-commerce transaction dataset
that mirrors the structure of the well-known "Online Retail" datasets
(InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice,
CustomerID, Country).

Why synthetic data?
This project is designed to run fully offline / in any CI environment
without depending on an external file download that could go stale or
be rate-limited. The generator deliberately injects the same kinds of
"messiness" found in real retail data so the ETL step has real work to do:

  - Cancelled orders (InvoiceNo starting with "C")
  - Missing CustomerID values (guest checkouts)
  - Occasional negative quantities / zero prices (data entry errors)
  - Duplicate rows
  - A long-tail product catalog with categories

Run:
    python scripts/generate_data.py
Produces:
    data/raw_sales.csv
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "raw_sales.csv"

N_CUSTOMERS = 800
N_PRODUCTS = 250
N_TRANSACTIONS = 50000
START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2024, 12, 31)

COUNTRIES = [
    "United Kingdom", "Germany", "France", "Ireland", "Spain",
    "Netherlands", "Belgium", "Portugal", "Italy", "Switzerland",
    "Sweden", "Norway", "Australia", "USA", "Canada",
]
# Weight UK heavily, like the real dataset (UK-based retailer)
COUNTRY_WEIGHTS = [40, 8, 8, 6, 5, 5, 4, 3, 4, 3, 3, 3, 3, 3, 2]

CATEGORIES = {
    "HOME DECOR": ["candle holder", "wall clock", "photo frame", "vase", "wall art"],
    "KITCHENWARE": ["mug", "tea towel", "cake stand", "baking tin", "lunch box"],
    "STATIONERY": ["notebook", "pencil case", "greeting card", "gift wrap", "sticker set"],
    "TOYS": ["wooden toy", "puzzle", "building blocks", "spinning top", "toy car"],
    "GARDEN": ["plant pot", "watering can", "garden sign", "bird feeder", "wind chime"],
    "LIGHTING": ["fairy lights", "table lamp", "lantern", "string lights", "night light"],
}


def build_products(n):
    products = []
    cats = list(CATEGORIES.keys())
    for i in range(n):
        category = random.choice(cats)
        noun = random.choice(CATEGORIES[category])
        adjective = random.choice(
            ["vintage", "retro", "rustic", "mini", "floral", "striped",
             "ceramic", "wooden", "metal", "pastel", "classic", "modern"]
        )
        description = f"{adjective} {noun}".upper()
        stock_code = f"{10000 + i}"
        unit_price = round(random.uniform(0.85, 49.99), 2)
        products.append((stock_code, description, category, unit_price))
    return products


def build_customers(n):
    customers = []
    for i in range(n):
        customer_id = 12000 + i
        country = random.choices(COUNTRIES, weights=COUNTRY_WEIGHTS, k=1)[0]
        customers.append((customer_id, country))
    return customers


def random_date(start, end):
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def main():
    products = build_products(N_PRODUCTS)
    customers = build_customers(N_CUSTOMERS)

    rows = []
    invoice_counter = 536365  # starting invoice number, matches real dataset style

    n_written = 0
    while n_written < N_TRANSACTIONS:
        invoice_counter += 1
        invoice_no = str(invoice_counter)

        is_cancellation = random.random() < 0.02
        if is_cancellation:
            invoice_no = "C" + invoice_no

        # occasionally a guest checkout with no customer id
        has_customer = random.random() > 0.06
        customer_id, country = random.choice(customers)
        if not has_customer:
            customer_id = ""

        invoice_date = random_date(START_DATE, END_DATE)

        # each invoice has a handful of line items
        n_lines = random.randint(1, 8)
        for _ in range(n_lines):
            if n_written >= N_TRANSACTIONS:
                break
            stock_code, description, category, unit_price = random.choice(products)

            quantity = random.randint(1, 24)
            if is_cancellation:
                quantity = -quantity
            elif random.random() < 0.005:
                # rare data entry error
                quantity = -quantity

            price = unit_price
            if random.random() < 0.003:
                price = 0.0  # rare bad data row

            rows.append(
                [
                    invoice_no,
                    stock_code,
                    description,
                    quantity,
                    invoice_date.strftime("%Y-%m-%d %H:%M:%S"),
                    price,
                    customer_id,
                    country,
                ]
            )
            n_written += 1

    # inject a handful of exact duplicate rows, common in raw exports
    rows += random.sample(rows, k=int(len(rows) * 0.004))
    random.shuffle(rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["InvoiceNo", "StockCode", "Description", "Quantity",
             "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
        )
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
