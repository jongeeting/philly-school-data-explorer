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
uv run psd build-geography       # catchments, zones, population-weighted crosswalk
uv run psd link-parcels          # school locations to City parcels (OPA)
uv run psd build-enrollment      # enrollment, catchment flows, school metrics
uv run psd build-scores          # Future Ready scores, growth, attendance, graduation
uv run psd build-assessments     # district PSSA and Keystone results, 2009-10 on
uv run psd build-fast-facts      # state demographics and school attributes
uv run psd build-attendance      # district attendance detail, 2013-14 on
uv run psd build-discipline      # district suspensions and serious incidents
uv run psd build-crdc            # federal CRDC discipline by race, disability, English learner
uv run psd build-area-context    # ACS neighborhood context by tract, catchment, zone, neighborhood
uv run psd peer-comparison       # each school vs. its closest-poverty peers, three poverty bases (derived)
uv run pytest
```

## Roadmap

Data foundation (details in [docs/DATA_MODEL.md](docs/DATA_MODEL.md)):

- [x] Repo scaffold, design rules, source manifest, prototype preserved
- [x] Download tooling: `psd discover` catalogs files, `psd fetch` archives them with SHA-256, `psd snapshot` archives pages
- [ ] Archive the at-risk sources (late-bus list, facilities dashboard) on a schedule
- [x] **Identity:** minted `school_id` (444 schools, 2002 to 2027), dated code crosswalk, reported closures, built from archived district lists ([docs/IDENTITY.md](docs/IDENTITY.md)); lineage deferred. **Blocked for release on the district's data terms** ([docs/SOURCE_TERMS.md](docs/SOURCE_TERMS.md))
- [x] **Geography:** catchments 2012-13 to 2024-25, assignment zones, population-weighted crosswalk, schools linked to City parcels (OPA) ([docs/GEOGRAPHY.md](docs/GEOGRAPHY.md))
- [~] **Measures:** measure dictionary started (`registry/measures.csv`); `enrollment` 2014-15 to 2025-26, `catchment_flow` 2016-17 to 2025-26, and `school_metric` built with status codes ([docs/ENROLLMENT.md](docs/ENROLLMENT.md)); Future Ready test scores, growth, attendance, and graduation 2017-18 to 2024-25 and district PSSA/Keystone 2009-10 to 2024-25 ([docs/SCORES.md](docs/SCORES.md)); Star and attendance detail next
- [~] **Flows and buildings:** catchment flows done; lead paint and drinking-water lead results per school ([docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)); 2020 facility condition assessments ([docs/FACILITIES.md](docs/FACILITIES.md)); asbestos results next; facility plans, school events later
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
