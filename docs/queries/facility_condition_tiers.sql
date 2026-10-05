-- Assessed sites by the district's condition tier (2020 assessment cycle).
SELECT CASE WHEN fci_pct < 15 THEN '1. under 15%: minimal capital need'
            WHEN fci_pct < 25 THEN '2. 15-25%: refurbish systems'
            WHEN fci_pct < 45 THEN '3. 25-45%: replace systems'
            WHEN fci_pct < 60 THEN '4. 45-60%: consider major renovation'
            ELSE '5. over 60%: consider closing or replacement' END AS tier,
       count(*) AS sites,
       round(sum(repair_cost) / 1e6) AS repair_cost_millions
FROM read_parquet('core/facility_condition.parquet')
GROUP BY tier
ORDER BY tier;
