-- Share of students with an out-of-school suspension in the federal Civil Rights Data
-- Collection, citywide (district and charter schools), by student group and collection year.
-- Counts and enrollment are summed over schools where both are reported. 2021 (2020-21) was
-- mostly virtual and reads near zero: draw it as a break, not a trend.
WITH m AS (
  SELECT school_id, sy, student_group, measure_id, value
  FROM read_parquet('core/school_metric.parquet')
  WHERE measure_id IN ('crdc_n_oss', 'crdc_enrollment')
    AND status IN ('reported', 'derived') AND value IS NOT NULL
), both_ AS (
  SELECT a.school_id, a.sy, a.student_group, a.value AS suspended, b.value AS enrolled
  FROM m a JOIN m b USING (school_id, sy, student_group)
  WHERE a.measure_id = 'crdc_n_oss' AND b.measure_id = 'crdc_enrollment'
)
SELECT sy, student_group, round(100.0 * sum(suspended) / sum(enrolled), 1) AS pct_suspended,
       count(*) AS schools
FROM both_
WHERE student_group IN ('all', 'black', 'white', 'hispanic', 'idea', 'english_learner')
GROUP BY sy, student_group
ORDER BY student_group, sy;
