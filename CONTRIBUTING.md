# Contributing

Design rules every table follows (full context in [docs/DATA_MODEL.md](docs/DATA_MODEL.md)):

1. **Keys.** Each entity gets one minted, permanent ID (`school_id`, `building_id`, `zone_id`). Outside codes (ULCS, AUN plus state school number, NCES, OPA parcel number) live in a crosswalk table with valid-from and valid-to years, never as the primary key.
2. **Time.** `sy` = the spring year of a school year (2025 = SY 2024-25 = FY2025, July to June). Every row also stores its snapshot date when the source has one (most counts are October 1).
3. **Grain.** Each fact table states its grain in one line. No table mixes grains.
4. **Long, not wide.** Scores, enrollment, and spending are rows (entity, year, measure, group, value). Wide views are built for the website, not stored.
5. **Status beside value.** Every value has a `status`: reported, suppressed, waived, not applicable, carried forward, or derived.
6. **Provenance on every row.** `source_id` points to the `source` table: publisher, URL, file name, download date, file hash, license.
7. **Raw is never edited.** Every fix is a row in `correction` with a reason.
8. **Derived is labeled.** Computed values live in `derived/`, tagged with a method version, never mixed into source facts.

Also:

- Apply the state's small-cell rule (suppress groups under 20) to anything derived.
- Store only aggregates for staff data; no named individuals in this repo.
- Show facts and fair comparisons; never a single default rank.
- American English.
- Nothing goes into `derived/` or a release until its manifest row records what its upstream terms allow (SEDA in particular is under a data use agreement).
- Tests must pass (`uv run pytest`) and `uv run ruff check .` must be clean before merging.
