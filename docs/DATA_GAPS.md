# Data gaps

What is missing, why, and how we plan to close it. Generated from [sources/gaps.csv](../sources/gaps.csv); edit the CSV, then run `uv run psd gaps`.

**41 unresolved** of 51 tracked (11 high priority).

**Kinds of gap**

- `not-in-any-list`: no source we know of records it
- `not-collected-by-district`: the publisher does not collect or publish it, or changed it
- `not-public`: exists or likely exists, but is not public
- `not-yet-ingested`: public, but we have not captured or loaded it yet
- `legal`: terms or permission issue
- `decision`: needs a project decision
- `unknown`: we do not know yet

Statuses: `open`, `in-progress`, `blocked`, `closed`. Closed gaps stay in the CSV with a note.

Owner: who can close it (`us`, `district`, `state`, `other`, or `owner decision`). Open questions for the district are collected in [DISTRICT_QUESTIONS.md](DISTRICT_QUESTIONS.md).

## Schools and identity

| ID | Gap | Kind | Priority | Status | Owner | How to close |
| --- | --- | --- | --- | --- | --- | --- |
| GAP-001 | School lineage (predecessor/successor) table is empty: no source says which school absorbed a closed school's students *(Longitudinal list has Year Closed but no receiving school; inferred candidates deferred by owner decision)* | `not-in-any-list` | high | open | district | Derive candidates from 2012-13 vs 2013-14 catchments and enrollment; confirm against Board resolutions; label evidence level (stated, geographic, enrollment) |
| GAP-002 | Longitudinal School List (2001-02 to 2016-17, 5,070 rows, ULCS keyed) is archived but not staged, so schools before 2019 have no school_id *(Staged 2026-10-04: 444 schools, 2002-2027; 93 district-reported closures)* | `not-yet-ingested` | high | closed | us | Stage it; mint IDs for pre-2019 schools; replace derived closure events with Year Closed |
| GAP-007 | 24 alternative or contracted programs share state code 9999 (plus one with 0); continuation academies report under a host school's code *(state_key flagged shared_across_schools)* | `not-collected-by-district` | high | open | state | Mark state measures 'not separately measurable'; use district files where they exist |
| GAP-003 | 2017-18 master list (xlsx, different layout) not staged *(Staged 2026-10-04 from xlsx; header line breaks normalized)* | `not-yet-ingested` | medium | closed | us | Write a loader for its layout |
| GAP-006 | District master lists omit most Alternate Schools in 2020-2025 (2 to 4 programs vs 25 to 28 in 2019 and 2026) *(Shown as listing-gap issues, never as closures)* | `not-collected-by-district` | medium | open | district | Ask the district why coverage changed; cross-check with enrollment files |
| GAP-008 | Unknown whether the district ever reassigns a retired ULCS code to a new school *(Minted school_id protects us either way)* | `unknown` | medium | open | district | Ask the district; add a check once the longitudinal list is staged |
| GAP-009 | Closure and opening dates come only from list presence; real-world dates are not recorded *(Year Opened and Year Closed now reported (to 2016-17 via longitudinal list); mid-year dates still absent)* | `not-collected-by-district` | medium | open | district | Use Year Opened/Closed (longitudinal list) and Board resolutions |
| GAP-038 | The SRC's March 7, 2013 school closure resolution PDF is not archived (Wayback 404); no minutes found for that meeting | `not-in-any-list` | medium | open | district | Ask the district; check news archives and APPS for copies |
| GAP-004 | NCES codes lost to scientific notation in CSV lists were repaired from xlsx where available or bridged from adjacent years; remaining blanks (about 25 per year in 2018, 2019, 2026, 2027) are programs with no NCES code in the source *(Repair and bridge status is in staging nces_source and xwalk evidence)* | `not-collected-by-district` | low | open | district | Confirm with the district whether alternative programs have NCES codes; bridged values are labeled evidence=includes_bridged_years |
| GAP-005 | Missing SRC school IDs (39 staged rows) | `not-collected-by-district` | low | open | district | Check which programs; fill from other years or ask the district |

## Geography

