# Peer comparison by poverty

`uv run psd peer-comparison` writes `derived/peer_comparison` (method `poverty_peers_k15_v1`). It answers one question: how does this school's result compare with the schools whose students are most like its own in poverty?

**How peers are chosen.** For each school, year, and measure (ELA and math proficiency; ELA and math growth), the peers are the 15 other schools in the same grade band (K-8, high, or mixed) with the closest share of economically disadvantaged students (PDE's figure for the same year). Selective-admission schools are neither compared nor used as peers, and neither are alternative or virtual programs. K-8 peers are close in poverty (median spread 2.7 points); high-school peers less so (8.5 points), since there are fewer high schools. Bands with fewer than 16 eligible schools (most 6-12 and K-12 schools) get no comparison.

**What is reported.** The school's value, the peer median and middle half (25th to 75th percentile), the difference from the peer median, the peers' poverty range, the peer school IDs, and a plain position: above, within, or below the peer range. Two windows: one year, and a three-year average.

**How much weight it bears.** Across non-overlapping periods (2021-23 vs 2023-25), a school's difference from its peers repeats at r = 0.60 for ELA proficiency and only 0.34 (ELA) and 0.45 (math) for growth. Treat positions as descriptive, prefer the averaged window, and never sort schools by them or fold them into a score.

**Not yet.** The poverty basis is the school's own students. Neighborhood context (census poverty, income, and adult education of the catchment) can change the picture for schools whose students differ from their neighborhood; it waits on ACS data (see DATA_GAPS.md).
