# Suspensions and serious incidents

`uv run psd build-discipline` loads both from the district's files (district schools only). They are published together, under one frame ("safe and fair schools"), so neither reads as one side's story.

**Out-of-school suspensions** (`school_metric`, 2013-14 to 2024-25): for each school, year, and group (gender, race and ethnicity, grade), the students with 0, 1, 2, 3, and 4+ suspensions and the student base. Counts always add up to the base. No disability or English learner groups are published.

- Share of students with any suspension: 11.4% (2013-14), 6.4% (2018-19), about 6% since 2021-22 (5.9% in 2024-25). 2019-20 ends with the March 2020 closure and 2020-21 was mostly virtual (0.0%): draw both as breaks.
- 2024-25 by group: Black 9.2%, multiracial 5.3%, Hispanic 4.5%, White 2.4%, Asian 1.2%; male 6.7%, female 4.8%.

**Serious incidents** (`school_incident` by type, and `sdp_serious_incidents_total` in `school_metric`, 2012-13 to 2024-25): counts as published. Types changed in 2016-17 (fine-grained types before, grouped categories after); `incident_type_scheme` marks the scheme and types are never mapped across it. Counts include non-violent categories (accidents, investigations, amnesty box) and are not rates. Totals are about 5,200 to 6,000 a year recently; 2012-13 reports 15,770, unexplained so far.

## Federal Civil Rights Data Collection (CRDC)

`uv run psd build-crdc` adds the U.S. Department of Education's school-level discipline data (district and charter) for 2015-16, 2017-18, 2020-21, and 2021-22: students with one or more out-of-school suspensions, in-school suspensions, expulsions, referrals to law enforcement, and school-related arrests, with enrollment for each group. Unlike the district files, it breaks discipline out by disability (IDEA and Section 504) and English learner status, which completes the paired release.

How groups are built: the CRDC reports students without disabilities, IDEA students, and Section 504-only students separately and disjointly, so all-student totals add the three; race groups add without-disability and IDEA students (504 counts are not broken out by race). In every collection the race groups plus Section 504 add exactly to the total. OCR rounds counts and suppresses small cells; joined by NCES ID.

Checks: for district schools the CRDC and district suspension counts agree school by school (r = 0.994 to 1.000), though CRDC totals run lower in some years (6% in 2015-16, 14% in 2017-18, about equal in 2021-22), so the two sources use somewhat different counting rules.

Facts (share of students with an out-of-school suspension):

| | 2015-16 | 2017-18 | 2021-22 |
| --- | --- | --- | --- |
| All students | 12.4% | 8.7% | 6.3% |
| IDEA (disability) | 19.6% | 14.2% | 9.1% |
| Section 504 | 12.1% | 8.9% | 7.1% |
| Without disabilities | 11.2% | 7.7% | 7.1% |
| English learners | 7.9% | 4.3% | 3.4% |
| Black | 16.8% | 12.5% | 8.7% |
| White | 4.7% | 2.6% | 2.6% |

Referrals to law enforcement fell from 6,834 students (35.6 per 1,000) in 2015-16 to 3,844 (21.6 per 1,000) in 2021-22; school-related arrests from 407 to 189; expulsions from 367 to 33. In 2021-22, referrals ran 37.7 per 1,000 for IDEA students, 29.4 for Black students, and 9.7 for White students. 2020-21 was mostly virtual and is near zero.

CRDC usage agreement: never link these data with individually identifiable data. 2011-12 and 2013-14 collections are archived but not loaded.