| ID | Gap | Kind | Priority | Status | Owner | How to close |
| --- | --- | --- | --- | --- | --- | --- |
| GAP-010 | Catchments for 2012-13 through 2024-25 not downloaded (cataloged, about 20 MB) *(Downloaded and built 2026-10-04: 13 boundary years, 2012-13 to 2024-25)* | `not-yet-ingested` | high | closed | us | psd fetch --source sdp_catchments |
| GAP-013 | No building table yet; schools are linked to City parcels (OPA account) by location, but not to buildings *(school_parcel built and reviewed (corrections/school_parcel.csv): 13 replaced, 13 confirmed, 1 unresolved (Cayuga 2018); building table waits on facilities data)* | `not-yet-ingested` | high | in-progress | district | Build from facilities dashboard and the City schools layer; join to parcels |
| GAP-011 | Census-to-catchment crosswalk is area-weighted only; population-weighted (census block) version not built *(geo_xwalk built from 2020 blocks (keyless PL file); see docs/GEOGRAPHY.md)* | `not-yet-ingested` | medium | closed | us | Build from decennial census blocks |
| GAP-031 | Catchment retention (students by catchment and school, SY 2016-17 on) is aggregated by catchment, not neighborhood, and cannot show where students went after the 2013 closures *(No student-level data is public (FERPA))* | `not-collected-by-district` | medium | open | district | Derive neighborhood figures by overlaying catchments on neighborhoods; use Board documents and 2012-13/2013-14 catchments for 2013 |
| GAP-034 | Catchments for SY 2025-26 and 2026-27 are not published (latest is 2024-25) | `not-collected-by-district` | medium | open | district | Watch for the next release; ask the district |
| GAP-035 | Council districts, state legislative districts, wards, ZIP codes, and police districts are not yet in geo_unit | `not-yet-ingested` | medium | open | us | Add from City and state publishers; same block weights |
| GAP-036 | ACS neighborhood context (income, education, homeownership) not loaded; the Census API needs a free key | `not-yet-ingested` | medium | open | us | Load ACS 5-year tables from the keyless Summary File (or the API with a free key); store any key as an env var and GitHub secret, never in recorded URLs |
| GAP-012 | Neighborhood set for display not chosen | `decision` | low | open | us | Decide (OpenDataPhilly set is the default) |

## Measures and facts

