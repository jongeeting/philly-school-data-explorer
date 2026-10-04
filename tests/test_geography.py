import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from phillyschools.geography import allocate_blocks, crosswalk, zone_id_for
from phillyschools.parcels import best_parcel, school_sites

CRS = "EPSG:2272"


def gdf(rows):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)


def test_population_weights_follow_people_not_area():
    # Two blocks in one tract: a big empty one (park) and a small one with everyone in it.
    blocks = gdf(
        [
            {"geoid20": "b1", "pop20": 0, "housing20": 0, "geometry": box(0, 0, 90, 100)},
            {"geoid20": "b2", "pop20": 100, "housing20": 40, "geometry": box(90, 0, 100, 100)},
        ]
    )
    blocks["block_area"] = blocks.geometry.area
    tract = gdf([{"unit_id": "t", "geometry": box(0, 0, 100, 100)}])
    catchments = gdf(
        [
            {"unit_id": "west", "geometry": box(0, 0, 50, 100)},
            {"unit_id": "east", "geometry": box(50, 0, 100, 100)},
        ]
    )
    xw = crosswalk(allocate_blocks(blocks, tract), allocate_blocks(blocks, catchments)).set_index(
        "to_unit"
    )
    assert xw.loc["east", "pop_share_of_from"] == 1.0
    assert xw.loc["west", "area_share_of_from"] == 0.5  # area weighting would have said half
    assert round(xw["pop_2020"].sum()) == 100


def test_split_block_is_allocated_by_area():
    blocks = gdf([{"geoid20": "b", "pop20": 100, "housing20": 0, "geometry": box(0, 0, 100, 100)}])
    blocks["block_area"] = blocks.geometry.area
    units = gdf(
        [
            {"unit_id": "a", "geometry": box(0, 0, 25, 100)},
            {"unit_id": "b", "geometry": box(25, 0, 100, 100)},
        ]
    )
    alloc = allocate_blocks(blocks, units).set_index("unit_id")
    assert round(alloc.loc["a", "pop"]) == 25 and round(alloc.loc["b", "pop"]) == 75


def test_zone_id_is_stable_for_same_path():
    path = ("1010", "1010", "2020", "3030")
    assert (
        zone_id_for(path)
        == zone_id_for(tuple(path))
        != zone_id_for(("1010", "9999", "2020", "3030"))
    )


def _answer(features):
    return {
        "features": [{"geometry": f[0].__geo_interface__, "properties": f[1]} for f in features]
    }


def test_parcel_prefers_containing_then_district_owned():
    # Work in EPSG:2272 feet; build a point via a known lon/lat and parcels around it.
    pt = gpd.GeoSeries.from_xy([-75.2], [39.95], crs="EPSG:4326").to_crs(CRS).iloc[0]
    x, y = pt.x, pt.y
    rowhouse = (box(x + 5, y - 10, x + 25, y + 10), {"brt_id": "1", "owner1": "SMITH JOHN"})
    district = (
        box(x + 40, y - 50, x + 140, y + 50),
        {"brt_id": "2", "owner1": "SCHOOL DISTRICT OF PHILA"},
    )
    inside = (box(x - 10, y - 10, x + 2, y + 10), {"brt_id": "3", "owner1": "CITY OF PHILA"})

    near = best_parcel(39.95, -75.2, _answer([rowhouse, district]))
    assert near["opa_account"] == "1" and near["match"] == "nearest"
    pref = best_parcel(39.95, -75.2, _answer([rowhouse, district]), district_run=True)
    assert pref["opa_account"] == "2" and pref["match"] == "owner_preferred"
    contained = best_parcel(39.95, -75.2, _answer([rowhouse, inside]), district_run=True)
    assert contained["opa_account"] == "3" and contained["confidence"] == "high"
    assert best_parcel(39.95, -75.2, {"features": []})["match"] == "none"


def test_school_sites_split_on_moves():
    attr = pd.DataFrame(
        {
            "school_id": ["s"] * 4,
            "sy": [2020, 2021, 2022, 2023],
            "lat": [39.9, 39.9, 39.95, 39.9],
            "lon": [-75.1, -75.1, -75.2, -75.1],
        }
    )
    sites = school_sites(attr)
    assert len(sites) == 3  # 2020-21 at A, 2022 at B, 2023 back at A
