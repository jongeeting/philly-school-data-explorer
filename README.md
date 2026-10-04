# Philly School Data

Open, linked data on Philadelphia's public schools: who goes to each school, how the building is doing, how students are doing, and how that has changed over time. Everything comes from data the School District, the Pennsylvania Department of Education, the City, and the Census Bureau already publish. This project links it together and records where every number came from.

**Status:** early. Phase 1 (repo scaffold and identity layer) is underway. The full plan is in [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Principles

- **Facts, not rankings.** Information and fair comparisons; never a best-to-worst list.
- **Neutral by design.** Contested topics are added in pairs so each side's concerns appear together.
- **Open and checkable.** Code and data are public; every number traces to a source file.
- **Built to hand off.** Static files and a static site, cheap enough for any host organization to run.

## Layout

| Folder | Contents | In git? |
| --- | --- | --- |
| `raw/` | Downloads exactly as published (never edited) | No; manifest and download scripts are |
| `staging/` | Each source cleaned to the design rules | No; rebuilt by script |
| `core/` | The core tables, as Parquet/GeoParquet | Released via GitHub releases |
| `marts/` | Wide tables shaped for the website | Released |
| `derived/` | Computed estimates tagged by method version | Released |
| `sources/` | Source manifest: URL, publisher, license, refresh cadence | Yes |
| `prototype/` | The first-pass scripts and outputs (Oct 3, 2026) that this project grew from | Yes |
| `docs/` | Data model, findings, methods | Yes |

## Licensing and citing

- **Code:** MIT ([LICENSE](LICENSE)).
- **Our compiled and derived data:** CC BY 4.0 ([LICENSE-DATA](LICENSE-DATA)). Please credit "Philly School Data" and the release version you used.
- **Source data** keeps its publisher's terms, recorded in `sources/manifest.csv`.

## Relationship to Build Philly Now

This project began inside [Build Philly Now](https://buildphillynow.com)'s workspace and shares parcel and boundary data with its property platform. The two are separate projects with separate branding.
