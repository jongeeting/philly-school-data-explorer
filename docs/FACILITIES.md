# Facility condition

`uv run psd build-fca` reads the facility condition assessments (FCAs) the district posted for the 2020 cycle: 76 district sites, assessed by Parsons, reports dated April and May 2022 (one site was posted twice and is kept once).

## Tables

- `facility_condition`: one row per site. Gross area, year built, replacement value, repair cost, facility condition index (FCI = repair cost / replacement value), remaining service life (RSLI), and Parsons' condition, educational suitability, and overall school scores.
- `facility_condition_part`: each building and grounds area on the site, with its own FCI and costs. Parts add up exactly to the site totals in all 76 reports.
- `facility_condition_system`: FCI and costs for 14 major systems (roof, windows, boilers, HVAC, electrical, lighting, and others). System FCIs can exceed 100%: replacing one system can require upgrading others.

`school_metric`: `fca_fci_pct`, `fca_condition_score_pct`, `fca_suitability_score_pct`, `fca_school_score_pct`. Schools sharing a site each get its figures; Bayard Taylor, on two sites, gets the combined FCI and replacement-value-weighted scores.

## Facts

District FCI tiers: under 15% minimal capital need; 15-25% refurbish systems; 25-45% replace systems; 45-60% consider major renovation; over 60% consider closing or replacement.

- Median FCI 47.1%. Of 76 sites: 2 under 15%, 3 at 15-25%, 27 at 25-45%, 38 at 45-60%, 6 over 60%.
- $1.54 billion in assessed repairs against $3.82 billion replacement value.
- Heating, ventilation, and unit ventilators are the largest repair need ($354 million), then heating and cooling controls ($112 million), windows ($102 million), and lighting ($101 million).

## Linking and limits

- Building codes are B plus the first three digits of a school's ULCS code (B842001 = 8420). When that code belongs to a school that closed before 2021, the site links by street address to the school there now (10 sites), or by hand (`corrections/env_site_school.csv`: Birney and Cleveland, now charter schools). Two athletic field sites are unlinked.
- Only these 76 reports are posted; the district has about 300 buildings. Earlier reports (2015-17) and the 2022-24 facilities dashboard are not in structured form.
