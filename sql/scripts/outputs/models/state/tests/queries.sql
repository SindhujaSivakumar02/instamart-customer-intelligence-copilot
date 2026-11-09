-- Q1: Customers with high-value completed orders
SELECT customer_id, SUM(CAST(order_amount AS REAL)) AS total_spend
FROM orders
WHERE lower(status) = 'completed'
  AND CAST(order_amount AS REAL) > 500
GROUP BY customer_id
HAVING SUM(CAST(order_amount AS REAL)) > 8000
ORDER BY total_spend DESC;

-- Q2: Revenue by city and product category
SELECT c.city, p.category,
       SUM(CAST(o.order_amount AS REAL)) AS revenue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN products p ON o.product_id = p.product_id
WHERE lower(o.status) = 'completed'
GROUP BY c.city, p.category
ORDER BY c.city, revenue DESC;

-- Q3: Products priced above average
SELECT product_id, product_name, price_inr
FROM products
WHERE CAST(price_inr AS REAL) >
      (SELECT AVG(CAST(price_inr AS REAL)) FROM products);

-- Q4: Customers with no completed orders
SELECT c.customer_id, c.city
FROM customers c
WHERE NOT EXISTS (
    SELECT 1 FROM orders o
    WHERE o.customer_id = c.customer_id
      AND lower(o.status) = 'completed'
);

-- Q5: Customer order totals using a CTE
WITH customer_totals AS (
    SELECT customer_id,
           SUM(CAST(order_amount AS REAL)) AS total_spend
    FROM orders
    WHERE lower(status) = 'completed'
    GROUP BY customer_id
)
SELECT COUNT(*) AS customer_count,
       AVG(total_spend) AS average_spend
FROM customer_totals;

-- Q6: Ranking customers within each city
WITH customer_totals AS (
    SELECT c.city, o.customer_id,
           SUM(CAST(o.order_amount AS REAL)) AS total_spend
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE lower(o.status) = 'completed'
    GROUP BY c.city, o.customer_id
)
SELECT city, customer_id, total_spend,
       RANK() OVER (PARTITION BY city ORDER BY total_spend DESC) AS rank_value,
       DENSE_RANK() OVER (PARTITION BY city ORDER BY total_spend DESC) AS dense_rank_value,
       ROW_NUMBER() OVER (PARTITION BY city ORDER BY total_spend DESC) AS row_number_value
FROM customer_totals
ORDER BY city, rank_value;

-- Q7: Daily running revenue
WITH daily_revenue AS (
    SELECT substr(order_ts, 1, 10) AS order_date,
           SUM(CAST(order_amount AS REAL)) AS revenue
    FROM orders
    WHERE lower(status) = 'completed'
    GROUP BY substr(order_ts, 1, 10)
)
SELECT order_date, revenue,
       SUM(revenue) OVER (ORDER BY order_date) AS running_total
FROM daily_revenue
ORDER BY order_date;