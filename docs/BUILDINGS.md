# Buildings

`uv run psd build-buildings` builds the building layer. A building is one physical structure; a school is a program. One building can hold several schools (17 buildings have two or three listed in the latest district list), and schools move: 23 schools were at more than one building between 2019 and 2027.

## Tables

- `building` (414): `building_id` (permanent, minted into `registry/building_id_registry.csv`), name, kind (353 school buildings, 15 annexes, 14 little school houses, 15 field houses, and garages, offices, a pool, a farm), street address, year built, and the City parcel (OPA account) with how sure we are.
- `building_xwalk` (896 keys): how each outside key points at a building: asbestos report code (317), facility-assessment part code (101), lead folder (247), water folder (231), with the link method.
- `school_building` (482): school x building x years. 374 `primary` rows come from the street address in each year's district school list (2019 to 2027), so a move shows as two rows with their years; 108 `other_building` rows tie a school to an annex or little school house through an environmental or assessment record and carry no years.
- `marts/building` (414 x 29): one row per building with its latest asbestos, lead-paint, drinking-water, and facility-condition results and the school year of each, the schools there now, and the parcel. Column descriptions are in `schema/building.json`.
- `building_parcel_review.csv` (69): buildings to check by hand (no parcel, low confidence, or methods that disagree), with the candidates.

## How records become buildings

Five sources point at places in different ways: the district list (a school's address), asbestos reports (a 4-digit code plus the cover page's name, address, year built, ULCS codes, and sometimes the assessment building code), facility assessments (building codes: B + 3 digits + a sequence, where 001 is the main building and 002 and up are annexes), lead folders (name and address), and water folders (a site name). Records merge when they share an asbestos code (an assessment part maps to a code by `code[1:4] + (sequence - 1)`, or by the "Building #" on the cover; two exceptions are in `corrections/building_links.csv`) or when their street addresses overlap and they are the same kind of structure. Suite, floor, and room text is ignored, a missing direction ("Cecil B Moore" for "N Cecil B Moore") still matches, and a school's two address numbers within ten of each other count as one building. Annexes, little school houses, field houses, pools, garages, and offices stay separate from the main building even at the same address. Folders with no address join the school's main building, or the one addressed building that carries the same school, the same name, or the same surname and first name (never the surname alone: Jenks, Marshall, and Brown each name two schools). Ten hand-set addresses, each with its evidence, are in `corrections/building_links.csv`. Water folders that contain only unread multi-school reports are not buildings.

## Parcels (OPA)

410 of 414 buildings have an OPA account. The district's street address is often not the parcel's address (a corner school is listed on one street and its parcel on the other), and a school's map point can land on a neighbor, so no single method is trusted. Every method answers for every building and they vote:

- the City's parcel layer by the school's map point, limited to the years the school was at that address;
- the City's parcel layer and OPA property records by street address, searched over the whole block so a parcel listed as a range ("2101-27 Eastburn Ave") is found;
- the Census geocoder, then the City parcel containing the point, accepted only for a School District-owned parcel at the point, an overlapping address, a matching owner name, a public parcel, or a parcel next door;
- a lone School District-owned parcel on the street within 80 house numbers, and the main building's parcel for its annexes.

An address-text match counts more than a map point. The result carries `parcel_confidence`: **high** (317) when two or more methods agree and no rival is close; **medium** (65) for one address-text match, a School District parcel at the school's map point, or an annex's main-building parcel; **low** (28) for one weak method; **none** (4). `parcel_methods` lists the agreeing methods and `parcel_conflict` any other account another method suggested. Cross-checking every building against the independent address methods agreed on the account for 455 of 511 comparisons before voting; most of the 56 differences were charter schools whose map point fell on a neighboring parcel, which the vote now corrects.

A parcel is not a building. Annexes and little school houses usually sit on the main building's parcel and share its OPA account (47 buildings share an account with another), and large campuses hold more than one building. Sub-accounts of one parcel (the City lists more than one account at one address) count as one parcel.

Checked against the Build Philly Now parcel table on 2026-10-05 (read-only): 359 of the 363 distinct accounts are present; the other four are not yet in that table.

## Limits

- Buildings are only those that appear in a district list, an environmental or assessment record, or a lead or water folder. About 300 district buildings are in the assessment program; only 76 sites were posted.
- 3 buildings have no address (assessment parts of field sites) and 4 have no parcel (Laboratory Charter, Ombudsman Northwest, Benjamin Franklin/Science Leadership at 5500 N Broad, and the Roxborough field house); the City has no parcel at those addresses and they are in the review file.
- `school_building` before 2019 is not available: the 2017-18 and earlier lists are not in a form we read for addresses. The latest list year is 2027 (the 2026-27 list).
- Building kind comes from the name, so a building named only for its school is called a school building.
