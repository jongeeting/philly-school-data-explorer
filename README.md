# Philly School Data Explorer

Open, linked data on Philadelphia's public schools: who goes to each school, how the building is doing, how students are doing, and how that has changed over time. Everything comes from data the School District, the Pennsylvania Department of Education, the City, and the Census Bureau already publish. This project links it together and records where every number came from.

**Status:** early. Scaffold and prototype are in place; the identity layer is next. The full plan is in [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

Built for people and agents equally: a dashboard, an MCP server, a chatbot, and plain files for researchers all read the same self-describing data. See [AGENTS.md](AGENTS.md), [llms.txt](llms.txt), and [docs/DISCOVERABILITY.md](docs/DISCOVERABILITY.md).

## Principles

- **Facts, not rankings.** Information and fair comparisons; never a best-to-worst list.
- **Neutral by design.** Contested topics are added in pairs so each side's concerns appear together.
- **Open and checkable.** Code and data are public; every number traces to a source file.
- **Built to hand off.** Static files and a static site, cheap enough for any host organization to run.

## Layout

| Folder | Contents | In git? |
| --- | --- | --- |
| `raw/` | Downloads exactly as published (never edited) | No; `sources/downloads.csv` and the tool are |
| `staging/` | Each source cleaned to the design rules | No; rebuilt by script |
| `core/` | The core tables, as Parquet/GeoParquet | Released via GitHub releases |
| `marts/` | Wide tables shaped for the website | Released |
| `derived/` | Computed estimates tagged by method version | Released |
| `sources/` | `manifest.csv` (datasets), `files.csv` (discovered file URLs), `downloads.csv` (what we archived, with hashes) | Yes |
| `registry/` | Permanent `school_id` registry (append-only) | Yes |
| `src/phillyschools/` | The `psd` command line tool and build code | Yes |
| `prototype/` | The first-pass scripts and outputs (Oct 3, 2026) that this project grew from | Yes |
| `docs/` | Data model, [data gaps](docs/DATA_GAPS.md), findings, methods | Yes |

## Quick start

```bash
uv sync
uv run psd discover              # catalog downloadable files from each source page
uv run psd fetch --dry-run --source sdp_master_school_list   # preview sizes
uv run psd fetch --source sdp_master_school_list              # archive into raw/
uv run psd build-identity        # build core/ identity tables
uv run pytest
```

## Roadmap

Data foundation (details in [docs/DATA_MODEL.md](docs/DATA_MODEL.md)):

- [x] Repo scaffold, design rules, source manifest, prototype preserved
- [x] Download tooling: `psd discover` catalogs files, `psd fetch` archives them with SHA-256, `psd snapshot` archives pages
- [ ] Archive the at-risk sources (late-bus list, facilities dashboard) on a schedule
- [~] **Identity:** minted `school_id`, dated code crosswalk, events, corrections, built from archived district lists ([docs/IDENTITY.md](docs/IDENTITY.md)); lineage next. **Blocked for release on the district's data terms** ([docs/SOURCE_TERMS.md](docs/SOURCE_TERMS.md))
- [ ] **Geography:** catchments by vintage, assignment zones, population-weighted tract crosswalk
- [ ] **Measures:** measure dictionary, method breaks, `school_metric` and `enrollment` with status codes
- [ ] **Flows and buildings:** catchment flows, buildings, conditions, facility plans, school events
- [ ] **Marts and dictionary:** wide tables, generated data dictionary, JSON schemas, tested example queries
- [ ] **First release:** validation report, version tag, changelog, DOI

Access layers (each reads the same released files):

- [ ] **Files and DuckDB:** Parquet and CSV releases; query straight from release URLs
- [ ] **Open metadata:** `datapackage.json`, Croissant, Zenodo DOI, Hugging Face and Kaggle mirrors
- [ ] **MCP server:** read-only, runs locally via `uvx`; tool descriptions enforce the rules (facts not rankings, small cells, cite source and year)
- [ ] **Dashboard:** static site with one crawlable page per school and place, plus JSON for each
- [ ] **Chatbot:** answers only from curated marts first, free-form queries later; needs a host that owns the running cost and accountability for answers

## Decisions pending

Repo owner (this account or a neutral org), neighborhood set for display, how far back to build (2012-13 or 2017-18), shared geography package with BPN, and hosting for any live chatbot.

## Licensing and citing

- **Code:** MIT ([LICENSE](LICENSE)).
- **Our compiled and derived data:** CC BY 4.0 ([LICENSE-DATA](LICENSE-DATA)). Please credit "Philly School Data Explorer" and the release version you used.
- **Source data** keeps its publisher's terms, recorded in `sources/manifest.csv`.

## Relationship to Build Philly Now

This project began inside [Build Philly Now](https://buildphillynow.com)'s workspace and shares parcel and boundary data with its property platform. The two are separate projects with separate branding.
