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
