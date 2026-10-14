-- Noon phones: SQL questions
-- Table: noon_phones (made by ingest/ingest.py)
-- Run these in pgAdmin: right-click the noon database > Query Tool.


-- 0. A view is a saved query. This one gives us smartphones only,
--    because feature phones (Nokia 105, ...) are a different kind of product.
--    The 3 phones with no category are smartphones, so we keep NULL too.
CREATE OR REPLACE VIEW smartphones AS
SELECT *
FROM noon_phones
WHERE category <> 'Feature Phones' OR category IS NULL;


-- Q1. How many phones does each brand have, and what do they cost?
-- GROUP BY puts the phones of each brand in one group,
-- then COUNT, AVG, MIN and MAX are calculated for each group.
SELECT brand,
       COUNT(*)         AS phones,
       ROUND(AVG(price)) AS avg_price,
       MIN(price)       AS cheapest,
       MAX(price)       AS most_expensive
FROM smartphones
GROUP BY brand
ORDER BY phones DESC;


-- Q2. How many phones are on discount, and which discounts are the biggest?
-- old_price is empty (NULL) when there is no discount.

-- Q2a. How many are on discount?
SELECT COUNT(*)         AS phones,
       COUNT(old_price) AS on_discount      -- COUNT(column) skips NULL values
FROM smartphones;

-- Q2b. The 10 biggest discounts
SELECT phone,
       old_price,
       price,
       ROUND(100 * (old_price - price) / old_price) AS discount_percent
FROM smartphones
WHERE old_price IS NOT NULL
ORDER BY discount_percent DESC
LIMIT 10;


-- Q3. Which phones are rated best?
-- A rating from 3 people is not reliable, so we only look at phones with 100+ ratings.
-- (The same phone can show up twice because each colour is a separate listing.)
SELECT phone, rating, rating_count, price
FROM smartphones
WHERE rating_count >= 100
ORDER BY rating DESC, rating_count DESC
LIMIT 10;


-- Q4. Is a phone sold by noon different from one sold by another store?
-- CASE turns every seller into one of two groups: 'noon' or 'other seller'.
-- The delivery part counts the phones with "Tomorrow" delivery and turns it into a percentage.
SELECT CASE WHEN vendor = 'noon' THEN 'noon' ELSE 'other seller' END AS seller,
       COUNT(*)                                                       AS phones,
       ROUND(AVG(price))                                              AS avg_price,
       ROUND(100.0 * SUM(CASE WHEN delivery = 'Tomorrow' THEN 1 ELSE 0 END) / COUNT(*)) AS pct_next_day
FROM smartphones
WHERE vendor IS NOT NULL
GROUP BY seller;
