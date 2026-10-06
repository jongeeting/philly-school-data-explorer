# Validation report

Generated 2026-10-06 by `uv run psd validate`. Hard checks fail the build; reconciliations compare independent sources and fail below a stated floor.

## Hard checks

| Check | Result | Detail |
| --- | --- | --- |
| school_metric grain is unique | pass | 0 duplicate keys |
| every metric school_id is in the registry | pass | 0 unknown |
| every measure is in the dictionary | pass | [] |
| statuses are from the allowed set | pass | [] |
| reported rows have a value | pass | 0 blank |
| every row has a source_id | pass | 0 blank |
| sy is within 2000 to 2027 | pass | range 2010 to 2027 |
| count measures are not negative | pass | 0 negative |
| percent measures are between 0 and 100 | pass | 0 outside; [] |
| school_year is unique by school and sy | pass | 8573 rows |
| school_profile has one row per school | pass | 494 rows |
| marts cover every metric school | pass |  |
| facility parts add up to site totals | pass | 0 sites differ by more than $1,000 |
| enrollment grades add to the all-grades row (within 1%) | pass | grades/all = 0.9986 over 5145 school-years |
| building_id is unique | pass | 467 buildings |
| every crosswalk key points at a building | pass | 899 keys |
| no outside key maps to two buildings | pass |  |
| school_building points at real schools and buildings | pass | 505 rows |
| most listed schools have a building from the district list (95%) | pass | 324 of 324 |
| every latest asbestos report has a building | pass | 0 without |
| every assessed building has a building_id | pass | 0 without |

## Reconciliations against independent sources

| Comparison | School-years | Correlation | Total ratio | Floor | Result | Note |
| --- | --- | --- | --- | --- | --- | --- |
| state enrollment vs district October 1 count | 2,408 | 0.999 | 1.004 | 0.98 | pass | two independent counts of the same students |
| federal vs district students with an out-of-school suspension | 833 | 0.976 | 0.962 | 0.93 | pass | same school-years, 2013-14 on; the sources count somewhat differently |
| federal vs district enrollment | 1,584 | 0.990 | 1.018 | 0.95 | pass | federal count date differs from October 1 |
| facility FCI recomputed from costs | 76 | 1.000 | 1.000 | 0.999 | pass | repair cost / replacement value equals the reported index |

## Status mix in school_metric

| Status | Rows |
| --- | --- |
| reported | 687,024 |
| suppressed | 185,727 |
| not_reported | 76,898 |
| not_applicable | 57,089 |
| carried_forward | 14,444 |
| waived | 7,200 |
| derived | 1,625 |
| not_separately_measurable | 1,084 |
| blended | 495 |
| partial | 265 |
| invalid_in_source | 1 |

## Coverage: schools with a reported `all students` value, by measure and school year

