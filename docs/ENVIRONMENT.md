# Lead paint and drinking water

`uv run psd build-env-results` reads the district's lead-safe assessments and lead-in-water letters, archived from its environmental Google Drive by `uv run psd fetch-environmental-latest`, the most recent report per school and type. Both are point-in-time: each building was assessed or tested once in its cycle, in different years.

## Drinking water (`school_water_lead`, 2022 to 2026, mostly 2025-26)

One row per outlet sample: date, floor, outlet, type (hydration station, fountain, faucet, food prep, ice maker), lead in parts per billion, whether it was below the lab's reporting limit, and whether it was above the district's 10 ppb action level. Follow-up letters (`follow_up`) add the retest and the corrective action ("Installed filter and retested", "Remediation complete").

`school_metric`: `water_outlets_tested` and `water_outlets_above_action`, from each building's latest initial test. Counts are the letter's own stated totals where it gives them; parsed rows match those totals in 224 of 230 letters (the rest lose wrapped rows).

- 219 schools; 2,984 outlets in the latest tests, 37 above 10 ppb, at 29 schools. 87% of samples were below the reporting limit (about 1 ppb).
- Outlets above the level are mostly food-prep outlets and faucets (25 and 11); 3 were hydration stations, which are 78% of the outlets tested.

## Lead paint (`school_lead_paint`, 2017 to 2026, mostly 2025-26)

One row per file in each building's lead-safe folder. For assessment files, the components tested with an XRF analyzer, the inspector's positive calls, positives with damaged paint and their square feet, the count at or above the federal 1.0 mg/cm2 level, and the inspection dates. Five firms use the same table; 99.6% of result rows are read.

`school_metric`: `lead_paint_components_tested`, `lead_paint_components_positive`, `lead_paint_positive_damaged`, from each building's most recent full survey (200+ components; smaller files are follow-up checks).

- 163 schools. The median school had lead paint on 21% of tested components; 142 had some lead-painted components with damaged paint (median 67). Damage is recorded before stabilization; the certification report records the fix.

## Linking and limits

- Files are linked by the school's street address in the master school lists, then by name; shared buildings link to every school in them. Twelve hand links are in `corrections/env_site_school.csv`. Annexes, field houses, and offices are kept with `site_folder` and no school.
- Not read: two 2019 water reports covering many charter schools in one table, archived results, and the asbestos (AHERA) reports, which are being archived for later work.

## Asbestos (AHERA) (`building_asbestos`, `building_asbestos_item`, mostly 2025 to 2026)

`uv run psd build-asbestos` reads each building's most recent 6-month periodic surveillance and 3-year re-inspection. Since 2023 both use one template whose Appendix A is a room-by-room log: every material in every space, its status (confirmed, assumed, no asbestos detected, non-suspect), amount, and damaged amount, in square feet, linear feet, or each.

- `building_asbestos`: one row per report with the building's ULCS code, inspection period, year built, and totals from the log: asbestos-containing items (confirmed or assumed), items with damage, and amounts by unit. Amounts are never added across units. `is_latest` marks the report that feeds `school_metric`.
- `building_asbestos_item`: the confirmed and assumed rows of each building's latest report, with a material group (pipe and boiler insulation, floor tile and mastic, transite, plaster and surfacing, ceiling tile, caulk and sealants, other).
- `school_metric`: `asbestos_items` and `asbestos_items_damaged`. A school with an annex or little school house has more than one building code; the counts add across its buildings (each building stays separate in `building_asbestos`).

Read this as a record of managed materials, not a risk score. Asbestos left intact in good condition is legal and common in buildings of this age, so the item count tracks building size and age. Damage as recorded at inspection is the actionable figure; repairs show up in the next report.

Limits: reports before 2023 (13 buildings' latest is from 2019, 5 from 2016) use an older layout and are read where the log parses; 12 buildings' newest report could not be downloaded (Drive served a confirmation page), so they use the previous one.
