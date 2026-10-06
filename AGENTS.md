# Guide for AI agents

Two audiences: agents **using** the data, and agents **working on** this repo.

## Using the data

- Start with `llms.txt` and `docs/DATA_MODEL.md`. Tables are long (entity, year, measure, group, value); look up meaning in the `measure` table, never guess from a column name.
- Query released Parquet files directly with DuckDB; example queries are in `docs/queries/` and run in tests. For one row per school or per school-year, use `marts/school_profile` and `marts/school_year`; `docs/DATA_DICTIONARY.md` and `schema/*.json` describe every column, and `docs/VALIDATION.md` shows what was checked. For anything about a physical building (asbestos, lead, water, condition, parcel), use `marts/building` and `school_building`; a building can hold several schools, and results are per building, not per school.
- Always report the `sy` (spring year of the school year), the measure's denominator, and the `source_id`.
- Respect `status`: suppressed, waived, not applicable, and carried-forward values are not zeros or blanks.
- Show facts and fair comparisons. Do not produce a best-to-worst ranking of schools, and do not state causes the data cannot support. On contested topics, present both sides' measures together.
- Check `sources/gaps.csv` before saying data does not exist, and when you find a new gap, add a row there and run `uv run psd gaps`.
- Never derive or report groups under 20 students, including by subtracting or combining queries.
- Names of individual employees are not in this repo and must not be reconstructed.

## Working on this repo

- Read `CONTRIBUTING.md`: the thirteen design rules are the spec.
- `uv sync`, then `uv run pytest` and `uv run ruff check .` must pass.
- `raw/` is never edited; fixes are rows in the `correction` table.
- `private/` is git-ignored internal strategy. Never commit it, quote it, or link to it from public files.
- `prototype/` is a frozen first pass; port from it, do not edit it.
- American English.