| ID | Gap | Kind | Priority | Status | Owner | How to close |
| --- | --- | --- | --- | --- | --- | --- |
| GAP-014 | Enrollment 2009-10 to 2025-26 is loaded (2009-14 workbooks staged 2026-10-04) *(District-only before 2014-15; one program (Ombudsman South Transition, 2010-12) has an SRC ID with no ULCS)* | `not-yet-ingested` | high | closed | us | Fetch and stage; note pre-2019 sector coverage |
| GAP-016 | Prototype score files (PDE Future Ready 2017-18 to 2024-25, School Fast Facts) are not archived here; prototype scripts cannot rerun *(Archived and loaded 2026-10-04: Future Ready 2017-18 to 2024-25 and School Fast Facts (docs/SCORES.md))* | `not-yet-ingested` | high | closed | us | Add PDE sources to the file catalog and archive with hashes |
| GAP-018 | Charter coverage is uneven: district PSSA, attendance, and employee files exclude charters; SPREE gives charters improvement labels only in 2024-25 | `not-collected-by-district` | high | open | state | Use PDE Future Ready for cross-sector measures; label sector coverage on every measure |
| GAP-019 | Measure dictionary and method breaks not written (attendance renamed 'persistent' in 2021-22; framework changes) *(registry/measures.csv has 36 measures (enrollment, flows, neighborhood rollup, Future Ready); district PSSA, Star, SPREE next)* | `not-yet-ingested` | high | in-progress | us | Phase 4 of the data model |
| GAP-015 | Catchment retention (flows) not ingested; roughly 16,000 students in cyber and out-of-city charters appear only in flows *(catchment_flow built 2026-10-04 with 50 placeholder schools (cyber, out-of-city charter, programs, non-public special education))* | `not-yet-ingested` | medium | closed | us | Add placeholder school records for out-of-system destinations so flows sum |
| GAP-017 | No 2020 state test results (state file repeats 2019); 2021 low participation and no growth scores; science waived in 2025 *(Handled with statuses: 2019-20 tests carried_forward, 2024-25 science waived; method breaks recorded in registry/measures.csv)* | `not-collected-by-district` | medium | in-progress | state | Record as measure breaks with status codes; never interpolate |
| GAP-020 | Student groups under 20 are suppressed at source; enrollment files for 2014-15 to 2018-19 were reposted Aug 2025 under new suppression rules | `not-collected-by-district` | medium | open | district | Keep status codes; archive both versions of reposted files |
| GAP-044 | The district's 2010-11 enrollment file reports zero Black, Hispanic, American Indian, and multiracial students in every school; those values are withheld *(corrections/enrollment.csv)* | `not-collected-by-district` | medium | open | district | Ask the district for a corrected file; until then the correction rows stand |
| GAP-046 | Future Ready starts in 2017-18; earlier school-level test results exist only in district PSSA/Keystone files (2009-10 on, district schools only) and are archived but not loaded *(District PSSA/Keystone 2009-10 to 2024-25 loaded into assessment_result 2026-10-04 (district schools only))* | `not-yet-ingested` | medium | closed | us | Stage district PSSA/Keystone files with a sector-coverage label |
| GAP-047 | PDE's persistent attendance definition (2021-22 on) is not documented in the data file; it replaced regular attendance | `unknown` | medium | open | state | Find PDE's published definition and record it in the measure dictionary |
| GAP-048 | District grades 3-8 proficiency fell about 8 points citywide between 2010-11 and 2011-12 (math 59.1% to 50.9%); the cause is not documented in the data files | `unknown` | medium | open | district | Document the cause from district or state sources before charting across it |
| GAP-049 | PDE ESSA school designation codes DFLT and ACSI are not defined in the Fast Facts file (CSI, TSI, and ATSI are the federal categories); 2020-21 shows only DFLT | `unknown` | medium | open | state | Find PDE's code definitions and record them in the dictionary |
| GAP-050 | PDE's economically disadvantaged share for Philadelphia schools rises from a median of 69.5% (2017-18) to 84.9% (2024-25); the files do not say whether the method changed | `unknown` | medium | open | state | Check PDE's definition history (direct certification, CEP) before trending |
| GAP-051 | Peer comparison uses only the poverty of a school's own students; a neighborhood basis (census poverty, income, and adult education of the catchment) is not built because ACS data is not loaded *(Crosswalk ready; see GAP-036)* | `not-yet-ingested` | medium | open | us | Load ACS 5-year tables (keyless Summary File or API with a key), push through geo_xwalk, add basis catchment_census to peer comparison |
| GAP-043 | 2019-20 enrollment keys schools by SRC ID; Camelot Academy's SRC ID does not map to a ULCS, so its 2019-20 enrollment is unassigned *(Resolved 2026-10-04: SRC IDs fall back to other years when a year's list omits a program)* | `not-collected-by-district` | low | closed | us | Ask the district or match by name with a correction row |
| GAP-045 | Ombudsman South Transition (2010-11 and 2011-12) has an SRC school ID that maps to no ULCS code, so its enrollment is unassigned | `not-collected-by-district` | low | open | district | Ask the district for its ULCS code |

## District operations and buildings

