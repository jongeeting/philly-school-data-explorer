# Discoverability: reaching people, agents, and researchers

Goal: whoever is looking for Philadelphia school data (a parent searching, a researcher citing, an agent answering a question) should find this and be able to use it without asking us anything.

## Metadata standards (do once, serve everyone)

| Standard | Serves | Status |
| --- | --- | --- |
| `llms.txt` at repo and site root | LLM agents and crawlers | Repo version done |
| `AGENTS.md` | Coding agents | Done |
| Frictionless `datapackage.json` per release (column descriptions, types, constraints) | Researchers, tools, agents | Phase 4 |
| Croissant JSON-LD (MLCommons) | Hugging Face, Kaggle, ML and agent tooling | Phase 6 |
| schema.org `Dataset` JSON-LD on the site | Google Dataset Search | With site |
| schema.org `School` / `Place` JSON-LD on each school and place page | Search engines, answer engines | With site |
| `CITATION.cff` plus a DOI per release | Researchers, citation tracking | CFF done; DOI at first release |
| `sitemap.xml`, one crawlable static page per school and place | Search engines | With site |
| OpenAPI or JSON schema for the MCP tools and static JSON endpoints | Agents | With MCP |

## Distribution channels

| Channel | Why | When |
| --- | --- | --- |
| GitHub Releases (Parquet, CSV, GeoParquet, GeoJSON, checksums) | Canonical, citable files | Each release |
| Zenodo (GitHub integration) | Free DOI per release; indexed by scholars and Google Scholar | First release |
| Hugging Face Datasets | Where agent and ML users look; Croissant-native | After first release |
| Kaggle Datasets | Students and analysts | After first release |
| OpenDataPhilly listing | Local civic-data audience | After site launch |
| Harvard Dataverse or ICPSR (optional) | Education researchers | If a host org wants it |
| PyPI and CRAN packages, and the MCP server (`uvx`) | Python and R users; MCP clients | After schema stabilizes |
| MCP registry listing | Agent discovery | With MCP |
| Newsroom and research-shop outreach | Humans who will cite us | Launch |

## Formats

- Parquet and CSV for every table; GeoParquet and GeoJSON for geography.
- A codebook per release (generated from `measure` and `source`), also as JSON.
- Static JSON per school and per place at stable URLs, for agents and light scripts.

## Keywords researchers and agents search for

Philadelphia school catchment, assignment zone, school district enrollment, chronic absence, PSSA, Keystone, Future Ready PA Index, PVAAS growth, facilities condition, school closures, charter schools, teacher turnover, ACS tract crosswalk. Use these terms in titles, descriptions, and page text.
