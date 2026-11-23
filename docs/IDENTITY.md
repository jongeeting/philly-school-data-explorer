# Identity layer

Tables (built by `uv run psd build-identity`, written to `core/`):

| Table | Grain | Notes |
| --- | --- | --- |
| `school` | one row per school/program (ULCS) | `first_sy_in_data` / `last_sy_in_data` describe our data window, not when a school opened or closed |
| `school_year_attr` | school x sy | name, governance, grades level, admission type, council district, lat/lon; `status` and `source_id` on every row; `location_status` (reported, derived, invalid_in_source, not_reported) and `correction_id` for the lat/lon |
| `school_id_xwalk` | school x outside code x run of years | `ulcs`, `state_key` (AUN-school number), `src_id`, `nces`; `shared_across_schools` flags placeholder state codes (0, 9999) and codes used by several programs |
| `school_event` | school x event | derived from year-to-year changes (governance, name, level, dropped from list); `status = derived` |
| `school_lineage` | predecessor x successor | hand-set links in `corrections/school_lineage.csv`, each with its evidence; never inferred (one link so far: Penn Treaty Middle regrouped into Penn Treaty High School, from Jon Geeting's local knowledge, consistent with the lists, no published document yet) |
| `correction` | one manual fix | every fix to source data is a row here, with old and new value; so far the school locations in `corrections/school_location.csv` |
| `source` | dataset x year | URL, local path, SHA-256, retrieval time, license; blank hash means raw file not yet archived |

`issues.csv` (not a core table) lists things a person should look at.

## School IDs

`school_id` (`sch_00001`, ...) is minted once per ULCS and recorded in `registry/school_id_registry.csv`, which is committed and append-only. A rebuild never renumbers; new codes get the next number. IDs are never reused, even if a school closes.

## Known issues (from the first build, 2018-19 to 2025-26 lists)

- **List coverage changes look like gaps.** The district's "Alternate Schools" category is listed in 2019 and 2026 but mostly omitted 2020-2025 (2 to 4 programs instead of 25 to 28). About 24 schools show a "listing gap" for that reason. Absence from a list is not a closure.
- **Some state keys are shared.** 24 programs share placeholder code 9999, and continuation academies (Stetson, Olney) report under their host school's code, so state data for them is blended.
- **One school changed NCES code:** Vaux High School (`sch_00197`) is 421899007634 in 2019 and 421899007661 from 2020. One ULCS (Boys Latin of Philadelphia Charter School) appears twice in 2025; the first row is kept.
- **GPS points lag address changes.** The lists' GPS Location often stays at a school's old building for one to eight years after its Street Address changes, so the point can be another school's building (Excel Middle Years Academy carried Strawberry Mansion High School's point; KIPP West Philadelphia stayed at 5900 Baltimore Ave, now Motivation High School). The 2026-27 list updated many of them at once, which made it look as if schools jumped in 2027. Each wrong point is fixed by a reviewed row in `corrections/school_location.csv` (44 school-years, 13 schools): replaced with the district's own point for the listed address where one exists, else a Census geocode of it (`location_status = derived`), or withheld when neither is reliable (`invalid_in_source`). The real moves stay: Kensington High School is at the former Meehan Middle School (3001 Ryan Ave) in 2026-27 while asbestos work closes its building, as Holme (2023-24 to fall 2025) and Pollock (2022-23) were before it. `psd build-identity` and `psd validate` fail when a school jumps onto a point another school held the year before and has since left.
- **Not yet answered:** whether the district ever reassigns a retired ULCS to a new school. The registry protects us either way; ask the district contact.

## Status

Built from archived raw files: the 2001-02 to 2016-17 Longitudinal School List, the 2017-18 list, and the 2018-19 to 2026-27 lists. 444 schools, 8,190 school-years, 93 district-reported closures (32 take effect in 2014, the 2013 closure round). All earlier IDs unchanged by each rebuild. **Not releasable** until the district's terms are resolved ([SOURCE_TERMS.md](SOURCE_TERMS.md)).

Notes on the build:

- Vocabulary (`DISTRICT` vs `District`, `ELEMENTARYMIDDLE` vs `Elementary-Middle`) is unified, so the 2017/2018 seam creates no false events.
- Event `sy` is the first school year the change is in effect. `closed` events come from the district's Year Closed field (status `reported`); `no_longer_listed` is a guess from list absence (status `derived`).
- NCES codes damaged in CSVs are repaired from the xlsx sibling where it exists, else bridged only when the nearest earlier and later codes agree. The xwalk `evidence` column says `includes_bridged_years` when a bridged year is inside the run.
- Pre-2019 rows have no AUN or NCES (the longitudinal list lacks them), so they have no `state_key` or `nces` crosswalk rows.

## Next

`school_lineage` (who absorbed a closed school) is deferred. See [DATA_GAPS.md](DATA_GAPS.md).

## The 2012 closure proposal

`school_closure_plan` holds the district's December 2012 closure proposal as reported by the press: 35 schools proposed for closure and 68 closing-to-receiving pairs (`registry/closure_plan_2012.csv`). `receiving_rule` is `named` when one school was named and `either` when several were offered. It records what was proposed, not what happened: 23 of the 35 were dropped from the district's list in the 2013 wave, while 12 (for example Peirce, Taylor, Cooke, Duckrey) were not, and the closures actually voted on March 7, 2013 included schools not in this list. The final resolution is not archived (GAP-038), so `school_lineage` stays empty rather than guessing which school absorbed which (GAP-078). Roosevelt Middle School shows as dropped from the list although the press reported it spared; that needs checking.
