# Test scores, growth, attendance, and graduation

Built by `uv run psd build-scores` from PDE's Future Ready PA Index data files (2017-18 to 2024-25) into `school_metric` (part `future_ready`): one row per school x year x measure x student group, for Philadelphia district and charter schools on one state definition. Measures are defined in [registry/measures.csv](../registry/measures.csv).

Measures: proficiency (ELA, math, science), PVAAS growth scores (ELA, math, science), test participation, grade 3 reading, grade 7 math, regular attendance (to 2020-21), persistent attendance (2021-22 on), chronic absenteeism (2024-25), and four- and five-year graduation. Student groups: all, economically disadvantaged, English learners, students with disabilities, and race and ethnicity groups.

## Status rules

| Source shows | Status |
| --- | --- |
| A number | `reported` |
| IS, Insufficient Sample, Insufficient Testers | `suppressed` |
| Not Applicable, Suppress:Data Does Not Apply | `not_applicable` |
| 2019-20 test results (no spring 2020 tests; the file repeats 2018-19) | `carried_forward` |
| 2024-25 science (waived statewide) | `waived` |
| Program sharing placeholder state code 0 or 9999 | `not_separately_measurable`, value withheld |
| School sharing its state code with its EOP or continuation program | `blended` (the host keeps the number; the program is `not_separately_measurable`) |

## Breaks to draw on any trend

- No 2019-20 tests; 2020-21 had low participation (about 240 of 297 schools report ELA) and no growth scores.
- Regular attendance became persistent attendance in 2021-22, with a different definition. They are separate measures.
- Chronic absenteeism first appears in 2024-25.

## How to read them

Proficiency tracks student poverty closely; growth is fairer to high-poverty schools but noisy for one year. Show them together, with student-group context, and never as a ranking. In 2024-25 the median Philadelphia school had 26.4% of tested students proficient in ELA.

## District PSSA and Keystone (longer history)

`uv run psd build-assessments` loads the district's school files (2009-10 to 2024-25, district schools only) into `core/assessment_result`: one row per school x year x test x subject x grade x student group x performance level, with students tested, count, percent (0 to 100), and status. Grades include `ALL` and `03-08` totals where the district publishes them; never add those to grade rows.

- Uses the "Actual" files (all tested students), not the accountability subset.
- Schools are keyed by SRC ID through 2017-18 and ULCS after; every school maps.
- Matches Future Ready ELA proficiency closely for schools in both (r = 0.996 in 2018-19, 0.995 in 2024-25).
- Breaks: new tests in 2014-15 (grades 3-8 math fell from 46.9% to 17.8% proficient citywide; Reading became ELA); an unexplained 8-point drop in 2011-12; no files for 2019-20 or 2020-21; Keystones from 2012-13.
