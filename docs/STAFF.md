# Staff (agency level)

`staff_lea_profile` and `staff_lea_retention` come from the Pennsylvania Department of Education's aggregate staff files (`psd build-pde-staff`). They are by agency, not by school: a school district or a charter school (each charter is its own agency). Individual staff reports exist on PDE's site, but we do not use them, and school-level turnover is not available from the aggregate files (GAP-027).

**`staff_lea_profile`** (2012-13 to 2025-26, October 1 snapshots): counts of professional personnel, administrators, classroom teachers, coordinators and others by sex; and for full-time staff the average salary, years of service, years in the agency, and education level (1 less than high school to 6 doctorate). Salaries may reflect expired contracts, salaries under $18,500 are excluded from averages, and a person is counted once per category. For Philadelphia City SD the average classroom teacher salary rose from about $71,400 (2012-13) to $86,700 (2025-26), with average years of service near 13 to 14 throughout.

**`staff_lea_retention`**: where one year's classroom teachers were the next year, for the pairs PDE publishes (2015-16 to 2016-17, 2017-18 to 2018-19, 2019-20 to 2020-21, and each pair from 2021-22 on). `sy` is the later year.

**A figure to check before using it.** Philadelphia City SD retained 86.7%, 91.7%, 87.2%, 85.1% and 89.2% of its classroom teachers as teachers in the pairs ending 2017, 2019, 2021, 2023 and 2024, then 69.3% for 2024-25, when 17.7% stayed in the district in another role (2 to 5% in other years) and the starting teacher count was 8,562 (8,083 the year before, 6,977 the next). The following pair is back at 89.9%. This looks like a change in how classroom teachers were coded, not a real exodus; do not publish it as a trend without confirming (GAP-081).

Not yet parsed, though downloaded: professional vacancies (2023-24 on, quarterly from 2024-25), budgeted complement and vacancies (Act 35), and support personnel counts by agency (2015-16 on).
