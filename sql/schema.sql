-- ============================================================
-- sql/schema.sql
-- Star schema for the Retail Sales Data Warehouse
-- Compatible with DuckDB and PostgreSQL (minor type tweaks only)
-- ============================================================

-- Drop existing objects for a clean re-run
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS staging_sales;

-- ------------------------------------------------------------
-- Staging table: holds the raw, uncleaned data exactly as loaded
-- ------------------------------------------------------------
CREATE TABLE staging_sales (
    invoice_no    VARCHAR,
    stock_code    VARCHAR,
    description   VARCHAR,
    quantity      INTEGER,
    invoice_date  TIMESTAMP,
    unit_price    DOUBLE,
    customer_id   VARCHAR,
    country       VARCHAR
);

-- ------------------------------------------------------------
-- Dimension: Customer
-- ------------------------------------------------------------
CREATE TABLE dim_customer (
    customer_key   INTEGER PRIMARY KEY,   -- surrogate key
    customer_id    VARCHAR,               -- natural/business key (may be 'UNKNOWN')
    country        VARCHAR,
    is_guest       BOOLEAN
);

-- ------------------------------------------------------------
-- Dimension: Product
-- ------------------------------------------------------------
CREATE TABLE dim_product (
    product_key    INTEGER PRIMARY KEY,   -- surrogate key
    stock_code     VARCHAR,               -- natural/business key
    description    VARCHAR,
    category       VARCHAR
);

-- ------------------------------------------------------------
-- Dimension: Date (one row per calendar day in range)
-- ------------------------------------------------------------
CREATE TABLE dim_date (
    date_key       INTEGER PRIMARY KEY,   -- YYYYMMDD
    full_date      DATE,
    year           INTEGER,
    quarter        INTEGER,
    month          INTEGER,
    month_name     VARCHAR,
    day            INTEGER,
    day_of_week    INTEGER,               -- 1 = Monday ... 7 = Sunday
    day_name       VARCHAR,
    is_weekend     BOOLEAN
);

-- ------------------------------------------------------------
-- Fact: Sales (one row per cleaned order line)
-- ------------------------------------------------------------
CREATE TABLE fact_sales (
    sales_key       BIGINT PRIMARY KEY,    -- surrogate key
    invoice_no      VARCHAR,
    date_key        INTEGER REFERENCES dim_date(date_key),
    customer_key    INTEGER REFERENCES dim_customer(customer_key),
    product_key     INTEGER REFERENCES dim_product(product_key),
    quantity        INTEGER,
    unit_price      DOUBLE,
    line_total      DOUBLE,
    is_cancellation BOOLEAN
);
