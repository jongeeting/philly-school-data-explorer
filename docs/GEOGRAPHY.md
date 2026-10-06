# Geography

Built by `uv run psd build-geography` and `uv run psd link-parcels` into `core/` (GeoParquet, GeoJSON, CSV; geometry in EPSG:4326).

| Table | Grain | Source |
| --- | --- | --- |
| `catchment` | school x level (ES/MS/HS) x boundary year | SDP catchment shapefiles, SY 2012-13 to 2024-25 (13 years) |
| `assignment_zone` | K-12 assignment path x boundary year (about 161 per year) | Derived from the elementary layer's grade-by-grade school IDs (`GR_ID_K` ... `GR_ID_12`) |
| `geo_unit` | one polygon of any type | catchments, zones, OpenDataPhilly neighborhoods (159), 2020 tracts |
| `geo_xwalk` | from unit x to unit (x boundary year) | 2020 census blocks (population and housing units) |
| `school_parcel` | school x location x run of years | City PWD parcels, queried at the district's GPS point |

## Population-weighted crosswalk

Every block's 2020 population (P1) and housing units (H1) come from the keyless redistricting bulk file. A block cut by a boundary is split by area; otherwise people are kept where they live. Each row gives `pop_2020`, `pop_share_of_from`, `pop_share_of_to`, and `area_share_of_from` for comparison. Method tag: `census_block_2020_pop_area_split_v1`.

Checks on the first build: blocks sum to 1,603,797 (Philadelphia's 2020 count); catchments cover all but about 40 residents in every year; every populated tract allocates 100% of its people. Population weighting moves 183 of 936 tract-to-elementary-catchment weights by more than 10 points versus area weighting, mostly tracts that are largely park or industrial land.

Neighborhoods are for display only; never use them as an analysis unit.

## School to parcel (OPA)

Each distinct school location is matched to the parcel containing it, else the nearest within 100 m. For district-run schools, a School District-owned parcel within 50 m beats a closer parcel owned by someone else (`match = owner_preferred`), because the district's points often sit in the street next to a rowhouse. `opa_account` is the key the BPN property platform uses.

Reviewed fixes are rows in [`corrections/school_parcel.csv`](../corrections/school_parcel.csv), applied on every build (`replace`, `confirm`, or `unresolved`), each with a reason and the archived evidence it rests on. The first review (Oct 4, 2026) covered the 27 district-run sites on parcels the district does not own, checked against the City's schools layer (OpenDataPhilly, same ULCS codes): 13 replaced (5 where the City's service had returned an error, 8 where the district's point matched a neighbor), 13 confirmed as real arrangements (City-owned buildings, a housing authority building, Penn Alexander, a City prison and juvenile center, leased SLA buildings), and 1 unresolved (Cayuga, 2018).

Current build: 390 school sites; 253 inside a parcel, 100 nearest within 100 m, 24 owner-preferred, 13 corrected; 1 still needs review. The City's parcel service sometimes answers with an error inside a normal response; those answers are retried and never cached.

## Not yet built

Council districts, state house/senate, wards, ZIP codes, and police districts in `geo_unit`; a `building` table (waiting on facilities data, see DATA_GAPS.md); 

## Census context (ACS)

`uv run psd build-area-context` writes `core/area_context` for two ACS 5-year periods: 2015-2019 (2010 tracts, sequence-based Summary File) and 2020-2024 (2020 tracts, table-based Summary File), both keyless. Measures: people and children in poverty, adults with a bachelor's degree or more, owner-occupied homes, and median household income (tract) or its household-weighted approximation (larger areas). 2010 tracts are included in `geo_unit` and `geo_xwalk` (`tract_2010`), allocated through 2020 blocks by 2020 population. Citywide: children in poverty 34.8% (2015-2019) and 29.0% (2020-2024).
Margins of error: tract values carry the Census Bureau's MOEs; shares get MOEs from the Census proportion formula (ratio formula when needed), and rollups combine weighted tract MOEs by root sum of squares (weights treated as fixed, tracts as independent). Sums of table cells count the largest zero-cell MOE once, per Census guidance. Every value has a coefficient of variation and a reliability label (high, medium, low). Elementary catchment child poverty is medium or low reliability for about half of catchments.

## Place geographies

`geo_unit` also holds the places people use to ask about a school: the 10 City Council districts (2024 boundaries), the Pennsylvania House and Senate districts that reach Philadelphia (Census TIGER/Line 2024; 26 and 7), the 66 political wards, 48 ZIP code areas, 22 police districts, and 18 Planning Commission districts. They are current boundaries (`sy` empty), loaded by `psd build-geography` from the City's open data services and Census.

- **`geo_xwalk`** carries a tract to each place type, weighted by 2020 census-block population like the other units. A tract that straddles a boundary splits its population across districts.
- **`school_place`** gives each school's unit of every type, by the school's latest known location (point in polygon). 344 schools have a location (GAP-077). Because it is a point, a school near a boundary sits in one district only; a catchment can span several, which `geo_xwalk` handles.
- **`school_profile`** carries them as `place_council_district`, `place_pa_house`, `place_pa_senate`, `place_ward`, `place_zip`, `place_police_district`, and `place_planning_district`.
- The derived council district matches the district-reported `council_district` for 99.1% of schools (341 of 344). Three differ (sch_00230, sch_00370, sch_00385), likely schools near a boundary or an error in one list; both values stay in the data.
- Legislative boundaries are the 2022 maps; earlier years are not loaded. Election divisions (about 1,700) are not loaded.
