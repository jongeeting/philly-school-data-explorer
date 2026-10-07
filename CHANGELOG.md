# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/). Versions are for the data release; a column rename or removal is a major version with an entry here. School and building IDs are permanent and never reused.

## [0.2.0] - 2026-10-07

### Added

- **School finance (state).** The Pennsylvania Annual Financial Report for 779 agencies (500 school districts, 209 charter schools, 68 career and technology centers), 2015-16 to 2024-25: revenue, expenditures by function and object, charter tuition paid, instruction expense, fund balance, with `marts/district_finance` wide by agency and year. Enrollment by agency (charters included) is the base for per-pupil figures.
- **Adequacy.** The 2007 costing-out study, the 2023 Kelly analysis, and the 2024 Basic Education Funding Commission calculation, side by side in `marts/adequacy_compare`, with the enacted adequacy and tax equity supplements (Ready to Learn allocations).
- **School budgets.** The district's School Budget Allotment Detail, purchase summaries, and position lines for each school, FY16 to FY27 (budgets, not actual spending).
- **School-level per-pupil spending.** The state's ESSA report by building, 2018-19 to 2023-24, charters included, linked to `school_id`.
- **Staff (by agency).** Staff profile (2012-13 to 2025-26) and classroom teacher retention. The 2024-25 Philadelphia figure is flagged as a likely coding change, not an exodus.
- **Places.** Council districts, PA House and Senate districts, wards, ZIP codes, police districts, and planning districts.
- **Closures.** The December 2012 closure proposal as a plan, observed enrollment change around the 2013 closures (not lineage), one evidenced lineage link (Penn Treaty Middle), and open questions for journalists and researchers.
- **Coverage.** `marts/measure_coverage` and `docs/COVERAGE.md` label which sectors (district, charter) each measure covers.
- **Tooling.** `psd snapshot-buses` archives the daily canceled and late bus lists, which have no public history.

### Known limits

- School budgets are planned amounts; actual spending by school is not published. The Board-adopted district operating budget and capital program budget are not loaded.
- Per-pupil spending by building is not comparable between district schools and charters (see `docs/FINANCE.md`).
- School-level teacher turnover is deferred; staff vacancies, Act 35 complement, and support personnel files are downloaded but not parsed.
- Debt, local tax files, and finance years before 2014-15 are not loaded.

## [0.1.0] - 2026-10-06

First public data release (a release candidate: the structure is stable, coverage will grow). Zenodo DOI (all versions): 10.5281/zenodo.23189127.

### Added

- **Identity.** 444 schools on the district's lists (2002 to 2027) with permanent `school_id`, a dated crosswalk of district, state, and federal codes, and 50 placeholder records for programs that appear only in state data.
- **Places.** Catchments (2012-13 to 2024-25), assignment zones, a population-weighted crosswalk to Census tracts, schools linked to City parcels (OPA), and neighborhood context from the American Community Survey with margins of error.
- **Students.** Enrollment (October 1 counts, 2010 to 2026) and where students live relative to their catchment (2016-17 to 2025-26).
- **Outcomes.** Future Ready PA Index scores, growth, attendance, graduation (2017-18 to 2024-25); district PSSA and Keystone results (2009-10 to 2024-25); School Fast Facts demographics; district attendance detail (2013-14 to 2024-25).
- **Discipline.** District out-of-school suspensions and serious incidents, and federal Civil Rights Data Collection discipline by race, disability, and English learner status (2011-12 to 2021-22, every other year).
- **Buildings.** 414 physical buildings with permanent `building_id`, which schools were in which building (2019 to 2027), and the City parcel for 410 of them with a stated confidence.
- **Facility records.** Facility condition assessments (2020 cycle, 76 sites), lead paint (163 schools), drinking-water lead (219 schools), and asbestos management reports (317 buildings).
- **Method.** 79 measures defined in one dictionary; a `status` and `source_id` on every value; peer comparison that is robust to the choice of basis; hard validation checks and reconciliations against independent sources (state vs district enrollment r = 0.999; federal vs district suspensions r = 0.976); example DuckDB queries that run in tests; `datapackage.json`, JSON schemas, and checksums.

### Known limits

- Environmental, condition, and parcel results are point-in-time, not yearly series; the facility assessments cover 76 of about 300 buildings.
- The District's October 1 enrollment count can be affected by how withdrawals are processed (see the note on `enrollment_count`).
- School-to-building history starts in 2019. School lineage (mergers and renames) is not yet inferred.
- 28 environmental files could not be downloaded; pre-2023 asbestos reports use an older layout and are read where they parse.
- 69 open gaps are tracked in `docs/DATA_GAPS.md`, with questions for the district in `docs/DISTRICT_QUESTIONS.md`.

### Terms

Our compilation is CC BY 4.0. The data come from the School District of Philadelphia, the Pennsylvania Department of Education, the U.S. Department of Education, the U.S. Census Bureau, and the City of Philadelphia, and remain subject to their terms (see `docs/SOURCE_TERMS.md`).
