-- One school's enrollment, test results, and attendance by school year (Stephen Decatur School).
-- Years differ by measure; blank means no reported value that year.
SELECT sy, name, enrollment_count, pct_proficient_ela, pct_proficient_math,
       pct_persistent_attendance, sdp_pct_oss_0 AS pct_students_with_no_suspension
FROM read_parquet('marts/school_year.parquet')
WHERE school_id = 'sch_00323'
ORDER BY sy;
