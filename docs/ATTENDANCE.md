# Attendance

Two sources, kept as separate measures:

| Source | Measures | Years | Schools |
| --- | --- | --- | --- |
| District (`uv run psd build-attendance`) | students attending 95%+ of days; 90%+ of days; counts and attendance base; average daily attendance. By gender, race and ethnicity, and grade (`grade_K` to `grade_12`) | 95%+ and ADA 2013-14 on; 90%+ 2020-21 on | district schools |
| State, Future Ready (`build-scores`) | regular attendance (to 2020-21), persistent attendance (2021-22 on), chronic absenteeism (2024-25) | 2017-18 on | district and charter |

Citywide in district schools (recomputed from counts): 37% to 47% of students attended 95%+ of days from 2013-14 to 2018-19. In 2024-25, 62.3% attended 90%+ of days, so about 38% were chronically absent (up from 57.9% attending 90%+ in 2021-22).

Breaks: 2019-20 counts in-person days only until the March 2020 closure, and 2020-21 was mostly virtual; both show inflated attendance (55.6% and 57.5% at 95%+) and should be drawn as breaks, never as a trend.

How the two sources relate: the state's persistent attendance tracks the district's 90%+ measure within about 1 point (r = 0.92 to 0.95) from 2022-23 on, but runs about 11.5 points higher in 2020-21 and 2021-22, which suggests a change in definition or student base those years (see DATA_GAPS.md).
