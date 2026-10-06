-- Buildings with damage recorded in at least one environmental inspection, with the schools
-- there now. Each result is point-in-time (see the *_sy columns for the year); a blank means
-- no report in our archive, not a clean result.
SELECT building_id, building_name, address, schools_current,
       asbestos_items_damaged, asbestos_report_sy,
       lead_positive_damaged, lead_survey_sy,
       water_outlets_above_action, water_sample_sy,
       round(fca_fci_pct, 1) AS facility_condition_index_pct
FROM read_parquet('marts/building.parquet')
WHERE building_kind = 'school_building'
  AND n_schools_current > 0
  AND (asbestos_items_damaged > 0 OR lead_positive_damaged > 0 OR water_outlets_above_action > 0)
ORDER BY building_name
LIMIT 50;
