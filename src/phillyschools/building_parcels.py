"""Find the City parcel (OPA account) for buildings whose address does not match a parcel's.

The district's street address is often not the parcel's address (a school on a corner lot is
listed on one street and the parcel on the other). The fix is to locate the building, then ask
the City which parcel it sits on, as for the school parcels:

  1. Geocode the address with the Census Bureau's public geocoder (batch, no key).
  2. Query the City's parcel layer around that point and take the parcel containing it,
     preferring a School District-owned parcel within 50 m (same rules as school parcels).

Every answer is archived under raw/ and recorded in sources/downloads.csv, so the build is
repeatable offline. A match carries its method and distance; low-confidence matches are held
for review rather than written.
"""

import csv
import hashlib
import io
import json
import re
import time
from datetime import UTC, datetime

import pandas as pd
import requests

from . import RAW, USER_AGENT
from .fetch import append_download
from .parcels import _key, best_parcel, query_points

GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
OPA_SQL = "https://phl.carto.com/api/v2/sql"
CACHE_DIR = RAW / "census_geocoder"
OPA_DIR = RAW / "city_opa_properties"
BATCH = 500


def _street_line(address: str) -> str:
    """The address the geocoder wants: number and street only."""
    return re.sub(r"\s+", " ", str(address)).strip().rstrip(",.")


def load_geocode_cache() -> dict:
    cache = {}
    for path in sorted(CACHE_DIR.glob("geocode_*.json")):
        cache.update(json.loads(path.read_text()))
    return cache


def geocode(addresses: list[tuple[str, str | None]], offline: bool = False) -> dict:
    """{address: {lat, lon, matched, matchtype}} for each (street, zip); archives new answers."""
    cache = load_geocode_cache()
    todo = [] if offline else [(a, z) for a, z in addresses if a not in cache]
    for start in range(0, len(todo), BATCH):
        chunk = todo[start : start + BATCH]
        buf = io.StringIO()
        w = csv.writer(buf)
        for i, (street, zp) in enumerate(chunk):
            w.writerow([i, _street_line(street), "Philadelphia", "PA", zp or ""])
        body = None
        for attempt in range(3):
            resp = requests.post(
                GEOCODER,
                files={"addressFile": ("addresses.csv", buf.getvalue())},
                data={"benchmark": "Public_AR_Current"},
                headers={"User-Agent": USER_AGENT},
                timeout=300,
            )
            if resp.status_code == 200 and resp.text.strip():
                body = resp.text
                break
            time.sleep(10 * (attempt + 1))
        if body is None:
            continue
        new = {}
        for row in csv.reader(io.StringIO(body)):
            if len(row) < 5:
                continue
            idx = int(row[0])
            street = chunk[idx][0]
            if row[2] == "Match" and len(row) >= 6 and row[5]:
                lon, lat = (float(x) for x in row[5].split(","))
                new[street] = {"lat": lat, "lon": lon, "matched": row[4], "matchtype": row[3]}
            else:
                new[street] = {"lat": None, "lon": None, "matched": None, "matchtype": row[2]}
        now = datetime.now(UTC)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_DIR / f"geocode_{now.strftime('%Y%m%dT%H%M%S')}_{start}.json"
        blob = json.dumps(new, sort_keys=True).encode()
        path.write_bytes(blob)
        append_download(
            {
                "source_key": "census_geocoder",
                "url": GEOCODER,
                "local_path": str(path.relative_to(RAW.parent)),
                "retrieved_at_utc": now.isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "bytes": len(blob),
                "etag": "",
                "last_modified": "",
            }
        )
        cache.update(new)
    return cache


def parcels_by_geocode(addresses: list[tuple[str, str | None]], offline: bool = False) -> dict:
    """{address: parcel dict} using geocoded points and the City parcel layer."""
    coded = geocode(addresses, offline=offline)
    points = {
        a: (coded[a]["lat"], coded[a]["lon"])
        for a, _ in addresses
        if a in coded and coded[a].get("lat") is not None
    }
    answers = query_points(sorted(set(points.values())), offline=offline)
    out = {}
    for a, (lat, lon) in points.items():
        best = best_parcel(lat, lon, answers.get(_key(lat, lon)), district_run=True)
        out[a] = {**best, "lat": lat, "lon": lon, "geocode": coded[a]["matchtype"]}
    return out


STOP = {
    "SCHOOL",
    "ELEMENTARY",
    "MIDDLE",
    "HIGH",
    "THE",
    "OF",
    "AT",
    "AND",
    "ANNEX",
    "CENTER",
    "ACADEMY",
    "CHARTER",
    "PHILA",
    "PHILADELPHIA",
    "LLC",
    "INC",
    "CHURCH",
    "BLDG",
    "BUILDING",
}


def _stems(text: str) -> set[str]:
    """First four letters of each significant word, so PAULS matches PAUL'S and BAPT BAPTIST."""
    words = re.sub(r"[^A-Z ]", " ", str(text).upper()).split()
    return {w[:4] for w in words if w not in STOP and len(w) >= 4}


