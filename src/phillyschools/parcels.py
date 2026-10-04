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

Reviewed fixes live in corrections/school_parcel.csv (committed) and are applied on every build:
`replace` swaps in the reviewed parcel, `confirm` accepts the match as is (for example a school
in a City-owned building), `unresolved` keeps the review flag. The City's service sometimes
answers HTTP 200 with an error body; those answers are retried and never cached.
"""

import hashlib
import json
import time
from datetime import UTC, datetime

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, shape

from . import CORE, RAW, ROOT, USER_AGENT
from .fetch import append_download
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
CORRECTIONS = ROOT / "corrections" / "school_parcel.csv"


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


def _ok(answer: dict) -> bool:
    return "error" not in answer and "features" in answer


def load_cache() -> dict:
    """Archived answers, skipping error bodies so those points are asked again."""
    cache = {}
    for path in sorted(CACHE_DIR.glob("point_queries_*.json")):
        cache.update({k: v for k, v in json.loads(path.read_text()).items() if _ok(v)})
    return cache


def _ask(session: requests.Session, lat: float, lon: float, attempts: int = 3) -> dict | None:
    for i in range(attempts):
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
        if resp.status_code == 200 and _ok(resp.json()):
            return resp.json()
        time.sleep(5 * (i + 1))
    return None


def query_points(
    points: list[tuple[float, float]], pause: float = 0.3, offline: bool = False
) -> dict:
    """Query points not already archived; save new good answers to a new dated file."""
    cache = load_cache()
    todo = [] if offline else [p for p in points if _key(*p) not in cache]
    if not todo:
        return cache
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    new = {}
    for lat, lon in todo:
        answer = _ask(session, lat, lon)
        if answer is not None:
            new[_key(lat, lon)] = answer
        time.sleep(pause)
    if new:
        now = datetime.now(UTC)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_DIR / f"point_queries_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        body = json.dumps(new, sort_keys=True).encode()
        path.write_bytes(body)
        append_download(
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
    cache.update(new)
    return cache


def _owner(props: dict) -> str:
    return " ".join(o for o in [props.get("owner1"), props.get("owner2")] if o)


def best_parcel(lat: float, lon: float, answer: dict | None, district_run: bool = False) -> dict:
    if answer is None:
        return {"match": "query_error"}
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


def load_corrections() -> pd.DataFrame:
    if not CORRECTIONS.exists():
        return pd.DataFrame()
    return pd.read_csv(CORRECTIONS, dtype=str)


def apply_corrections(df: pd.DataFrame, corrections: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["correction_id"] = None
    out["review_note"] = None
    ids = ["pwd_parcel_id", "opa_account", "parcel_address", "parcel_owner", "match", "confidence"]
    for col in ids:
        out[col] = out[col].astype("object")
    out["pwd_parcel_id"] = out["pwd_parcel_id"].map(
        lambda v: None if pd.isna(v) else str(int(float(v)))
    )
    if corrections.empty:
        return out
    key = out["school_id"] + "|" + out["valid_from_sy"].astype(int).astype(str)
    for c in corrections.itertuples():
        hit = key == f"{c.school_id}|{int(c.valid_from_sy)}"
        if not hit.any():
            raise ValueError(f"correction {c.correction_id} matches no school site")
        out.loc[hit, "correction_id"] = c.correction_id
        out.loc[hit, "review_note"] = c.reason
        if c.action == "replace":
            out.loc[hit, ["pwd_parcel_id", "opa_account", "parcel_address", "parcel_owner"]] = [
                c.pwd_parcel_id,
                c.opa_account,
                c.parcel_address,
                c.parcel_owner,
            ]
            out.loc[hit, ["match", "confidence", "distance_m", "status"]] = [
                "corrected",
                "reviewed",
                None,
                "corrected",
            ]
            out.loc[hit, "needs_review"] = False
        elif c.action == "confirm":
            out.loc[hit, "confidence"] = "reviewed"
            out.loc[hit, "needs_review"] = False
        elif c.action == "unresolved":
            out.loc[hit, "needs_review"] = True
        else:
            raise ValueError(f"unknown correction action {c.action}")
    return out


def build_school_parcel(attr: pd.DataFrame, offline: bool = False) -> pd.DataFrame:
    sites = school_sites(attr)
    cache = query_points(sorted({(r.lat, r.lon) for r in sites.itertuples()}), offline=offline)
    gov = attr.sort_values("sy").groupby("school_id")["governance"].last()
    matched = [
        best_parcel(r.lat, r.lon, cache.get(_key(r.lat, r.lon)), gov.get(r.school_id) == "District")
        for r in sites.itertuples()
    ]
    out = pd.concat([sites, pd.DataFrame(matched)], axis=1)
    out["needs_review"] = (out["school_id"].map(gov) == "District") & ~out["parcel_owner"].fillna(
        ""
    ).str.upper().str.contains(DISTRICT_OWNER)
    out["status"] = "derived"
    out["method"] = f"pwd_point_query_{SEARCH_METERS}m_owner_pref_v3"
    out["source_id"] = "city_pwd_parcels"
    return apply_corrections(out, load_corrections())


def write_school_parcel(df: pd.DataFrame) -> None:
    df.to_parquet(CORE / "school_parcel.parquet", index=False)
    df.to_csv(CORE / "school_parcel.csv", index=False)
