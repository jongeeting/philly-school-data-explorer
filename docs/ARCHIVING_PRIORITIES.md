# Archiving priorities

History that isn't captured is gone. Start these first, before any site work:

1. **Daily canceled/late bus list** (`sdp_transportation_late_buses`): the district keeps no public history. Scrape daily and store each snapshot untouched.
2. **Facilities data dashboard and master plan** (`sdp_facilities_dashboard`, `sdp_facilities_master_plan`): an earlier building-conditions site went offline in 2024. Snapshot every release.
3. **District PDFs** (Goals & Guardrails, charter evaluations, AHERA reports): download and hash on each publication.

Each snapshot goes in `raw/` with a row in the download manifest (URL, retrieval date, SHA-256).
