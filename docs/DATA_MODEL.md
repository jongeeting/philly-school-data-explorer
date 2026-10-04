# Philly Schools Data Model

Oct 4, 2026 · @Jon Geeting

## What this is

This is the blueprint for a free, public website about Philadelphia's public schools. Anyone (a parent, a teacher, a reporter, a council member) should be able to look up any school or neighborhood and see the facts: who goes there, how the building is doing, how students are doing, and how that has changed over time.

Everything on it comes from data the School District, the state, the City, and the Census Bureau already publish. That data is scattered across hundreds of files with different codes, dates, and definitions. This project gathers it, links it together, and keeps a record of where every number came from.

Four principles shape the design:

- **Facts, not rankings.** The site shows information and fair comparisons. It never ranks schools best to worst.
- **Neutral by design.** No faction in the education debate should be able to call it theirs. Contested topics get added in pairs, so each side's concerns show up together.
- **Open and checkable.** The code and data are public, so anyone can verify a number or reuse the work.
- **Built to hand off.** It's designed to be cheap and simple to run, so an independent organization can take it over.

"BPN" below refers to Build Philly Now's property research platform, which maps every parcel in the city. The two projects share map and boundary data but are separate, with separate branding.

**How to read this doc.** The first five sections are the overview: what people will see, how it's built, how the data fits together, the hard problems, and next steps. Everything under "Technical reference" is detail for whoever builds it.

## What people will see

Twelve screens, all drawing on the same underlying data. There is no ranking screen; a chart of school results against student poverty shows which schools beat expectations without a leaderboard.

The Phase column is the build order: 1 is the data foundation, 2 the parent-facing tools, 3 trends over time, 4 fair comparisons between schools, 5 the contested topics.

| View | Who it's for | Draws on | Phase |
| --- | --- | --- | --- |
| My schools (address lookup) | Parents | AIS geocoder, assignment zones, catchment flows | 2 |
| School card | Parents, press | Every school-level fact, each with its own "as of" year | 2 |
| Place card (catchment, zone, neighborhood, district) | Parents, officials | Place facts, computed two ways: schools located here and schools its kids attend | 2 |
| Map | Everyone | Parcels, catchments, zones, districts, tracts, buildings, as vector tiles | 2 |
| Compare tool | Advocates, press, staff | The common entity layer; normalizations from the measure dictionary | 3 |
| Trends | Everyone | Long metric tables, with method breaks drawn | 3 |
| Flows | Parents, planners | `catchment_flow` | 2 |
| Facilities and closures tracker | Parents, press, officials | `facility_plan`, `building_condition`, utilization, events | 2 |
| Elected-official report | Council, state legislators, staff | Everything, filtered to a district, printable | 3 |
| Board goals scorecard | Board, press | Goals and Guardrails targets and results | 3 |
| Spending explorer | Advocates, press | `spending` | 4 |
| Methods, dictionary, downloads, changelog | Researchers, skeptics | `measure`, `source`, `correction`, releases | 1 |

What the views require of the data model:

- *A common entity layer.* Every unit (school, catchment, zone, neighborhood, district) has an entity type and ID and uses the same long metric table, so comparison is one query.
- *Aggregation and normalization rules in the measure dictionary.* Each measure says how it rolls up (sum, enrollment-weighted average, not aggregable) and which normalizations apply (per pupil, per capita, percentile, peer-adjusted).
- *Two meanings of a place statistic, both labeled.* "Located here" and "attended by kids who live here" give different answers.
- *Translatable text.* Interface strings and measure names in translation files from the start; the district publishes in about a dozen languages.

## How it's built

Keep the public site static, and make BPN's Postgres a consumer of the data rather than its home. You get the synergy without tying the schools project's survival, or its brand, to BPN's infrastructure.

In plain terms: a set of scripts downloads the public files whenever they're updated, cleans and links them, and publishes the result two ways, as downloadable data files and as a fast, simple website. There is no server or database to keep running.

**Why not Postgres on Render as the core**

