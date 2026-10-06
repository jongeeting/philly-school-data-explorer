# Buildings

`uv run psd build-buildings` builds the building layer. A building is one physical structure; a school is a program. One building can hold several schools (17 buildings have two or three listed in the latest district list), and schools move: 23 schools were at more than one building between 2019 and 2027.

## Tables

- `building` (467): `building_id` (permanent, minted into `registry/building_id_registry.csv`), name, kind (school building, annex, little school house, field house, pool, garage or barn, office or center, farm or outdoor), street address, year built, and the City parcel's OPA account when known.
- `building_xwalk` (899 keys): how each outside key points at a building: asbestos report code (317), facility-assessment part code (101), lead folder (247), water folder (234), with the link method.
- `school_building` (505): school x building x years. 374 `primary` rows come from the street address in each year's district school list (2019 to 2027), so a move shows as two rows with their years; 131 `other_building` rows tie a school to an annex or little school house through an environmental or assessment record and carry no years.
- `marts/building` (467 x 26): one row per building with its latest asbestos, lead-paint, drinking-water, and facility-condition results and the school year of each, the schools there now, and the parcel. Column descriptions are in `schema/building.json`.

## How records become buildings

Five sources point at places in different ways: the district list (a school's address), asbestos reports (a 4-digit code plus the cover page's address and year built), facility assessments (building codes: B + 3 digits + a sequence, where 001 is the main building and 002 and up are annexes), lead folders (name and address), and water folders (a site name). Records merge when they share an asbestos code (an assessment part maps to a code by `code[1:4] + (sequence - 1)`; two exceptions are in `corrections/building_links.csv`) or when their street addresses overlap and they are the same kind of structure. Suite, floor, and room text is ignored, a missing direction ("Cecil B Moore" for "N Cecil B Moore") still matches, and a school's two address numbers within ten of each other count as one building. Annexes, little school houses, field houses, pools, garages, and offices stay separate from the main building even at the same address. Records with no address join their school's main building.

## Parcels (OPA)

352 of 467 buildings have an OPA account. In order: the school's map point from the vetted `school_parcel` table, restricted to the years the school was at that address (308); the address of an existing school parcel (23); a lookup of the address in the City's parcel service, archived under `raw/city_pwd_parcels/address_queries_*.json` (21). The district's street address is often not the parcel's address (a corner school can sit on a parcel with a different street), so address-only matches are the weakest and are labeled in `parcel_match`.

A parcel is not a building. Annexes and little school houses usually sit on the main building's parcel and share its OPA account (83 buildings share an account with another), and large campuses hold more than one building.

Checked against BPN's parcel table on 2026-10-05 (read-only): 327 of the 329 distinct accounts are present; the two missing are tracked on the BPN side.

## Limits

- Buildings are only those that appear in a district list, an environmental or assessment record, or a lead or water folder. About 300 district buildings are in the assessment program; only 76 sites were posted.
- 65 buildings have no address (mostly annexes and outdoor sites known only from an environmental folder), and 115 have no parcel.
- `school_building` before 2019 is not available: the 2017-18 and earlier lists are not in a form we read for addresses. The latest list year is 2027 (the 2026-27 list).
- Building kind comes from the name, so a building named only for its school is called a school building.
