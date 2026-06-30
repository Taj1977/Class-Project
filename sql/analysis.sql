-- ============================================================
-- sql/analysis.sql
-- Analytical queries against the retail star schema.
-- Each query is labeled with a comment header so it can be
-- copy-pasted individually, or run all at once via scripts/run_analysis.py
-- ============================================================

-- ------------------------------------------------------------
-- 1. Monthly revenue trend (excluding cancellations)
-- ------------------------------------------------------------
-- @name: monthly_revenue
SELECT
    d.year,
    d.month,
    d.month_name,
    ROUND(SUM(f.line_total), 2) AS revenue,
    COUNT(DISTINCT f.invoice_no) AS num_orders
FROM fact_sales f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.is_cancellation = FALSE
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;


-- ------------------------------------------------------------
-- 2. Top 10 products by revenue
-- ------------------------------------------------------------
-- @name: top_products
SELECT
    p.stock_code,
    p.description,
    p.category,
    ROUND(SUM(f.line_total), 2) AS revenue,
    SUM(f.quantity) AS units_sold
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
WHERE f.is_cancellation = FALSE
GROUP BY p.stock_code, p.description, p.category
ORDER BY revenue DESC
LIMIT 10;


-- ------------------------------------------------------------
-- 3. Revenue by product category
-- ------------------------------------------------------------
-- @name: revenue_by_category
SELECT
    p.category,
    ROUND(SUM(f.line_total), 2) AS revenue,
    SUM(f.quantity) AS units_sold,
    COUNT(DISTINCT f.invoice_no) AS num_orders
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
WHERE f.is_cancellation = FALSE
GROUP BY p.category
ORDER BY revenue DESC;


-- ------------------------------------------------------------
-- 4. Revenue and order count by country (top 10)
-- ------------------------------------------------------------
-- @name: revenue_by_country
SELECT
    c.country,
    ROUND(SUM(f.line_total), 2) AS revenue,
    COUNT(DISTINCT f.invoice_no) AS num_orders,
    COUNT(DISTINCT c.customer_key) AS num_customers
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE f.is_cancellation = FALSE
GROUP BY c.country
ORDER BY revenue DESC
LIMIT 10;


-- ------------------------------------------------------------
-- 5. Day-of-week sales pattern
-- ------------------------------------------------------------
-- @name: sales_by_day_of_week
SELECT
    d.day_name,
    d.day_of_week,
    ROUND(SUM(f.line_total), 2) AS revenue,
    COUNT(DISTINCT f.invoice_no) AS num_orders
FROM fact_sales f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.is_cancellation = FALSE
GROUP BY d.day_name, d.day_of_week
ORDER BY d.day_of_week;


-- ------------------------------------------------------------
-- 6. Customer cohort analysis: first purchase month vs.
--    number of customers retained in subsequent months
-- ------------------------------------------------------------
-- @name: customer_cohorts
WITH first_purchase AS (
    SELECT
        f.customer_key,
        MIN(d.full_date) AS first_purchase_date
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    JOIN dim_customer c ON f.customer_key = c.customer_key
    WHERE f.is_cancellation = FALSE AND c.is_guest = FALSE
    GROUP BY f.customer_key
),
cohorts AS (
    SELECT
        customer_key,
        strftime(first_purchase_date, '%Y-%m') AS cohort_month
    FROM first_purchase
),
activity AS (
    SELECT
        f.customer_key,
        strftime(d.full_date, '%Y-%m') AS activity_month
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.is_cancellation = FALSE
    GROUP BY f.customer_key, strftime(d.full_date, '%Y-%m')
)
SELECT
    co.cohort_month,
    a.activity_month,
    COUNT(DISTINCT a.customer_key) AS active_customers
FROM cohorts co
JOIN activity a ON co.customer_key = a.customer_key
WHERE a.activity_month >= co.cohort_month
GROUP BY co.cohort_month, a.activity_month
ORDER BY co.cohort_month, a.activity_month;


-- ------------------------------------------------------------
-- 7. Top customers by lifetime value
-- ------------------------------------------------------------
-- @name: top_customers
SELECT
    c.customer_id,
    c.country,
    ROUND(SUM(f.line_total), 2) AS lifetime_value,
    COUNT(DISTINCT f.invoice_no) AS num_orders
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE f.is_cancellation = FALSE AND c.is_guest = FALSE
GROUP BY c.customer_id, c.country
ORDER BY lifetime_value DESC
LIMIT 10;


-- ------------------------------------------------------------
-- 8. Cancellation rate overview
-- ------------------------------------------------------------
-- @name: cancellation_overview
SELECT
    COUNT(*) FILTER (WHERE is_cancellation) AS cancelled_lines,
    COUNT(*) AS total_lines,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_cancellation) / COUNT(*), 2) AS cancellation_rate_pct
FROM fact_sales;