def judge(
    result: dict,
    building_name: str,
    building_address: str,
    loose_overlap,
    near_number: bool = False,
) -> str | None:
    """The reason to trust a geocoded parcel, or None to hold it for review.

    The geocoded point sits on the street frontage, so the nearest parcel can be a neighbor.
    Accept a parcel whose address range overlaps the building's; one whose owner shares two
    or more name words with the building (a school in a church or lease); or a School
    District-owned parcel at the point or within 50 m (a corner school listed on the other
    street), which is the rule that located the school parcels. Also: a geocoded point inside
    a public parcel, or a parcel a few doors from the address (an annex in a neighboring
    church), each labeled by method."""
    if not result.get("opa_account"):
        return None
    if loose_overlap(building_address, result.get("parcel_address")):
        return "geocode_address_overlap"
    owner = str(result.get("parcel_owner") or "")
    if len(_stems(owner) & _stems(building_name)) >= 2:
        return "geocode_owner_name"
    if "SCHOOL DIST" in owner.upper() and (result.get("distance_m") or 0) <= 50:
        return "geocode_school_owned"
    public = re.search(r"SCHOOL DIST|CITY OF PHILA|PHILA CITY", owner.upper())
    if (
        result.get("match") == "contains"
        and result.get("geocode") in {"Exact", "Non_Exact"}
        and public
    ):
        return "geocode_contains_public"  # the geocoded point is inside a public parcel
    if near_number and (result.get("distance_m") or 99) <= 10:
        return "geocode_next_door"
    return None


def as_frame(results: dict) -> pd.DataFrame:
    return pd.DataFrame.from_dict(results, orient="index").rename_axis("address").reset_index()


def _opa_where(num: int, core: str) -> str:
    """Parcels on the whole block (the number without its last two digits), because a parcel can
    be listed as a range ("2101-27 EASTBURN AVE") that a prefix on the exact number misses."""
    core = core.replace("'", "")
    block = str(num)[:-2] or str(num)[0]
    return (
        "select parcel_number, location, owner_1, owner_2, building_code_description "
        f"from opa_properties_public where location ilike '{block}%' and location ilike '%{core}%'"
    )


def load_opa_cache() -> dict:
    cache = {}
    for path in sorted(OPA_DIR.glob("address_queries_*.json")):
        cache.update(json.loads(path.read_text()))
    return cache


def opa_by_address(addresses: list[str], offline: bool = False, pause: float = 0.3) -> dict:
    """OPA property records whose location starts with the address number and has the street.

    This is the City's assessment dataset, independent of the parcel layer, and finds
    accounts the parcel layer's address misses. Answers are archived like the others."""
    from .buildings import _core, split_address

    cache = load_opa_cache()
    todo = [] if offline else sorted({a for a in addresses if f"{a}|block" not in cache})
    if not todo:
        return cache
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    new = {}
    for addr in todo:
        parsed = split_address(addr)
        if not parsed:
            continue
        for attempt in range(3):
            resp = session.get(
                OPA_SQL, params={"q": _opa_where(parsed[0], _core(parsed[2]))}, timeout=90
            )
            if resp.status_code == 200 and "rows" in resp.json():
                new[f"{addr}|block"] = resp.json()["rows"]
                break
            time.sleep(5 * (attempt + 1))
        time.sleep(pause)
    if new:
        now = datetime.now(UTC)
        OPA_DIR.mkdir(parents=True, exist_ok=True)
        path = OPA_DIR / f"address_queries_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        blob = json.dumps(new, sort_keys=True).encode()
        path.write_bytes(blob)
        append_download(
            {
                "source_key": "city_opa_properties",
                "url": OPA_SQL,
                "local_path": str(path.relative_to(RAW.parent)),
                "retrieved_at_utc": now.isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "bytes": len(blob),
                "etag": "",
                "last_modified": "",
            }
        )
    cache.update(new)
    return cache


STREET_DIR = RAW / "city_pwd_parcels"


def load_street_cache() -> dict:
    cache = {}
    for path in sorted(STREET_DIR.glob("street_queries_*.json")):
        cache.update(json.loads(path.read_text()))
    return cache


def school_owned_on_street(cores: list[str], offline: bool = False, pause: float = 0.3) -> dict:
    """{street core: School District-owned parcels on streets with that name} from the City layer."""
    from .parcels import FIELDS, SERVICE

    cache = load_street_cache()
    todo = [] if offline else sorted({c for c in cores if c not in cache})
    if not todo:
        return cache
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    new = {}
    for core in todo:
        where = f"owner1 LIKE 'SCHOOL DIST%' AND address LIKE '%{core.replace(chr(39), '')}%'"
        for attempt in range(3):
            resp = session.get(
                f"{SERVICE}/query",
                params={
                    "where": where,
                    "outFields": FIELDS,
                    "returnGeometry": "false",
                    "f": "json",
                },
                timeout=60,
            )
            body = resp.json() if resp.status_code == 200 else {}
            if "features" in body:
                new[core] = [f["attributes"] for f in body["features"]]
                break
            time.sleep(5 * (attempt + 1))
        time.sleep(pause)
    if new:
        now = datetime.now(UTC)
        path = STREET_DIR / f"street_queries_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        blob = json.dumps(new, sort_keys=True).encode()
        path.write_bytes(blob)
        append_download(
            {
                "source_key": "city_pwd_parcels",
                "url": SERVICE,
                "local_path": str(path.relative_to(RAW.parent)),
                "retrieved_at_utc": now.isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "bytes": len(blob),
                "etag": "",
                "last_modified": "",
            }
        )
    cache.update(new)
    return cache
