"""School locations to City parcels (PWD), giving each school site an OPA account number.

For each distinct school location (from the district's GPS field), ask the City's parcel
service for parcels within SEARCH_METERS and pick the parcel that contains the point, or else
the nearest one. Responses are archived untouched in raw/city_pwd_parcels/ with a hash.

This is a derived link (status `derived`) with a confidence label:
  high    point falls inside the parcel
  medium  nearest parcel within 25 m
  low     nearest parcel 25 to 100 m away (check by hand before relying on it)

For district-run schools, a School District-owned parcel within OWNER_PREFERENCE_METERS beats a
closer parcel owned by someone else: the district's points often sit in the street, and the
nearest parcel is then a neighboring rowhouse. Those matches are labeled `owner_preferred`.

A campus can span several parcels; this records only the one at the district's point.
"""

import hashlib
import json
import time
from datetime import UTC, datetime

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, shape

from . import CORE, RAW, USER_AGENT
from .fetch import _write_downloads, read_downloads
from .identity import _runs

SERVICE = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/PWD_PARCELS/FeatureServer/0"
)
SEARCH_METERS = 100
OWNER_PREFERENCE_METERS = 50
DISTRICT_OWNER = "SCHOOL DIST"
FIELDS = "parcelid,brt_id,address,owner1,owner2,gross_area"
CACHE_DIR = RAW / "city_pwd_parcels"
CRS_WORK = "EPSG:2272"
FEET_TO_M = 0.3048


def school_sites(attr: pd.DataFrame) -> pd.DataFrame:
    """One row per school x location x run of consecutive years at that location."""
    a = attr.dropna(subset=["lat", "lon"]).copy()
    a["lat"], a["lon"] = a["lat"].round(6), a["lon"].round(6)
    rows = []
    for (sid, lat, lon), g in a.groupby(["school_id", "lat", "lon"]):
        for first, last in _runs(g["sy"].tolist()):
            rows.append(
                {
                    "school_id": sid,
                    "lat": lat,
                    "lon": lon,
                    "valid_from_sy": first,
                    "valid_to_sy": last,
                }
            )
    return pd.DataFrame(rows)


def _key(lat: float, lon: float) -> str:
    return f"{lat:.6f},{lon:.6f}"


def load_cache() -> dict:
    cache = {}
    for path in sorted(CACHE_DIR.glob("point_queries_*.json")):
        cache.update(json.loads(path.read_text()))
    return cache


def query_points(points: list[tuple[float, float]], pause: float = 0.3) -> dict:
    """Query only points not already archived; write the new answers to a new dated file."""
    cache = load_cache()
    todo = [p for p in points if _key(*p) not in cache]
    if not todo:
        return cache
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    new = {}
    for lat, lon in todo:
        resp = session.get(
            f"{SERVICE}/query",
            params={
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "distance": SEARCH_METERS,
                "units": "esriSRUnit_Meter",
                "outFields": FIELDS,
                "returnGeometry": "true",
                "outSR": 2272,
                "f": "geojson",
            },
            timeout=60,
        )
        resp.raise_for_status()
        new[_key(lat, lon)] = resp.json()
        time.sleep(pause)
    now = datetime.now(UTC)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"point_queries_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    body = json.dumps(new, sort_keys=True).encode()
    path.write_bytes(body)
    downloads = read_downloads()
    downloads.append(
        {
            "source_key": "city_pwd_parcels",
            "url": SERVICE,
            "local_path": str(path.relative_to(RAW.parent)),
            "retrieved_at_utc": now.isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "etag": "",
            "last_modified": "",
        }
    )
    _write_downloads(downloads)
    cache.update(new)
    return cache


def _owner(props: dict) -> str:
    return " ".join(o for o in [props.get("owner1"), props.get("owner2")] if o)


def best_parcel(lat: float, lon: float, answer: dict, district_run: bool = False) -> dict:
    feats = answer.get("features") or []
    if not feats:
        return {"match": "none"}
    pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(CRS_WORK).iloc[0]
    scored = []
    for f in feats:
        geom = shape(f["geometry"])
        scored.append(
            (0.0 if geom.contains(pt) else geom.distance(pt) * FEET_TO_M, f["properties"])
        )
    dist, props = min(scored, key=lambda s: s[0])
    match = "contains" if dist == 0 else "nearest"
    if district_run and DISTRICT_OWNER not in _owner(props).upper():
        owned = [s for s in scored if DISTRICT_OWNER in _owner(s[1]).upper()]
        owned = [s for s in owned if s[0] <= OWNER_PREFERENCE_METERS]
        if owned:
            dist, props = min(owned, key=lambda s: s[0])
            match = "owner_preferred"
    confidence = "high" if dist == 0 else "medium" if dist <= 25 else "low"
    return {
        "match": match,
        "distance_m": round(dist, 1),
        "confidence": confidence,
        "pwd_parcel_id": props.get("parcelid"),
        "opa_account": props.get("brt_id"),
        "parcel_address": props.get("address"),
        "parcel_owner": _owner(props),
        "candidates_within_100m": len(feats),
    }


def build_school_parcel(attr: pd.DataFrame) -> pd.DataFrame:
    sites = school_sites(attr)
    cache = query_points(sorted({(r.lat, r.lon) for r in sites.itertuples()}))
    gov = attr.sort_values("sy").groupby("school_id")["governance"].last()
    matched = [
        best_parcel(r.lat, r.lon, cache[_key(r.lat, r.lon)], gov.get(r.school_id) == "District")
        for r in sites.itertuples()
    ]
    out = pd.concat([sites, pd.DataFrame(matched)], axis=1)
    out["needs_review"] = (out["school_id"].map(gov) == "District") & ~out["parcel_owner"].fillna(
        ""
    ).str.upper().str.contains(DISTRICT_OWNER)
    out["status"] = "derived"
    out["method"] = f"pwd_point_query_{SEARCH_METERS}m_owner_pref_v2"
    out["source_id"] = "city_pwd_parcels"
    return out


def write_school_parcel(df: pd.DataFrame) -> None:
    df.to_parquet(CORE / "school_parcel.parquet", index=False)
    df.to_csv(CORE / "school_parcel.csv", index=False)
