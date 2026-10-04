# Identity layer

Tables (built by `uv run psd build-identity`, written to `core/`):

| Table | Grain | Notes |
| --- | --- | --- |
| `school` | one row per school/program (ULCS) | `first_sy_in_data` / `last_sy_in_data` describe our data window, not when a school opened or closed |
| `school_year_attr` | school x sy | name, governance, grades level, admission type, council district, lat/lon; `status` and `source_id` on every row |
| `school_id_xwalk` | school x outside code x run of years | `ulcs`, `state_key` (AUN-school number), `src_id`, `nces`; `shared_across_schools` flags placeholder state codes (0, 9999) and codes used by several programs |
| `school_event` | school x event | derived from year-to-year changes (governance, name, level, dropped from list); `status = derived` |
| `school_lineage` | predecessor x successor | empty until sourced from the 2017 Longitudinal School List and Board resolutions; never inferred |
| `correction` | one manual fix | empty; every fix to source data is a row here |
| `source` | dataset x year | URL, local path, SHA-256, retrieval time, license; blank hash means raw file not yet archived |

`issues.csv` (not a core table) lists things a person should look at.

## School IDs

`school_id` (`sch_00001`, ...) is minted once per ULCS and recorded in `registry/school_id_registry.csv`, which is committed and append-only. A rebuild never renumbers; new codes get the next number. IDs are never reused, even if a school closes.

## Known issues (from the first build, 2018-19 to 2025-26 lists)

- **List coverage changes look like gaps.** The district's "Alternate Schools" category is listed in 2019 and 2026 but mostly omitted 2020-2025 (2 to 4 programs instead of 25 to 28). About 24 schools show a "listing gap" for that reason. Absence from a list is not a closure.
- **Some state keys are shared.** 24 programs share placeholder code 9999, and continuation academies (Stetson, Olney) report under their host school's code, so state data for them is blended.
- **One school changed NCES code:** Vaux High School (`sch_00197`) is 421899007634 in 2019 and 421899007661 from 2020. One ULCS (Boys Latin of Philadelphia Charter School) appears twice in 2025; the first row is kept.
- **Not yet answered:** whether the district ever reassigns a retired ULCS to a new school. The registry protects us either way; ask the district contact.

## Next

Rebuild from archived raw files (`psd fetch`) instead of prototype output, add the 2026-27 list, and derive lineage from the Longitudinal School List.