- *Handoff.* The goal is a host org you hand this to. A static site plus files costs close to nothing and keeps working if nobody touches it for a year. A running server and database cost money every month, need credentials and upgrades, and break quietly when neglected.
- *Update rhythm.* School data changes a few times a year. A live database earns its keep when data changes daily or users write to it; neither is true here at launch.
- *Neutrality.* Hosted inside BPN's stack, the site reads as a BPN product. That's the faction problem we've been designing around.
- *Openness.* Parquet files in a public release can be opened by any volunteer, journalist, or researcher with no account. A database needs an API or a dump.

**Where Postgres does fit**

- *As a load target for BPN.* One script loads each release into BPN's Postgres (with PostGIS), so parcels in the property platform carry their school zone, catchment, and school facts. Same IDs, same geography, separate products.
- *Later, if the site needs writes.* Saved comparisons, user accounts, alerts, or a public API with high traffic would justify a database. Postgres on Render is a sensible choice then, and the files make the migration easy.

**The recommended split**

| Layer | Choice | Why |
| --- | --- | --- |
| Pipeline | Python plus DuckDB, run by GitHub Actions | Free, reproducible, runs on a laptop |
| Source of truth | Parquet and GeoParquet in versioned GitHub releases | Open, citable, no server |
| Map tiles | PMTiles (parcels, catchments, zones, districts, tracts) on static hosting | Handles about 580,000 parcels with no tile server |
| Website | Static build (Observable Framework, or BPN's frontend framework if you'd rather share skills), MapLibre for maps | Cheap, fast, survives neglect |
| In-browser queries | DuckDB-WASM for the compare tool | Slicing without a backend |
| Address lookup | City AIS geocoder, then point-in-polygon in the browser | No server of our own |
| BPN integration | Release loaded into BPN Postgres/PostGIS by script | Shared IDs and geography, separate brands |
| Hosting | Netlify, Cloudflare Pages, or GitHub Pages | Free or nearly free tiers |

One caution on the shared geography: whichever project owns the parcel-to-zone join, the other should consume its release, not re-derive it. Two copies of the same join drift apart.

## How the data fits together

&#91;embedded content: core tables · three hubs, two bridges, facts below\]

The school ID is the hub. Places reach schools through `catchment_flow`, buildings reach schools through `school_building`, and the building's parcel number is the bridge to the property platform.

Key terms used throughout:

- **School:** a program with its own district code. One building can hold more than one school, and schools move between buildings.
- **Catchment:** the area assigned to a neighborhood school. Elementary, middle, and high schools each have their own.
- **Assignment zone:** an area where every address is assigned to the same set of schools from kindergarten through 12th grade. Philadelphia has 160.
- **Catchment flow:** where children who live in a catchment actually enroll. Citywide, only 38% attend their own catchment school.
- **Census tract:** a small area the Census Bureau reports neighborhood statistics for, such as income and education levels.
- **Measure:** any statistic the site shows (attendance, test scores, enrollment), each with a written definition and source.

## The hard problems

Gathering the data is the easy part. The hard part is keeping it honest over time: schools change names and buildings, boundaries move, and definitions shift. These decisions are cheap to make now and expensive to fix once a public site depends on them.

The five that matter most:

1. **Schools change identity.** They open, close, merge, rename, convert to charter, change grade spans, and move buildings. We need our own stable school ID with dated links to the district and state codes, not a raw district code as the key.
2. **Everything is versioned in time.** Boundaries, grade spans, names, and governance each have a valid-from and valid-to. A 2019 score has to join to the 2019 catchment, not today's.
3. **Measures need a dictionary.** "Regular attendance" became "persistent attendance" in 2021-22; growth and proficiency mean different things. Every number should point to a measure definition with its source, denominator, and known breaks.
4. **Missing is data.** Suppressed ("IS"), waived, not applicable, and copied-forward (2019-20) are different facts. Store the reason, never just a blank.
5. **Geography crosswalks need population weights.** We joined tracts to catchments by area. Weighting by census-block population is the right fix, and it's the same layer the BPN platform needs.

## Decisions and next steps

**Decisions for you**

