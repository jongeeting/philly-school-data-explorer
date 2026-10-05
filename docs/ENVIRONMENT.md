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
