-- Schools with recorded damage, by governance. Point-in-time records from each school's
-- latest inspection (mostly 2025-26); asbestos damage counts every confirmed or assumed
-- material with damage, so compare the share of schools, not raw item counts. Coverage differs
-- sharply by governance (the district posts few charter reports), so read the first column of
-- each pair before the second.
SELECT governance,
       count(*) AS schools_listed,
       count(lead_paint_positive_damaged) AS with_lead_assessment,
       count_if(lead_paint_positive_damaged > 0) AS lead_damage_recorded,
       count(asbestos_items_damaged) AS with_asbestos_report,
       count_if(asbestos_items_damaged > 0) AS asbestos_damage_recorded
FROM read_parquet('marts/school_profile.parquet')
WHERE record_kind = 'school' AND listed_in_latest_year
GROUP BY governance
ORDER BY schools_listed DESC;