| ID | Gap | Kind | Priority | Status | Owner | How to close |
| --- | --- | --- | --- | --- | --- | --- |
| GAP-021 | Daily canceled or late bus list: no public history, and we have not started capturing it *(History not captured is gone)* | `not-public` | high | open | district | Scrape daily with psd snapshot via a scheduled job; needs the exact page URL |
| GAP-022 | Facilities dashboard (scores for building condition, program alignment, utilization, neighborhood vulnerability, plus per-school recommendations) runs in a Qlik app with no export; scripted access is refused *(Wayback has the page shell only, no data)* | `not-public` | high | open | district | Ask the district for an export or API access; meanwhile save the master-plan PDFs; keyed by ULCS |
| GAP-024 | Maintenance work orders, bus on-time history, substitute fill rates, and IEP evaluation timeliness are not public *(Operations is the least covered area)* | `not-public` | high | open | district | Ask the district what exists internally; consider a data request |
| GAP-037 | Board minutes for the April 23 and April 30, 2026 meetings (the facilities plan vote) are not posted; the May 28 approval item has no attachment | `not-public` | high | open | district | Watch later packets; ask the Board office |
| GAP-023 | AHERA asbestos and lead reports are likely PDFs, not structured *(Duplicate of GAP-033)* | `not-yet-ingested` | medium | closed | us | Download, hash, extract room-level results |
| GAP-025 | Staff vacancies (due Aug 2025), SPOTlight scorecard (due spring 2025), and Pre-K sites (due spring 2026) are past the district's promised refresh dates *(Per district data page, checked 2026-10-04)* | `not-collected-by-district` | medium | open | district | Track missed promises in the release table |
| GAP-026 | Goals and Guardrails results are PDFs, with targets reset in April 2024 | `not-yet-ingested` | medium | open | district | Extract per-report tables; version targets in the commitment table |
| GAP-032 | Building condition reports (FCA): 2020-22 reports are PDFs on Google Drive (about 78), 2017 reports and 2018-19 AHERA survive only on the Wayback Machine; the 2022-24 facilities site's API data was never archived | `not-yet-ingested` | medium | open | district | Recover Drive IDs from the archived FCA page; pull Wayback captures; file names start with ULCS |
| GAP-033 | Environmental records (AHERA asbestos, lead, water testing) are hundreds of per-school PDFs in Google Drive folders | `not-yet-ingested` | medium | open | us | List the folders, download and hash, extract results; ULCS in file names |
| GAP-040 | Since 2025, minutes are not posted as their own documents; they appear only as attachments to the next meeting's packet, and action items have no ID that persists across meetings | `not-collected-by-district` | medium | open | district | Parse packets; mint our own resolution IDs |
| GAP-041 | Board records (PrimeGov 2019 on, NovusAgenda, 2013-18 PDFs, SRC on Wayback) are cataloged as sources but not archived | `not-yet-ingested` | medium | open | us | Archive with the PrimeGov JSON API, sequential NovusAgenda IDs, the WordPress PDF list, and Wayback |
| GAP-039 | Board meeting video has no transcripts or captions and cannot be downloaded | `not-collected-by-district` | low | open | district | Store video IDs and titles; consider our own speech-to-text later |
| GAP-042 | 28 of 320 videos on the district TelVue player are not reachable from its listing pages (playlists show at most 50, no pagination); most are SRC meetings *(core/board_video_catalog.csv has 292)* | `not-public` | low | open | district | Ask the district for a video list, or find them via search or individual media pages |

## Workforce

| ID | Gap | Kind | Priority | Status | Owner | How to close |
| --- | --- | --- | --- | --- | --- | --- |
| GAP-027 | Teacher-level and school-level turnover requires the PDE staff files, which are not cataloged or downloaded *(Individual teacher data is deliberately excluded)* | `not-yet-ingested` | medium | open | us | Add PDE personnel files; aggregate to school level only |

## Legal and licensing

| ID | Gap | Kind | Priority | Status | Owner | How to close |
| --- | --- | --- | --- | --- | --- | --- |
| GAP-028 | District Terms of Use restrict copying and limit use to governmental, accountability, and evaluative purposes; OpenDataPhilly lists the license as unspecified *(Nothing is released until resolved)* | `legal` | high | blocked | district | Obtain written permission or a data-sharing agreement; see docs/SOURCE_TERMS.md |
| GAP-029 | District-derived tables already sit in the public repo under prototype/data/ | `legal` | high | open | owner decision | Decide: leave, remove from current tree, or scrub history (force-push needs owner approval) |
| GAP-030 | Terms for PDE, Future Ready, SEDA, and City datasets not yet checked *(SEDA is under a data use agreement)* | `unknown` | medium | open | us | Read each publisher's terms; record in sources/manifest.csv |
