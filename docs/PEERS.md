# Peer comparison by poverty

`uv run psd peer-comparison` writes `derived/peer_comparison` (method `poverty_peers_k15_v1`). It answers one question: how does this school's result compare with the schools whose students are most like its own in poverty?

**How peers are chosen.** For each school, year, and measure (ELA and math proficiency; ELA and math growth), the peers are the 15 other schools in the same grade band (K-8, high, or mixed) with the closest share of economically disadvantaged students (PDE's figure for the same year). Selective-admission schools are neither compared nor used as peers, and neither are alternative or virtual programs. K-8 peers are close in poverty (median spread 2.7 points); high-school peers less so (8.5 points), since there are fewer high schools. Bands with fewer than 16 eligible schools (most 6-12 and K-12 schools) get no comparison.

**What is reported.** The school's value, the peer median and middle half (25th to 75th percentile), the difference from the peer median, the peers' poverty range, the peer school IDs, and a plain position: above, within, or below the peer range. Two windows: one year, and a three-year average.

**How much weight it bears.** Across non-overlapping periods (2021-23 vs 2023-25), a school's difference from its peers repeats at r = 0.60 for ELA proficiency and only 0.34 (ELA) and 0.45 (math) for growth. Treat positions as descriptive, prefer the averaged window, and never sort schools by them or fold them into a score.

**Three poverty bases, side by side** (`basis` column):

| Basis | What it measures | Covers |
| --- | --- | --- |
| `school_econ_disadvantaged` | PDE's economically disadvantaged share of the school's own students | all schools with Fast Facts |
| `catchment_child_poverty` | ACS 2020-2024 child poverty in the school's own catchment | neighborhood schools only |
| `student_neighborhoods_child_poverty` | enrollment-weighted ACS child poverty of the catchments where the school's students live (catchment flows) | district, charter, and citywide schools, 2016-17 on |

What the bases show (2024-25, ELA proficiency, three-year averages): student poverty and neighborhood child poverty correlate at only 0.54 to 0.59; proficiency tracks student poverty (r = -0.80) more than neighborhood poverty (-0.57 to -0.61); and a school's position is the same on the student and student-neighborhood bases for only 53% of schools. Show the bases together rather than picking one. Example: McCall and Greenberg are above their peer range on every basis; John S. Jenks is above on student poverty but within its range once its neighborhood is taken into account.

Neighborhood figures come from `core/area_context`: ACS 2015-2019 (2010 tracts, crosswalked through 2020 census blocks) for school years through 2019-20, and ACS 2020-2024 after. Both are keyless Summary File downloads; tract values carry margins of error, rollups do not yet. Census-based positions are steadier year to year within one ACS period (r about 0.9) than across the switch between periods (about 0.65).

## How precise the census bases are

Census figures for small areas carry wide margins of error: child poverty is about +/-9.5 points in a typical elementary catchment and +/-4.8 in a high school catchment (2020-2024). K-8 peer groups span only about 5 points of poverty, so a school's census-based peer set could reasonably be different. Each census-based row therefore carries `basis_moe` and `position_robust`: whether the school's position is the same with its poverty figure at both edges of its margin. High-school positions are robust 84-97% of the time; K-8 positions only 47-64% (lower for proficiency, which depends more on poverty, than for growth). Show a census-based position only where `position_robust` is true; otherwise say the comparison is too uncertain to call.