| Measure | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | 2027 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `asbestos_items` |  |  |  |  | 1 |  |  | 2 |  |  | 1 | 4 | 1 | 7 | 232 |  |
| `asbestos_items_damaged` |  |  |  |  | 1 |  |  | 2 |  |  | 1 | 4 | 1 | 7 | 232 |  |
| `building_capacity` |  |  |  |  |  | 246 | 246 | 246 | 250 | 248 | 246 | 246 | 245 | 245 | 258 |  |
| `catchment_size` |  |  |  |  |  | 329 | 337 | 341 | 350 | 328 | 327 | 334 | 334 | 343 | 332 |  |
| `cep_econ_disadvantaged_rate` |  |  |  |  |  |  |  |  |  |  |  | 245 |  |  |  |  |
| `crdc_enrollment` | 266 |  | 275 |  | 289 |  | 300 |  |  | 301 | 299 |  |  |  |  |  |
| `crdc_n_arrested` | 265 |  | 275 |  | 289 |  | 300 |  |  | 83 | 299 |  |  |  |  |  |
| `crdc_n_expelled` | 265 |  | 111 |  | 289 |  | 300 |  |  | 84 | 299 |  |  |  |  |  |
| `crdc_n_iss` | 265 |  | 275 |  | 289 |  | 300 |  |  | 84 | 299 |  |  |  |  |  |
| `crdc_n_oss` | 265 |  | 275 |  | 289 |  | 300 |  |  | 84 | 299 |  |  |  |  |  |
| `crdc_n_referred_law` | 265 |  | 165 |  | 289 |  | 300 |  |  | 84 | 299 |  |  |  |  |  |
| `enrollment_catchment_ratio` |  |  |  |  |  | 196 | 194 | 192 | 197 | 196 | 197 | 196 | 196 | 195 | 195 |  |
| `fca_condition_score_pct` |  |  |  |  |  |  |  |  |  |  | 73 |  |  |  |  |  |
| `fca_fci_pct` |  |  |  |  |  |  |  |  |  |  | 73 |  |  |  |  |  |
| `fca_school_score_pct` |  |  |  |  |  |  |  |  |  |  | 67 |  |  |  |  |  |
| `fca_suitability_score_pct` |  |  |  |  |  |  |  |  |  |  | 67 |  |  |  |  |  |
| `grad_rate_4yr` |  |  |  |  |  |  | 79 | 84 | 85 | 84 | 87 | 84 | 86 | 85 |  |  |
| `grad_rate_5yr` |  |  |  |  |  |  | 73 | 82 | 83 | 83 | 83 | 86 | 84 | 85 |  |  |
| `growth_score_ela` |  |  |  |  |  |  | 292 | 297 |  |  | 231 | 294 | 295 | 291 |  |  |
| `growth_score_math` |  |  |  |  |  |  | 292 | 297 |  |  | 229 | 295 | 294 | 292 |  |  |
| `growth_score_science` |  |  |  |  |  |  | 288 | 294 |  |  | 247 | 296 | 293 |  |  |  |
| `lead_paint_components_positive` |  |  |  |  |  | 1 |  | 1 |  |  | 3 | 15 | 8 | 37 | 84 | 14 |
| `lead_paint_components_tested` |  |  |  |  |  | 1 |  | 1 |  |  | 3 | 15 | 8 | 37 | 84 | 14 |
| `lead_paint_positive_damaged` |  |  |  |  |  | 1 |  | 1 |  |  | 3 | 15 | 8 | 37 | 84 | 14 |
| `participation_ela` |  |  |  |  |  |  | 293 | 297 |  | 262 | 297 | 297 | 294 | 294 |  |  |
| `participation_math` |  |  |  |  |  |  | 293 | 297 |  | 294 | 271 | 297 | 294 | 294 |  |  |
| `participation_science` |  |  |  |  |  |  | 292 | 296 |  | 273 | 286 | 297 | 294 | 286 |  |  |
| `pct_catchment_students_attending` |  |  |  |  |  | 196 | 194 | 192 | 197 | 196 | 197 | 196 | 196 | 195 | 195 |  |
| `pct_enrollment_from_catchment` |  |  |  |  |  | 196 | 194 | 192 | 350 | 328 | 327 | 333 | 333 | 343 | 332 |  |
| `pct_grade3_reading_proficient` |  |  |  |  |  |  | 204 | 204 |  | 206 | 209 | 205 | 204 | 204 |  |  |
| `pct_grade7_math_proficient` |  |  |  |  |  |  | 177 | 178 |  | 180 | 182 | 182 | 177 | 178 |  |  |
| `pct_persistent_attendance` |  |  |  |  |  |  |  |  |  |  | 301 | 298 | 298 | 298 |  |  |
| `pct_proficient_ela` |  |  |  |  |  |  | 293 | 297 |  | 240 | 297 | 297 | 294 | 294 |  |  |
| `pct_proficient_math` |  |  |  |  |  |  | 293 | 297 |  | 287 | 271 | 297 | 294 | 294 |  |  |
| `pct_proficient_science` |  |  |  |  |  |  | 292 | 296 |  | 193 | 286 | 297 | 294 |  |  |  |
| `pct_regular_attendance` |  |  |  |  |  |  | 296 | 300 | 302 | 301 |  |  |  |  |  |  |
| `retention_total_enrollment` |  |  |  |  |  | 329 | 337 | 341 | 350 | 328 | 327 | 334 | 334 | 343 | 332 |  |
| `sdp_attendance_students` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_average_daily_attendance` |  |  | 212 | 216 | 215 | 215 | 215 | 215 | 215 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_n_attending_90` |  |  |  |  |  |  |  |  |  | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_n_attending_95` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_n_oss_0` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_n_oss_1` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_n_oss_2` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_n_oss_3` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_n_oss_4plus` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_oss_students` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_pct_attending_90` |  |  |  |  |  |  |  |  |  | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_pct_attending_95` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_pct_oss_0` |  |  | 212 | 216 | 216 | 213 | 213 | 213 | 213 | 213 | 214 | 215 | 216 | 216 |  |  |
| `sdp_serious_incidents_total` |  | 240 | 219 | 216 | 242 | 222 | 229 | 220 | 222 | 191 | 215 | 216 | 218 | 217 |  |  |
| `state_enrollment` |  |  |  |  |  |  | 299 | 304 | 304 | 301 | 302 | 301 | 299 | 298 |  |  |
| `students_attending_neighborhood_school` |  |  |  |  |  | 196 | 194 | 192 | 350 | 328 | 327 | 334 | 334 | 343 | 332 |  |
| `water_outlets_above_action` |  |  |  |  |  |  |  |  | 1 |  | 1 | 14 | 4 | 95 | 96 | 8 |
| `water_outlets_tested` |  |  |  |  |  |  |  |  | 1 |  | 1 | 14 | 4 | 95 | 96 | 8 |
