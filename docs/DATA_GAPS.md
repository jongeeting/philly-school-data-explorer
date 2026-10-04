# Data gaps

What is missing, why, and how we plan to close it. Generated from [sources/gaps.csv](../sources/gaps.csv); edit the CSV, then run `uv run psd gaps`.

**30 unresolved** of 30 tracked (14 high priority).

**Kinds of gap**

- `not-in-any-list`: no source we know of records it
- `not-collected-by-district`: the publisher does not collect or publish it, or changed it
- `not-public`: exists or likely exists, but is not public
- `not-yet-ingested`: public, but we have not captured or loaded it yet
- `legal`: terms or permission issue
- `decision`: needs a project decision
- `unknown`: we do not know yet

Statuses: `open`, `in-progress`, `blocked`, `closed`. Closed gaps stay in the CSV with a note.

## Schools and identity

| ID | Gap | Kind | Priority | Status | How to close |
| --- | --- | --- | --- | --- | --- |
| GAP-001 | School lineage (predecessor/successor) table is empty: no source says which school absorbed a closed school's students *(Longitudinal list has Year Closed but no receiving school)* | `not-in-any-list` | high | open | Derive candidates from 2012-13 vs 2013-14 catchments and enrollment; confirm against Board resolutions; label evidence level (stated, geographic, enrollment) |
| GAP-002 | Longitudinal School List (2001-02 to 2016-17, 5,070 rows, ULCS keyed) is archived but not staged, so schools before 2019 have no school_id *(298 of its ~398 ULCS already in registry)* | `not-yet-ingested` | high | open | Stage it; mint IDs for pre-2019 schools; replace derived closure events with Year Closed |
| GAP-007 | 24 alternative or contracted programs share state code 9999 (plus one with 0); continuation academies report under a host school's code *(state_key flagged shared_across_schools)* | `not-collected-by-district` | high | open | Mark state measures 'not separately measurable'; use district files where they exist |
| GAP-003 | 2017-18 master list (xlsx, different layout) not staged | `not-yet-ingested` | medium | open | Write a loader for its layout |
| GAP-004 | NCES codes lost to scientific notation in the CSV lists for 2024, 2026, 2027 (984 of 2,793 staged rows have none) *(Raw bytes are intact in raw/; this is our loader's choice)* | `not-yet-ingested` | medium | open | Read NCES from the XLSX versions of those lists when the CSV is damaged |
| GAP-006 | District master lists omit most Alternate Schools in 2020-2025 (2 to 4 programs vs 25 to 28 in 2019 and 2026) *(Shown as listing-gap issues, never as closures)* | `not-collected-by-district` | medium | open | Ask the district why coverage changed; cross-check with enrollment files |
| GAP-008 | Unknown whether the district ever reassigns a retired ULCS code to a new school *(Minted school_id protects us either way)* | `unknown` | medium | open | Ask the district; add a check once the longitudinal list is staged |
| GAP-009 | Closure and opening dates come only from list presence; real-world dates are not recorded *(Current school_event rows are status=derived)* | `not-collected-by-district` | medium | open | Use Year Opened/Closed (longitudinal list) and Board resolutions |
| GAP-005 | Missing SRC school IDs (39 staged rows) | `not-collected-by-district` | low | open | Check which programs; fill from other years or ask the district |

## Geography

| ID | Gap | Kind | Priority | Status | How to close |
| --- | --- | --- | --- | --- | --- |
| GAP-010 | Catchments for 2012-13 through 2024-25 not downloaded (cataloged, about 20 MB) | `not-yet-ingested` | high | open | psd fetch --source sdp_catchments |
| GAP-013 | No building table or school-to-building link; no OPA parcel numbers on schools *(Shared geography with BPN is a pending decision)* | `not-yet-ingested` | high | open | Build from facilities dashboard and the City schools layer; join to parcels |
| GAP-011 | Census-to-catchment crosswalk is area-weighted only; population-weighted (census block) version not built *(Prototype used tract area weights)* | `not-yet-ingested` | medium | open | Build from decennial census blocks |
| GAP-012 | Neighborhood set for display not chosen | `decision` | low | open | Decide (OpenDataPhilly set is the default) |

## Measures and facts

| ID | Gap | Kind | Priority | Status | How to close |
| --- | --- | --- | --- | --- | --- |
| GAP-014 | Enrollment files (2009-10 on) cataloged but not downloaded; charters included only from 2019-20 | `not-yet-ingested` | high | open | Fetch and stage; note pre-2019 sector coverage |
| GAP-016 | Prototype score files (PDE Future Ready 2017-18 to 2024-25, School Fast Facts) are not archived here; prototype scripts cannot rerun *(Findings are in docs/FINDINGS_2026-10-03.md)* | `not-yet-ingested` | high | open | Add PDE sources to the file catalog and archive with hashes |
| GAP-018 | Charter coverage is uneven: district PSSA, attendance, and employee files exclude charters; SPREE gives charters improvement labels only in 2024-25 | `not-collected-by-district` | high | open | Use PDE Future Ready for cross-sector measures; label sector coverage on every measure |
| GAP-019 | Measure dictionary and method breaks not written (attendance renamed 'persistent' in 2021-22; framework changes) | `not-yet-ingested` | high | open | Phase 4 of the data model |
| GAP-015 | Catchment retention (flows) not ingested; roughly 16,000 students in cyber and out-of-city charters appear only in flows | `not-yet-ingested` | medium | open | Add placeholder school records for out-of-system destinations so flows sum |
| GAP-017 | No 2020 state test results (state file repeats 2019); 2021 low participation and no growth scores; science waived in 2025 *(Usable test years: 2018, 2019, 2022-2025)* | `not-collected-by-district` | medium | open | Record as measure breaks with status codes; never interpolate |
| GAP-020 | Student groups under 20 are suppressed at source; enrollment files for 2014-15 to 2018-19 were reposted Aug 2025 under new suppression rules | `not-collected-by-district` | medium | open | Keep status codes; archive both versions of reposted files |

## District operations and buildings

| ID | Gap | Kind | Priority | Status | How to close |
| --- | --- | --- | --- | --- | --- |
| GAP-021 | Daily canceled or late bus list: no public history, and we have not started capturing it *(History not captured is gone)* | `not-public` | high | open | Scrape daily with psd snapshot via a scheduled job; needs the exact page URL |
| GAP-022 | Facilities data dashboard and master plan: no snapshots archived; an earlier building-conditions site went offline in 2024 *(Chalkbeat reported shifting capacity figures)* | `not-yet-ingested` | high | open | Locate dashboard data endpoints; snapshot every release |
| GAP-024 | Maintenance work orders, bus on-time history, substitute fill rates, and IEP evaluation timeliness are not public *(Operations is the least covered area)* | `not-public` | high | open | Ask the district what exists internally; consider a data request |
| GAP-023 | AHERA asbestos and lead reports are likely PDFs, not structured | `not-yet-ingested` | medium | open | Download, hash, extract room-level results |
| GAP-025 | Staff vacancies (due Aug 2025), SPOTlight scorecard (due spring 2025), and Pre-K sites (due spring 2026) are past the district's promised refresh dates *(Per district data page, checked 2026-10-04)* | `not-collected-by-district` | medium | open | Track missed promises in the release table |
| GAP-026 | Goals and Guardrails results are PDFs, with targets reset in April 2024 | `not-yet-ingested` | medium | open | Extract per-report tables; version targets in the commitment table |

## Workforce

| ID | Gap | Kind | Priority | Status | How to close |
| --- | --- | --- | --- | --- | --- |
| GAP-027 | Teacher-level and school-level turnover requires the PDE staff files, which are not cataloged or downloaded *(Individual teacher data is deliberately excluded)* | `not-yet-ingested` | medium | open | Add PDE personnel files; aggregate to school level only |

## Legal and licensing

| ID | Gap | Kind | Priority | Status | How to close |
| --- | --- | --- | --- | --- | --- |
| GAP-028 | District Terms of Use restrict copying and limit use to governmental, accountability, and evaluative purposes; OpenDataPhilly lists the license as unspecified *(Nothing is released until resolved)* | `legal` | high | blocked | Obtain written permission or a data-sharing agreement; see docs/SOURCE_TERMS.md |
| GAP-029 | District-derived tables already sit in the public repo under prototype/data/ | `legal` | high | open | Decide: leave, remove from current tree, or scrub history (force-push needs owner approval) |
| GAP-030 | Terms for PDE, Future Ready, SEDA, and City datasets not yet checked *(SEDA is under a data use agreement)* | `unknown` | medium | open | Read each publisher's terms; record in sources/manifest.csv |