- [ ] Repo owner: your account, a new neutral org, or Code for Philly.
- [ ] Neighborhood set for display (OpenDataPhilly's is the default).
- [ ] How far back to build: 2012-13 (district schools only before 2019) or 2017-18 (all sectors, state data).
- [ ] Whether the geography layer is shared with the BPN platform as a common package, or copied.
- [ ] Questions for our School District data contact: code reuse, merge history, and whether they'll review the methods page.

**How this becomes a Claude Code prompt series**

Each phase becomes one prompt that points at this doc and ends with a passing test suite. A rough sequence:

1. *Repo scaffold.* Folder layers, source manifest, download scripts, the design rules as a CONTRIBUTING file, and a test harness.
2. *Identity.* `school`, `school_year_attr`, `school_id_xwalk`, lineage, and corrections, rebuilt from the scripts we already have.
3. *Geography.* Catchments by vintage, assignment zones, `geo_unit`, and population-weighted `geo_xwalk` from census blocks.
4. *Measures.* The `measure` dictionary, breaks, and the `school_metric` and `enrollment` facts, with status codes.
5. *Flows and buildings.* `catchment_flow`, `building`, `school_building`, `building_condition`, `facility_plan`, `school_event`.
6. *Marts.* Wide tables for the parent tool, plus the generated data dictionary page.
7. *Release.* Validation report, version tag, changelog.

Phases 1 to 4 are the foundation; the parent tool can start once phase 6 lands. I'd write each prompt only after the one before it runs, since each build will surface something this plan missed.

## Technical reference

The sections below are the detailed specification for whoever builds the site: when each source is published, every table, the rules each table follows, known gaps, and file storage. They assume some familiarity with data work.

## Release calendar and vintages

Release timing varies by dataset, so the model stores two dates on every fact: the period it describes (`sy` or fiscal year) and the release it came from. Each release is archived as published and never overwritten. The district does revise files: enrollment files for 2014-15 to 2018-19 were reposted in August 2025 under new suppression rules.

Refresh dates as posted on the [district's data page](https://www.philasd.org/research/) (checked Oct 4, 2026) and by the state:

| Dataset | Publisher | Last refreshed | Next promised | Lag after school year |
| --- | --- | --- | --- | --- |
| Master school list | SDP | Oct 2026 | Oct 2027 | Current year |
| Enrollment (Oct 1 count) | SDP | Nov 2025 | Nov 2026 | About 1-2 months |
| PSSA and Keystone | SDP | Feb 2026 | Nov 2026 | About 6-9 months |
| State assessments and Future Ready Index | PDE | Nov 14, 2025 | November | About 6 months |
| Attendance, suspensions, serious incidents (in-year district files) | SDP | May 2026 | Aug 2026 | Several times a year |
| Attendance, suspensions, serious incidents (school files) | SDP | Feb 2026 | Spring 2027 | About 8-9 months |
| Graduation rates | SDP | Feb 2026 | Spring 2027 | About 8 months |
| Star (district interim tests) | SDP | Sep 2025 | Sep 2026 | About 3 months |
| SPREE school reports | SDP | Apr 2026 | Spring 2027 | About 10 months |
| Philly School Experience Survey | SDP | Aug 2026 (preliminary) | Oct 2026 (final) | 3-5 months |
| Catchment flows | SDP | Dec 2025 | Dec 2026 | About 3 months |
| Expenditures | SDP | Jan 2026 | Jan 2027 | About 7 months after fiscal year |
| Employee roster | SDP | Jul 2026 | Oct 2026 | Several times a year; marked preliminary since a new HR system in Jan 2025 |
| Teacher and leader demographics | SDP | Jan 2026 | Jan 2027 | About 7 months |
| Staff vacancies | SDP | May 2025 | **Aug 2025, missed** | Overdue |
| District SPOTlight scorecard | SDP | Apr 2024 | **Spring 2025, missed** | Overdue |
| Pre-K sites | SDP | Apr 2025 | **Spring 2026, missed** | Overdue |
| Youth Risk Behavior Survey | SDP | 2026 | 2028 | Every two years |
| Professional vacancies | PDE | Quarterly collection since 2024-25 | Not stated | Not stated |

Two additions to the entity list follow from this:

- `release`: one row per published file version, with publish date, the promised next date, and what changed. Missed promises become a tracked, low-heat accountability measure of their own.
- `commitment`: one row per published target (Board goals, SPREE targets, facilities plan promises), with baseline, target, deadline, adoption date, and version. When a target moves, the old row stays.

## Entities

Twenty-two tables in four groups, plus the \`release\` and \`commitment\` tables described in the release calendar. "Phase" is the first build phase that needs the table: 1 geography spine, 2 parent tool, 3 trends, 4 fair comparison, 5 contested topics.

**Things (dimensions)**

| Table | Grain | Main sources | Cadence | Phase |
| --- | --- | --- | --- | --- |
| `school` | one row per school or program, ever | SDP master lists, PDE fast facts | yearly | 1 |
| `school_year_attr` | school x year: name, governance, grades served, admission type, operator, network, designations | SDP master lists | yearly | 1 |
| `school_id_xwalk` | school x outside code x valid years (ULCS, AUN-school, NCES, SRC) | built by us | yearly | 1 |
| `building` | one physical building, with OPA parcel number | facilities dashboard, schools parcels layer | rarely | 2 |
| `school_building` | school x building x years (handles co-locations and moves) | master lists, facilities plan | yearly | 2 |
| `operator` | charter management organization or the district | master lists | rarely | 2 |
| `measure` | one row per measure: definition, unit, denominator, direction, source, known breaks | built by us | as needed | 1 |
| `source` | one row per downloaded file: URL, date, hash, license | pipeline | every run | 1 |

**Places (geography)**

| Table | Grain | Main sources | Cadence | Phase |
| --- | --- | --- | --- | --- |
| `catchment` | school x level x boundary year (polygons, 2012-13 on) | SDP catchment shapefiles | yearly | 1 |
| `assignment_zone` | unique K-12 path x boundary year (160 today) | derived from ES layer | yearly | 1 |
| `geo_unit` | one row per polygon of any type: neighborhood, council, state house, state senate, ward, division, planning district, zip, police district, tract, block group, block | city, state, Census | per release | 1 |
| `geo_xwalk` | geo unit x geo unit x weight (area and population) | built by us from census blocks | per release | 1 |

**Facts (measurements)**

| Table | Grain | Main sources | Cadence | Phase |
| --- | --- | --- | --- | --- |
| `enrollment` | school x year x grade x student group | SDP, PDE | yearly, Oct 1 | 2 |
| `catchment_flow` | catchment x enrolled school x year (student counts) | SDP catchment retention | yearly | 2 |
| `school_metric` | school x year x measure x student group (scores, attendance, graduation, survey) | PDE Future Ready, SDP | yearly | 2-3 |
| `cohort_metric` | school x cohort (entry year and grade) x year x measure | SDP graduation, PDE | yearly | 3 |
| `building_condition` | building x assessment year x system (condition, fit, capacity) | facilities dashboard, AHERA reports | per assessment | 2 |
| `spending` | school or district x fiscal year x category x fund | SDP budgets and expenditures, PDE per-pupil | yearly | 4 |
| `area_context` | geo unit x year x census measure | ACS 5-year, decennial | yearly | 4 |

**Events**

| Table | Grain | Main sources | Cadence | Phase |
| --- | --- | --- | --- | --- |
| `school_event` | school x date x event type: opened, closed, merged, renamed, charter conversion, turnaround, grade change, leadership change, charter renewal | master lists, Board resolutions, CSO reports | as they happen | 2 |
| `facility_plan` | building x plan version x recommendation (close, co-locate, modernize, maintain) x target year | facilities master plan | per plan version | 2 |
| `correction` | one row per manual fix, with reason | us | as needed | 1 |

The events table is the piece we hadn't named. It's what the pre/post trend method needs, and it's what turns the 2013 closures and the 2026 plan into before-and-after studies.

## Design rules

Eight rules every table follows. They're written to be pasted into a Claude Code prompt as-is.

1. **Keys.** Each entity gets one minted, permanent ID (`school_id`, `building_id`, `zone_id`). Outside codes (ULCS, AUN plus state school number, NCES, OPA parcel number) live in a crosswalk table with valid-from and valid-to years, never as the primary key.
2. **Time.** One convention: `sy` = the spring year of a school year (2025 = SY 2024-25 = FY2025, July to June). Every row also stores its snapshot date when the source has one (most counts are October 1).
3. **Grain.** Each fact table states its grain in one line, such as "one row per school, year, measure, student group." No table mixes grains.
4. **Long, not wide.** Scores, enrollment, and spending are stored as rows (entity, year, measure, group, value), the way we already built the score table. Wide views are built for the website, not stored.
5. **Status beside value.** Every value has a `status` column: reported, suppressed, waived, not applicable, carried forward, or derived.
6. **Provenance on every row.** `source_id` points to a sources table: publisher, URL, file name, download date, file hash, and license.
7. **Raw is never edited.** Downloads are saved untouched. Every fix (a wrong code, a merged school) is a row in a corrections table with a reason, so the public can audit it.
8. **Derived is labeled.** Anything we compute (a shrunken estimate, a peer residual, a utilization rate) lives in its own tables, tagged with the method version, never mixed into source facts.

## Gaps we haven't considered yet

**Identity and time**

- *Code reuse.* We don't know whether the district ever reassigns a retired ULCS code to a new school. One case already maps a code to two state keys. The minted `school_id` protects us either way, but it's worth asking your contact.
- *Merges and splits.* When two schools merge, does the new one inherit either history? We need a lineage table (predecessor, successor, date, type) so trend lines don't silently restart or blend.
- *Programs vs. buildings vs. schools.* Covered in the entity table, but the hard part is the rules: which one owns enrollment, which owns condition, which closes.
- *Grade span changes.* A K-5 that becomes K-8 isn't comparable year to year on school-wide measures. Store grades served per year and flag the break.

**Meaning**

- *Denominators.* "38% attend their catchment school" depends on whether the base is catchment residents or school enrollment. The district file reports both. Every measure row should name its denominator and carry the count where available.
- *Unit of reporting vs. unit of service.* The state reports some alternative programs under a shared code (the 9999 problem). Those programs need an explicit "not separately measurable" status, not a blended number.
- *Methodology breaks.* COVID, new state tests in 2015, the attendance rename, and any year a catchment boundary moved. A `measure_break` table lets every chart draw the break instead of a misleading line.
- *Out-of-system students.* About 16,000 in cyber and out-of-city charters show up in flow data only. They need placeholder school records so flows add up.

**Geography**

- *Addresses.* The parent tool needs address-to-zone lookup. The City's AIS geocoder returns parcel and coordinates; boundary ties along streets need a rule.
- *Boundary vintages.* Catchments change over time; we have polygons back to 2012-13. Store each vintage, and record which vintage each fact joins to.
- *Neighborhood definitions are contested.* Pick one published set, label the source, and treat it as display only, never as an analysis unit.

**People and privacy**

- *Small cells.* Apply the state's rule (suppress groups under 20) to anything we derive, including flow counts by catchment and grade.
- *Named individuals.* The employee file includes names and pay. Store only aggregates in the public repo, even when teacher data arrives.

**Trust**

- *Validation tests.* Row counts by year, totals that reconcile with district-published figures, codes that resolve. These run on every refresh and fail loudly.
- *Release versions.* Each public data release gets a version and changelog, so a chart cited in a news story can be reproduced later.
- *Licensing per source.* District terms of use, SEDA's agreement, and city open data licenses differ. The sources table records each, and the repo license covers only our code and derived work.

## Storage, layers and tooling

Use files plus DuckDB, not a database server. Everything fits on a laptop, costs nothing to host, and any volunteer can clone the repo and query it.

| Layer | What lives there | Format | In the public repo? |
| --- | --- | --- | --- |
| `raw/` | downloads exactly as published, plus a manifest with URL, date, and hash | original files | No (too big); the manifest and download script are |
| `staging/` | each source cleaned to the design rules, one file per source and year | Parquet, GeoParquet | No; rebuilt by script |
| `core/` | the 22 tables above | Parquet, GeoParquet | Yes, as versioned releases |
| `marts/` | wide tables shaped for the website (one row per school, per zone) | Parquet, GeoJSON, CSV | Yes |
| `derived/` | our computed estimates, tagged by method version | Parquet | Yes, with the methods page |

Other choices:

- *Python plus DuckDB* for all transforms, as already decided. DuckDB reads Parquet directly and handles spatial joins with its spatial extension.
- *dbt is optional.* It adds tests and a browsable data catalog, which helps a future host org, but it's one more tool for a beginner. My sense is to start with plain Python scripts and a test suite, then adopt dbt only if a host org's staff already use it.
- *GitHub releases for data.* Code in the repo, data files attached to tagged releases, so the repo stays small and every release is citable.
- *A data dictionary generated from the `measure` and `source` tables,* published as a page. That page is the main credibility asset.
