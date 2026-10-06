"""Place geographies: council, state legislative, ward, ZIP, police, and planning districts.

Boundaries come from the City's ArcGIS services and Census TIGER/Line. They are added to
`geo_unit` (one polygon per unit, current boundaries, `sy` empty), crosswalked from Census tracts
with the same block-population weights as the other units, and joined to schools by the school's
location (`school_place`). Every download is archived under raw/ and logged in
sources/downloads.csv.
"""

import hashlib
import json
from datetime import UTC, datetime

import geopandas as gpd
import pandas as pd
import requests

from . import CORE, RAW, USER_AGENT
from .fetch import append_download

CRS_WORK = "EPSG:2272"
ARCGIS = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services"
TIGER = "https://www2.census.gov/geo/tiger/TIGER2024"

# unit type -> (source_key, label, url, id column, id prefix, name template)
CITY_LAYERS = {
    "council_district": ("city_council_districts", "Council_Districts_2024", "district_num"),
    "ward": ("city_political_wards", "Political_Wards", "ward_num"),
    "zip": ("city_zip_codes", "Zipcodes_Poly", "code"),
    "police_district": ("city_police_districts", "police_districts", "DIST_NUMC"),
    "planning_district": ("city_planning_districts", "Planning_Districts", "abbrev"),
}
LEGISLATIVE = {
    "pa_house": ("census_sldl", f"{TIGER}/SLDL/tl_2024_42_sldl.zip", "SLDLST"),
    "pa_senate": ("census_sldu", f"{TIGER}/SLDU/tl_2024_42_sldu.zip", "SLDUST"),
}
PLACE_TYPES = [*CITY_LAYERS, *LEGISLATIVE]
MIN_OVERLAP_SQM = 500_000  # a legislative district counts as in the city above 0.5 sq km


def _archive(source_key: str, url: str, body: bytes, name: str, ext: str):
    folder = RAW / source_key
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    path = folder / f"{name}_{now.strftime('%Y%m%dT%H%M%SZ')}{ext}"
    path.write_bytes(body)
    append_download(
        {
            "source_key": source_key,
            "url": url,
            "local_path": str(path.relative_to(RAW.parent)),
            "retrieved_at_utc": now.isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "etag": "",
            "last_modified": "",
        }
    )
    return path


def fetch_places() -> list:
    """Download any boundary layer not yet archived."""
    got = []
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    for utype, (source_key, service, _col) in CITY_LAYERS.items():
        if list((RAW / source_key).glob("*.geojson")):
            continue
        url = (
            f"{ARCGIS}/{service}/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"
        )
        resp = session.get(url, timeout=120)
        resp.raise_for_status()
        json.loads(resp.content)  # fail loudly on an error body
        got.append(_archive(source_key, url, resp.content, utype, ".geojson"))
    for utype, (source_key, url, _col) in LEGISLATIVE.items():
        if list((RAW / source_key).glob("*.zip")):
            continue
        resp = session.get(url, timeout=300)
        resp.raise_for_status()
        got.append(_archive(source_key, url, resp.content, utype, ".zip"))
    return got


def _latest(source_key: str, pattern: str):
    return max((RAW / source_key).glob(pattern))


def _pad(value, width: int) -> str:
    return str(value).strip().split(".")[0].zfill(width)


def place_units(city: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One GeoDataFrame of every place unit in the working CRS.

    `city` is the union of Philadelphia's Census tracts, used to keep only legislative districts
    that reach into the city."""
    frames = []
    for utype, (source_key, _service, col) in CITY_LAYERS.items():
        g = gpd.read_file(_latest(source_key, "*.geojson")).to_crs(CRS_WORK)
        if utype == "zip":
            key = g[col].astype(str).str.strip().str[:5]
            g = g.assign(_key=key).dissolve(by="_key").reset_index()
            ids = "zip_" + g["_key"]
            names = "ZIP " + g["_key"]
        elif utype == "council_district":
            ids = "council_" + g[col].map(lambda v: _pad(v, 2))
            names = "Council District " + g[col].map(lambda v: str(int(float(v))))
        elif utype == "ward":
            ids = "ward_" + g[col].map(lambda v: _pad(v, 2))
            names = "Ward " + g[col].map(lambda v: str(int(float(v))))
        elif utype == "police_district":
            ids = "police_" + g[col].map(lambda v: _pad(v, 2))
            names = "Police District " + g[col].map(lambda v: str(int(float(v))))
        else:
            ids = "planning_" + g[col].astype(str).str.lower().str.replace(r"\W+", "_", regex=True)
            names = g["dist_name"].astype(str)
        frames.append(
            gpd.GeoDataFrame(
                {"unit_id": ids.values, "unit_type": utype, "name": names.values},
                geometry=g.geometry.values,
                crs=CRS_WORK,
            )
        )
    for utype, (source_key, _url, col) in LEGISLATIVE.items():
        g = gpd.read_file(f"zip://{_latest(source_key, '*.zip')}").to_crs(CRS_WORK)
        overlap = g.geometry.intersection(city).area
        g = g[overlap > MIN_OVERLAP_SQM * 10.7639]  # square meters to square feet
        prefix = "pahouse_" if utype == "pa_house" else "pasenate_"
        label = "PA House District " if utype == "pa_house" else "PA Senate District "
        frames.append(
            gpd.GeoDataFrame(
                {
                    "unit_id": (prefix + g[col].map(lambda v: _pad(v, 3))).values,
                    "unit_type": utype,
                    "name": (label + g[col].map(lambda v: str(int(v)))).values,
                },
                geometry=g.geometry.values,
                crs=CRS_WORK,
            )
        )
    out = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=CRS_WORK)


def school_places(units: gpd.GeoDataFrame) -> pd.DataFrame:
    """Each school's place units, by the school's latest known location (point in polygon)."""
    sp = pd.read_parquet(CORE / "school_parcel.parquet")
    sp = sp.dropna(subset=["lat", "lon"]).sort_values("valid_to_sy").groupby("school_id").last()
    pts = gpd.GeoDataFrame(
        {"school_id": sp.index},
        geometry=gpd.points_from_xy(sp["lon"], sp["lat"]),
        crs="EPSG:4326",
    ).to_crs(CRS_WORK)
    j = gpd.sjoin(pts, units[["unit_id", "unit_type", "name", "geometry"]], predicate="within")
    out = pd.DataFrame(j.drop(columns=["geometry", "index_right"]))
    out["status"] = "derived"
    out["method"] = "school_location_point_in_polygon_v1"
    out["source_id"] = "school_parcel+" + out["unit_type"].map(
        {t: (CITY_LAYERS.get(t) or LEGISLATIVE[t])[0] for t in PLACE_TYPES}
    )
    return out.sort_values(["school_id", "unit_type"]).reset_index(drop=True)
