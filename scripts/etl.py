"""
etl.py
-------
Loads the raw sales CSV into a staging table, cleans it, and builds the
star schema (dim_customer, dim_product, dim_date, fact_sales) inside a
DuckDB warehouse file.

Run:
    python scripts/etl.py
Produces:
    warehouse.duckdb
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw_sales.csv"
SCHEMA_SQL = ROOT / "sql" / "schema.sql"
DB_PATH = ROOT / "warehouse.duckdb"

CATEGORY_KEYWORDS = {
    "HOME DECOR": ["CANDLE", "CLOCK", "FRAME", "VASE", "WALL ART"],
    "KITCHENWARE": ["MUG", "TEA TOWEL", "CAKE STAND", "BAKING TIN", "LUNCH BOX"],
    "STATIONERY": ["NOTEBOOK", "PENCIL CASE", "GREETING CARD", "GIFT WRAP", "STICKER"],
    "TOYS": ["TOY", "PUZZLE", "BUILDING BLOCKS", "SPINNING TOP"],
    "GARDEN": ["PLANT POT", "WATERING CAN", "GARDEN SIGN", "BIRD FEEDER", "WIND CHIME"],
    "LIGHTING": ["FAIRY LIGHTS", "LAMP", "LANTERN", "STRING LIGHTS", "NIGHT LIGHT"],
}


def run_schema(con):
    con.execute(SCHEMA_SQL.read_text())


def load_staging(con):
    con.execute(
        f"""
        INSERT INTO staging_sales
        SELECT
            InvoiceNo, StockCode, Description, Quantity,
            InvoiceDate, UnitPrice, CustomerID, Country
        FROM read_csv_auto('{RAW_CSV}', header=True)
        """
    )
    n = con.execute("SELECT COUNT(*) FROM staging_sales").fetchone()[0]
    print(f"Loaded {n} rows into staging_sales")


def clean_staging(con):
    # Drop exact duplicate rows
    con.execute(
        """
        CREATE OR REPLACE TABLE staging_sales AS
        SELECT DISTINCT * FROM staging_sales
        """
    )
    # Drop rows with non-positive unit price (bad data) -- keep negative
    # quantities, since those are legitimate cancellations.
    con.execute("DELETE FROM staging_sales WHERE unit_price <= 0")
    n = con.execute("SELECT COUNT(*) FROM staging_sales").fetchone()[0]
    print(f"staging_sales after cleaning: {n} rows")


def build_dim_customer(con):
    con.execute(
        """
        WITH normalized AS (
            SELECT
                COALESCE(NULLIF(customer_id, ''), 'UNKNOWN') AS customer_id,
                country,
                (customer_id = '' OR customer_id IS NULL) AS is_guest
            FROM staging_sales
        ),
        grouped AS (
            SELECT
                customer_id,
                ANY_VALUE(country) AS country,
                ANY_VALUE(is_guest) AS is_guest
            FROM normalized
            GROUP BY customer_id
        )
        INSERT INTO dim_customer
        SELECT
            ROW_NUMBER() OVER (ORDER BY customer_id) AS customer_key,
            customer_id,
            country,
            is_guest
        FROM grouped
        """
    )
    n = con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
    print(f"dim_customer: {n} rows")


def categorize(description: str) -> str:
    if not description:
        return "OTHER"
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in description:
                return category
    return "OTHER"


def build_dim_product(con):
    con.execute("CREATE TEMP TABLE distinct_products AS SELECT DISTINCT stock_code, description FROM staging_sales")
    products = con.execute("SELECT stock_code, description FROM distinct_products").fetchall()

    rows = []
    for i, (stock_code, description) in enumerate(products, start=1):
        category = categorize(description or "")
        rows.append((i, stock_code, description, category))

    con.executemany(
        "INSERT INTO dim_product VALUES (?, ?, ?, ?)", rows
    )
    print(f"dim_product: {len(rows)} rows")


def build_dim_date(con):
    con.execute(
        """
        INSERT INTO dim_date
        SELECT
            CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
            d AS full_date,
            CAST(strftime(d, '%Y') AS INTEGER) AS year,
            CAST(((CAST(strftime(d, '%m') AS INTEGER) - 1) / 3) + 1 AS INTEGER) AS quarter,
            CAST(strftime(d, '%m') AS INTEGER) AS month,
            strftime(d, '%B') AS month_name,
            CAST(strftime(d, '%d') AS INTEGER) AS day,
            CAST(strftime(d, '%u') AS INTEGER) AS day_of_week,
            strftime(d, '%A') AS day_name,
            CAST(strftime(d, '%u') AS INTEGER) IN (6, 7) AS is_weekend
        FROM (
            SELECT UNNEST(generate_series(
                (SELECT MIN(CAST(invoice_date AS DATE)) FROM staging_sales),
                (SELECT MAX(CAST(invoice_date AS DATE)) FROM staging_sales),
                INTERVAL 1 DAY
            )) AS d
        )
        """
    )
    n = con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
    print(f"dim_date: {n} rows")


def build_fact_sales(con):
    con.execute(
        """
        INSERT INTO fact_sales
        SELECT
            ROW_NUMBER() OVER () AS sales_key,
            s.invoice_no,
            CAST(strftime(CAST(s.invoice_date AS DATE), '%Y%m%d') AS INTEGER) AS date_key,
            c.customer_key,
            p.product_key,
            s.quantity,
            s.unit_price,
            ROUND(s.quantity * s.unit_price, 2) AS line_total,
            (s.invoice_no LIKE 'C%') AS is_cancellation
        FROM staging_sales s
        JOIN dim_customer c
          ON COALESCE(NULLIF(s.customer_id, ''), 'UNKNOWN') = c.customer_id
        JOIN dim_product p
          ON s.stock_code = p.stock_code AND s.description = p.description
        """
    )
    n = con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    print(f"fact_sales: {n} rows")


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = duckdb.connect(str(DB_PATH))
    run_schema(con)
    load_staging(con)
    clean_staging(con)
    build_dim_customer(con)
    build_dim_product(con)
    build_dim_date(con)
    build_fact_sales(con)
    con.close()
    print(f"\nWarehouse built at {DB_PATH}")


if __name__ == "__main__":
    main()
