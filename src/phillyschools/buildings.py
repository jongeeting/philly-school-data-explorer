"""Buildings: one row per physical building, and which schools were in it when.

Tables (core/):
  building         building_id, name, kind, address, year built, City parcel (OPA) when known
  building_xwalk   building_id x outside key (asbestos code, assessment part code, lead and
                   water folders, street address) with how the link was made
  school_building  school_id x building_id x valid years: from the street address in each
                   year's district school list, so moves and co-locations show up

A building is a cluster of records from five sources that point at the same place:
  master list     a school's street address in each year's district list
  AHERA report    4-digit building code and the cover page's name, address, and year built
  assessment      FCA building part codes (B + 3 digits + sequence; sequence 001 is the
                  main building, 002 and up are annexes) and the site's street address
  lead folder     name, street address, and ZIP in the folder name
  water folder    site name; schools are linked by name, and a street address when named

Records merge when they share an AHERA code (an assessment part maps to a code by
code[1:4] + (sequence - 1), with hand fixes in corrections/building_links.csv) or when their
street address ranges overlap and they are the same kind of structure. Annexes, little
school houses, field houses, pools, garages, and offices are kept apart from the main
building even at the same address. Records with no address join their school's main building.

IDs are minted into registry/building_id_registry.csv and never reused or renumbered.
"""

import hashlib
import json
import re
import time
from collections import defaultdict
from datetime import UTC, datetime

import pandas as pd
import requests

from . import CORE, RAW, ROOT, USER_AGENT
from .envresults import (
    folder_address,
    pdf_text,
    school_index,  # noqa: F401  (kept for callers that want the same name matching)
    split_address,
)
from .fetch import append_download
from .parcels import FIELDS, SERVICE

REGISTRY_FILE = ROOT / "registry" / "building_id_registry.csv"
LINKS_FILE = ROOT / "corrections" / "building_links.csv"
COVER = re.compile(
    r"\n[ \t]*([^\n]+?)[ \t]*\n[ \t]*ULCS[ \t]*#?[ \t]*:?[ \t]*(\d{4})[ \t]*\n"
    r"[ \t]*(\d[^\n]+?)[ \t]*\n[ \t]*Philadelphia,?[ \t]*(?:PA|Pennsylvania)[ \t]*(\d{5})"
    r"(?:[ \t]*\n[ \t]*Year Built:[ \t]*(\d{4}))?",
    re.IGNORECASE,
)
KINDS = [
    ("little_school_house", r"little school house|\blsh\b"),
    ("annex", r"annex"),
    ("field_house", r"field ?house|\bfield\b|stands|restroom"),
    ("pool", r"\bpool\b"),
    ("garage_or_barn", r"garage|\bbarn\b|bus "),
    ("office_or_center", r"admin|security|education center|community center|head start|police"),
    ("farm_or_outdoor", r"\bfarm\b|environmental center|\bhouse \("),
]


def kind_of(name: str) -> str:
    n = str(name).lower()
    for kind, pattern in KINDS:
        if re.search(pattern, n):
            return kind
    return "school_building"


# ---------------------------------------------------------------- claims


def master_claims() -> pd.DataFrame:
    """A school's street address in each district list year (2019 on, where the CSV exists)."""
    reg = pd.read_csv(ROOT / "registry" / "school_id_registry.csv", dtype=str)
    to_id = reg.set_index("ulcs")["school_id"]
    rows = []
    for path in sorted((RAW / "sdp_master_school_list").glob("*Master School List*.csv")):
        d = pd.read_csv(path, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
        d.columns = [c.strip() for c in d.columns]
        if "Street Address" not in d:
            continue
        sy = int(re.search(r"\d{4}-(\d{4})", path.name).group(1))
        for u, name, addr, zp in zip(
            d["ULCS Code"], d["Publication Name"], d["Street Address"], d["Zip Code"], strict=True
        ):
            sid = to_id.get(str(u).strip())
            if sid and split_address(addr):
                rows.append(
                    {"school_id": sid, "sy": sy, "name": name, "address": addr.strip(), "zip": zp}
                )
    return pd.DataFrame(rows)


ACRONYMS = {"HS", "MS", "ES", "PA", "LSH", "KIPP", "AMY", "II", "III"}


def tidy_name(name: str) -> str:
    """Title case that keeps apostrophes and acronyms right ("PAUL'S BAPTIST CHURCH")."""
    words = []
    for w in str(name).split():
        up = re.sub(r"[^A-Za-z]", "", w).upper()
        words.append(
            w.upper()
            if up in ACRONYMS
            else re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), w)
        )
    return " ".join(words)


def cover_info(path) -> dict:
    t = pdf_text(RAW.parent / path, 1, 3)
    m = COVER.search(t)
    if not m:
        return {}
    name, _ulcs, addr, zp, built = m.groups()
    return {
        "cover_name": tidy_name(name),
        "address": addr.strip(),
        "zip": zp,
        "year_built": int(built) if built else None,
    }


def _cover_or_folder(cover: str | None, folder: str) -> str:
    """A cover name that wrapped onto a second line reads as one short word: use the folder."""
    if cover and len(cover.split()) >= 2:
        return cover
    return tidy_name(folder)


def ahera_claims() -> pd.DataFrame:
    a = pd.read_parquet(CORE / "building_asbestos.parquet")
    latest = a[a["is_latest"]]
    rows = []
    for r in latest.itertuples():
        info = cover_info(r.file)
        rows.append(
            {
                "source": "ahera",
                "key": r.building_code,
                "name": _cover_or_folder(info.get("cover_name"), r.site_folder),
                "folder": r.site_folder,
                "address": info.get("address"),
                "zip": info.get("zip"),
                "year_built": info.get("year_built"),
                "school_ids": r.school_id,
                "ahera_code": r.building_code,
            }
        )
    return pd.DataFrame(rows)


def load_link_fixes() -> pd.DataFrame:
    if LINKS_FILE.exists():
        return pd.read_csv(LINKS_FILE, dtype=str)
    return pd.DataFrame(columns=["link_id", "source", "key", "ahera_code", "reason"])


def fca_claims(fixes: pd.DataFrame) -> pd.DataFrame:
    parts = pd.read_parquet(CORE / "facility_condition_part.parquet")
    site = pd.read_parquet(CORE / "facility_condition.parquet").set_index("site_code")
    fix = {
        r.key: r.ahera_code for r in fixes[fixes["source"] == "fca"].itertuples() if r.ahera_code
    }
    rows = []
    for r in parts[parts["part_code"].str[0] == "B"].itertuples():
        seq = int(r.part_code[4:])
        code = fix.get(r.part_code) or (r.part_code[1:4] + str(seq - 1) if seq < 100 else None)
        s = site.loc[r.site_code]
        main = seq == 1
        rows.append(
            {
                "source": "fca",
                "key": r.part_code,
                "name": r.part_name,
                "folder": r.part_name,
                "address": s["address"]
                if main
                else None,  # the site address is the main building's
                "zip": None,
                "year_built": s["year_built"] if main and pd.notna(s["year_built"]) else None,
                "school_ids": r.school_ids,
                "ahera_code": code,
                "site_code": r.site_code,
            }
        )
    return pd.DataFrame(rows)


def lead_claims() -> pd.DataFrame:
    d = pd.read_parquet(CORE / "school_lead_paint.parquet")
    rows = []
    for folder, g in d.groupby("site_folder"):
        parts = folder.split("_")
        rows.append(
            {
                "source": "lead",
                "key": folder,
                "name": parts[0],
                "folder": folder,
                "address": folder_address(folder) or None,
                "zip": parts[2] if len(parts) >= 3 else None,
                "year_built": None,
                "school_ids": g["school_id"].dropna().iloc[0]
                if g["school_id"].notna().any()
                else None,
            }
        )
    return pd.DataFrame(rows)


def water_claims() -> pd.DataFrame:
    d = pd.read_parquet(CORE / "school_water_lead.parquet")
    rows = []
    for folder, g in d.groupby("site_folder"):
        street = re.search(r"\((\d+[^)]*)\)", folder)
        name = re.sub(r"\s*Site \d+.*$|\s*\(.*$", "", folder).strip()
        rows.append(
            {
                "source": "water",
                "key": folder,
                "name": name,
                "folder": folder,
                "address": street.group(1) if street else None,
                "zip": None,
                "year_built": None,
                "school_ids": g["school_id"].dropna().iloc[0]
                if g["school_id"].notna().any()
                else None,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- clustering


class UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, i: int) -> int:
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def _overlap(a: tuple, b: tuple) -> bool:
    return a[2] == b[2] and a[0] <= b[1] and b[0] <= a[1]


NEAR_NUMBERS = 10  # one school's two address numbers this close on a street are one building
DIRECTIONS = {"N", "S", "E", "W"}
SUFFIXES = {"ST", "AVE", "RD", "LN", "DR", "BLVD", "PK", "PL", "WAY", "CT", "TER", "PKWY"}
SUITE = re.compile(
    r"\s*[-,]?\s*(?:\d+(?:ST|ND|RD|TH)\s+)?(?:FLR|FLOOR|SUITE|STE|RM|ROOM|UNIT|BLDG|BUILDING)\b.*$",
    re.IGNORECASE,
)


def clean_address(address: str) -> str:
    """Drop suite, floor, and room text and stray punctuation before parsing."""
    a = SUITE.sub("", str(address).split(",")[0])  # text after a comma is a name or suite
    return re.sub(r"[.\s]+$", "", a).strip()


def street_parts(street: str) -> tuple[str | None, str]:
    words = street.split()
    direction = words[0] if words and words[0] in DIRECTIONS else None
    core = " ".join(w for w in words if w not in DIRECTIONS and w not in SUFFIXES)
    return direction, core


def _loose_overlap(a: tuple, b: tuple) -> bool:
    """Same street name (suffix ignored; direction must agree only when both give one)."""
    (da, ca), (db, cb) = street_parts(a[2]), street_parts(b[2])
    return ca == cb and (da is None or db is None or da == db) and a[0] <= b[1] and b[0] <= a[1]


def cluster(claims: pd.DataFrame) -> pd.Series:
    """Cluster index per claim: shared AHERA code, or overlapping address and same kind."""
    c = claims.reset_index(drop=True)
    uf = UnionFind(len(c))
    by_code = defaultdict(list)
    for i, code in enumerate(c["ahera_code"]):
        if isinstance(code, str):
            by_code[code].append(i)
    for idx in by_code.values():
        for j in idx[1:]:
            uf.union(idx[0], j)
    parsed = [split_address(clean_address(a)) if isinstance(a, str) else None for a in c["address"]]
    kinds = [kind_of(n) for n in c["name"]]
    schools = [set(str(x).split(", ")) if isinstance(x, str) else set() for x in c["school_ids"]]
    buckets = defaultdict(list)
    for i, p in enumerate(parsed):
        if p:
            buckets[(street_parts(p[2])[1], kinds[i])].append(i)
    for idx in buckets.values():
        for x in range(len(idx)):
            for y in range(x + 1, len(idx)):
                a, b = parsed[idx[x]], parsed[idx[y]]
                near_same_school = (
                    bool(schools[idx[x]] & schools[idx[y]])
                    and street_parts(a[2]) == street_parts(b[2])
                    and abs(a[0] - b[0]) <= NEAR_NUMBERS
                )
                if _loose_overlap(a, b) or near_same_school:
                    uf.union(idx[x], idx[y])
    return pd.Series([uf.find(i) for i in range(len(c))], index=c.index)


# ---------------------------------------------------------------- registry


def load_registry() -> pd.DataFrame:
    if REGISTRY_FILE.exists():
        return pd.read_csv(REGISTRY_FILE, dtype=str)
    return pd.DataFrame(columns=["building_id", "anchor_type", "anchor_value", "minted_on"])


def anchors_for(group: pd.DataFrame) -> list[tuple[str, str]]:
    out = []
    for code in sorted(set(group["ahera_code"].dropna())):
        out.append(("ahera_code", code))
    for key in sorted(group.loc[group["source"] == "fca", "key"]):
        out.append(("fca_part_code", key))
    for key in sorted(group.loc[group["source"].isin(["lead", "water"]), "key"]):
        out.append(("site_folder", key))
    for key in sorted(group.loc[group["source"] == "master", "key"]):
        out.append(("master_address", key))
    return out


def assign_ids(
    groups: dict[int, pd.DataFrame], registry: pd.DataFrame
) -> tuple[dict, pd.DataFrame]:
    """Reuse an ID when any anchor is already registered; mint a new one otherwise."""
    known = {(r.anchor_type, r.anchor_value): r.building_id for r in registry.itertuples()}
    top = max((int(b.split("_")[1]) for b in registry["building_id"]), default=0)
    today = datetime.now(UTC).date().isoformat()
    added, ids, used = [], {}, set()
    for cid in sorted(groups):
        anchors = anchors_for(groups[cid])
        found = [b for b in sorted({known[a] for a in anchors if a in known}) if b not in used]
        if found:  # a split cluster must not reuse an ID another cluster already took
            bid = found[0]
        else:
            top += 1
            bid = f"bld_{top:05d}"
        ids[cid] = bid
        used.add(bid)
        for a in anchors:
            if a not in known:
                known[a] = bid
                added.append(
                    {
                        "building_id": bid,
                        "anchor_type": a[0],
                        "anchor_value": a[1],
                        "minted_on": today,
                    }
                )
    reg = pd.concat([registry, pd.DataFrame(added)], ignore_index=True) if added else registry
    return ids, reg


# ---------------------------------------------------------------- build


def _best(group: pd.DataFrame, col: str):
    for source in ["master", "ahera", "fca", "lead", "water"]:
        vals = group.loc[(group["source"] == source) & group[col].notna(), col]
        if len(vals):
            return vals.iloc[0], source
    return None, None


def build_buildings(offline: bool = False) -> dict:
    fixes = load_link_fixes()
    master = master_claims()
    school_names = pd.read_parquet(CORE / "school.parquet").set_index("school_id")["current_name"]
    # one master claim per school and distinct address (years kept for school_building)
    mc = (
        master.sort_values("sy")
        .groupby(["school_id", "address"], as_index=False)
        .agg(
            name=("name", "last"),
            zip=("zip", "last"),
            first_sy=("sy", "min"),
            last_sy=("sy", "max"),
        )
    )
    master_rows = pd.DataFrame(
        {
            "source": "master",
            "key": mc["school_id"] + "|" + mc["address"],
            "name": mc["name"],
            "folder": mc["name"],
            "address": mc["address"],
            "zip": mc["zip"],
            "year_built": None,
            "school_ids": mc["school_id"],
            "ahera_code": None,
            "first_sy": mc["first_sy"],
            "last_sy": mc["last_sy"],
        }
    )
    claims = pd.concat(
        [master_rows, ahera_claims(), fca_claims(fixes), lead_claims(), water_claims()],
        ignore_index=True,
    )
    for col in ["ahera_code", "site_code"]:
        if col not in claims:
            claims[col] = None
    claims["cluster"] = cluster(claims)

    # records with no address join their school's main building
    main_cluster = {}
    for r in master_rows.assign(
        cl=claims.loc[claims["source"] == "master", "cluster"].values
    ).itertuples():
        main_cluster.setdefault(r.school_ids, r.cl)  # earliest address; replaced below by latest
    latest = (
        mc.sort_values("last_sy")
        .groupby("school_id")
        .tail(1)
        .set_index("school_id")["address"]
        .to_dict()
    )
    key_cluster = dict(zip(claims["key"], claims["cluster"], strict=True))
    for sid, addr in latest.items():
        main_cluster[sid] = key_cluster.get(f"{sid}|{addr}", main_cluster.get(sid))
    attached = []
    for i, r in claims.iterrows():
        main_code = r["source"] == "ahera" and str(r["key"]).endswith("0")
        if isinstance(r["address"], str) or r["source"] == "master":
            continue
        if r["source"] == "ahera" and not main_code:
            continue
        first = str(r["school_ids"]).split(", ")[0] if isinstance(r["school_ids"], str) else None
        if first in main_cluster and kind_of(r["name"]) == "school_building":
            claims.at[i, "cluster"] = main_cluster[first]
            attached.append(i)
    claims["link_method"] = "address_or_code"
    claims.loc[attached, "link_method"] = "school_main_building"

    groups = {cid: g for cid, g in claims.groupby("cluster")}
    registry = load_registry()
    ids, registry = assign_ids(groups, registry)
    claims["building_id"] = claims["cluster"].map(ids)

    opa = _parcels()
    school_pt = _school_point_parcels(claims, ids)
    addresses = [
        a
        for a in claims["address"].dropna().unique()
        if split_address(a) and not _parcel_for(a, opa)
    ][:0]  # filled below, only for buildings the school points do not resolve
    unresolved = [
        g["address"].dropna().iloc[0]
        for cid, g in groups.items()
        if ids[cid] not in school_pt and g["address"].notna().any()
    ]
    city = query_addresses(sorted(set(addresses + unresolved)), offline=offline)
    rows = []
    for cid, g in groups.items():
        name, _ = _best(g, "name")
        # a building takes the name on its AHERA cover, else the most recent school's
        a_name, _ = _best(g[g["source"] == "ahera"], "name")
        name = a_name or name
        addr, addr_src = _best(g, "address")
        z, _ = _best(g, "zip")
        yb, _ = _best(g, "year_built")
        kinds = {kind_of(n) for n in g["name"]}
        kind = next((k for k in kinds if k != "school_building"), "school_building")
        parcel = (
            school_pt.get(ids[cid])
            or _parcel_for(addr, opa)
            or (_parcel_from_city(addr, city) if addr else {})
        )
        rows.append(
            {
                "building_id": ids[cid],
                "building_name": name,
                "building_kind": kind,
                "address": addr,
                "address_source": addr_src,
                "zip": z,
                "year_built": yb,
                "opa_account": parcel.get("opa_account"),
                "parcel_address": parcel.get("parcel_address"),
                "parcel_owner": parcel.get("parcel_owner"),
                "parcel_match": parcel.get("match", "none"),
                "n_records": len(g),
                "sources": ", ".join(sorted(set(g["source"]))),
                "status": "derived",
                "source_id": "buildings:v1",
            }
        )
    building = pd.DataFrame(rows).sort_values("building_id").reset_index(drop=True)

    xwalk = claims.loc[
        claims["source"] != "master", ["building_id", "source", "key", "link_method"]
    ]
    xwalk = xwalk.rename(columns={"source": "key_type", "key": "key_value"})
    xwalk["key_type"] = xwalk["key_type"].map(
        {
            "ahera": "ahera_code",
            "fca": "fca_part_code",
            "lead": "lead_folder",
            "water": "water_folder",
        }
    )
    xwalk["source_id"] = "buildings:v1"
    ac = claims.loc[claims["source"] == "ahera", ["building_id", "key"]].rename(
        columns={"key": "x"}
    )
    del ac

    sb = _school_building(mc, claims, key_cluster, school_names)
    return {
        "building": building,
        "building_xwalk": xwalk.reset_index(drop=True),
        "school_building": sb,
        "claims": claims,
        "registry": registry,
    }


PARCEL_CACHE = RAW / "city_pwd_parcels"


def _core(street: str) -> str:
    """The distinctive word of a normalized street ('W HUNTING PARK AVE' -> 'HUNTING')."""
    words = [
        w for w in street.split() if w not in {"N", "S", "E", "W", "ST", "AVE", "RD", "LN", "DR"}
    ]
    return max(words, key=len) if words else street


def _address_key(address: str) -> str:
    a = split_address(address)
    return f"{a[0]}|{a[1]}|{a[2]}" if a else address


def load_address_cache() -> dict:
    cache = {}
    for path in sorted(PARCEL_CACHE.glob("address_queries_*.json")):
        cache.update(json.loads(path.read_text()))
    return cache


def query_addresses(addresses: list[str], pause: float = 0.3, offline: bool = False) -> dict:
    """City parcels whose address overlaps each building address; archived like point queries."""
    cache = load_address_cache()
    todo = [] if offline else sorted({a for a in addresses if _address_key(a) not in cache})
    if not todo:
        return cache
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    new = {}
    for addr in todo:
        lo, _hi, street = split_address(addr)
        where = f"address LIKE '{lo}%' AND address LIKE '%{_core(street).replace(chr(39), '')}%'"
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
                new[_address_key(addr)] = {"where": where, "features": body["features"]}
                break
            time.sleep(5 * (attempt + 1))
        time.sleep(pause)
    if new:
        now = datetime.now(UTC)
        path = PARCEL_CACHE / f"address_queries_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
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


def _parcel_from_city(address: str, cache: dict) -> dict:
    a = split_address(address)
    answer = cache.get(_address_key(address)) if a else None
    if not answer:
        return {}
    hits = []
    for f in answer["features"]:
        at = f["attributes"]
        pa = split_address(at.get("address") or "")
        if pa and _overlap(a, pa):
            hits.append(at)
    accounts = {h["brt_id"] for h in hits if h.get("brt_id")}
    if len(accounts) == 1:
        h = next(h for h in hits if h.get("brt_id"))
        owner = " ".join(o for o in [h.get("owner1"), h.get("owner2")] if o)
        return {
            "opa_account": h["brt_id"],
            "parcel_address": h["address"],
            "parcel_owner": owner or None,
            "match": "city_address_overlap",
        }
    if len(accounts) > 1:
        return {"match": "city_address_ambiguous"}
    return {}


def _school_point_parcels(claims: pd.DataFrame, ids: dict) -> dict:
    """A building's parcel from its schools' map points (the vetted school_parcel table).

    Only the years a school was listed at that address count: a school's parcel rows carry
    valid years, so a former address does not take the current parcel. If the schools there
    point at one parcel the building takes it; if they disagree it is left for review."""
    sp = pd.read_parquet(CORE / "school_parcel.parquet").dropna(subset=["opa_account"])
    by_school = {sid: g for sid, g in sp.groupby("school_id")}
    master = claims[claims["source"] == "master"].copy()
    master["school"] = master["key"].str.split("|").str[0]
    final_sy = master.groupby("school")["last_sy"].transform("max")
    seen = defaultdict(set)
    for r, final in zip(master.itertuples(), final_sy, strict=True):
        sid = r.school
        g = by_school.get(sid)
        if g is None:
            continue
        if len(g) == 1 and r.last_sy < final:
            continue  # one parcel on file: it belongs to the school's current address only
        hit = g[(g["valid_from_sy"] <= r.last_sy) & (g["valid_to_sy"] >= r.first_sy)]
        for h in hit.itertuples():
            seen[r.building_id].add((h.opa_account, h.parcel_address, h.parcel_owner))
    out = {}
    for bid, parcels in seen.items():
        if len({a for a, _, _ in parcels}) == 1:
            acct, addr, owner = min(parcels)
            out[bid] = {
                "opa_account": acct,
                "parcel_address": addr,
                "parcel_owner": owner,
                "match": "school_map_point",
            }
    return out


def _parcels() -> pd.DataFrame:
    p = pd.read_parquet(CORE / "school_parcel.parquet")
    p = p.dropna(subset=["opa_account"]).copy()
    p["parsed"] = [split_address(a) for a in p["parcel_address"]]
    return p.dropna(subset=["parsed"])


def _parcel_for(address, parcels: pd.DataFrame) -> dict:
    a = split_address(address) if isinstance(address, str) else None
    if not a:
        return {}
    hits = parcels[[_overlap(a, p) for p in parcels["parsed"]]]
    accounts = hits["opa_account"].unique()
    if len(accounts) == 1:
        return {
            "opa_account": accounts[0],
            "parcel_address": hits["parcel_address"].iloc[0],
            "match": "address_overlap",
        }
    if len(accounts) > 1:
        return {"match": "ambiguous"}
    return {}


def _school_building(mc, claims, key_cluster, school_names) -> pd.DataFrame:
    ids = dict(zip(claims["key"], claims["building_id"], strict=True))
    rows = []
    for r in mc.itertuples():
        bid = ids.get(f"{r.school_id}|{r.address}")
        rows.append(
            {
                "school_id": r.school_id,
                "building_id": bid,
                "valid_from_sy": int(r.first_sy),
                "valid_to_sy": int(r.last_sy),
                "role": "primary",
                "evidence": "district school list address",
                "status": "reported",
                "source_id": "sdp_master_school_list",
            }
        )
    sb = pd.DataFrame(rows)
    # a school whose list address moved between years gets one row per building and run
    sb = sb.groupby(["school_id", "building_id"], as_index=False).agg(
        valid_from_sy=("valid_from_sy", "min"),
        valid_to_sy=("valid_to_sy", "max"),
        role=("role", "first"),
        evidence=("evidence", "first"),
        status=("status", "first"),
        source_id=("source_id", "first"),
    )
    # environmental and assessment records that tie a school to another building (annexes)
    have = set(zip(sb["school_id"], sb["building_id"], strict=True))
    extra = []
    for r in claims[claims["source"].isin(["ahera", "fca", "lead", "water"])].itertuples():
        if not isinstance(r.school_ids, str):
            continue
        for sid in r.school_ids.split(", "):
            if (sid, r.building_id) in have:
                continue
            have.add((sid, r.building_id))
            extra.append(
                {
                    "school_id": sid,
                    "building_id": r.building_id,
                    "valid_from_sy": None,
                    "valid_to_sy": None,
                    "role": "other_building",
                    "evidence": f"{r.source} record",
                    "status": "derived",
                    "source_id": f"sdp_environmental:{r.source}"
                    if r.source != "fca"
                    else "sdp_facility_condition:fca_2020",
                }
            )
    if extra:
        sb = pd.concat([sb, pd.DataFrame(extra)], ignore_index=True)
    return sb.sort_values(["school_id", "building_id"]).reset_index(drop=True)


def write_buildings(t: dict) -> None:
    for name in ["building", "building_xwalk", "school_building"]:
        t[name].to_parquet(CORE / f"{name}.parquet", index=False)
        t[name].to_csv(CORE / f"{name}.csv", index=False)
    t["registry"].to_csv(REGISTRY_FILE, index=False)


# ---------------------------------------------------------------- building mart

MART_DOCS = {
    "building_id": "Permanent minted building ID (bld_NNNNN); never reused. Outside keys are in building_xwalk.",
    "building_name": "Name on the asbestos report cover, else the school list or folder name.",
    "building_kind": "school_building, annex, little_school_house, field_house, pool, garage_or_barn, office_or_center, or farm_or_outdoor, from the name.",
    "address": "Street address: the district school list first, else the asbestos report, assessment, or lead folder.",
    "zip": "ZIP code where a source gives one.",
    "year_built": "Year built from the asbestos report cover or the facility assessment.",
    "opa_account": "OPA account of the City parcel the building sits on, when matched; blank otherwise.",
    "parcel_address": "The City's address for that parcel.",
    "parcel_owner": "Owner of that parcel as the City records it.",
    "parcel_match": "How the parcel was found: school_map_point, address_overlap, city_address_overlap, or none.",
    "schools_current": "school_ids listed at this building in the most recent district list, comma-separated.",
    "n_schools_current": "Number of schools listed at this building in the most recent list.",
    "asbestos_items": "Confirmed or assumed asbestos-containing entries in the latest report's room log (sums codes if the building has several).",
    "asbestos_items_damaged": "Of those, entries with damage recorded at inspection.",
    "asbestos_report_sy": "School year of the asbestos report.",
    "lead_components_tested": "Painted components tested by XRF in the latest full lead-safe survey.",
    "lead_components_positive": "Components the inspector called positive for lead paint.",
    "lead_positive_damaged": "Positive components with damaged paint at assessment.",
    "lead_survey_sy": "School year the lead survey ended.",
    "water_outlets_tested": "Drinking water outlets tested in the latest initial lead-in-water test.",
    "water_outlets_above_action": "Outlets above the district's 10 ppb action level on first sample.",
    "water_sample_sy": "School year of the water sampling.",
    "fca_fci_pct": "Facility condition index of this building from the 2020 assessment (repair cost / replacement value).",
    "fca_repair_cost": "Assessed repair cost in dollars.",
    "fca_replacement_value": "Replacement value in dollars.",
    "fca_report_sy": "School year of the assessment report.",
}


def _sy(ts) -> float:
    t = pd.to_datetime(ts, errors="coerce")
    return float("nan") if pd.isna(t) else t.year + (1 if t.month >= 7 else 0)


def build_building_mart(t: dict) -> pd.DataFrame:
    b = t["building"].copy()
    xw = t["building_xwalk"]
    sb = t["school_building"]
    latest_sy = sb["valid_to_sy"].max()
    cur = sb[(sb["role"] == "primary") & (sb["valid_to_sy"] == latest_sy)]
    sch = cur.groupby("building_id")["school_id"].agg(lambda x: ", ".join(sorted(x)))
    b["schools_current"] = b["building_id"].map(sch)
    b["n_schools_current"] = (
        b["building_id"].map(cur.groupby("building_id").size()).fillna(0).astype(int)
    )

    def key_map(kind: str) -> dict:
        x = xw[xw["key_type"] == kind]
        return dict(zip(x["key_value"], x["building_id"], strict=True))

    # asbestos: each code's latest report
    a = pd.read_parquet(CORE / "building_asbestos.parquet")
    a = a[a["is_latest"]].assign(
        building_id=lambda d: d["building_code"].map(key_map("ahera_code"))
    )
    a["sy"] = [
        y + (1 if (m or 0) >= 7 else 0)
        for y, m in zip(a["report_year"], a["report_month"], strict=True)
    ]
    ag = a.groupby("building_id").agg(
        asbestos_items=("acm_items", "sum"),
        asbestos_items_damaged=("acm_items_damaged", "sum"),
        asbestos_report_sy=("sy", "max"),
    )
    # lead: each folder's most recent full survey
    ld = pd.read_parquet(CORE / "school_lead_paint.parquet")
    ld = ld[(ld["n_components_tested"] >= 200)].dropna(subset=["inspection_end"])
    ld = ld.sort_values("inspection_end").groupby("site_folder").tail(1)
    ld["building_id"] = ld["site_folder"].map(key_map("lead_folder"))
    ld["sy"] = ld["inspection_end"].map(_sy)
    lg = ld.groupby("building_id").agg(
        lead_components_tested=("n_components_tested", "sum"),
        lead_components_positive=("n_positive", "sum"),
        lead_positive_damaged=("n_positive_damaged", "sum"),
        lead_survey_sy=("sy", "max"),
    )
    # water: each folder's most recent initial test letter
    w = pd.read_parquet(CORE / "school_water_lead.parquet")
    w = w[~w["follow_up"] & w["lead_ppb"].notna()]
    pf = w.groupby(["site_folder", "file"], as_index=False).agg(
        last=("sample_date", "max"),
        tested=("outlet", "count"),
        above=("above_action_level", "sum"),
        lt=("letter_outlets_tested", "first"),
        la=("letter_outlets_above", "first"),
    )
    pf["tested"], pf["above"] = pf["lt"].fillna(pf["tested"]), pf["la"].fillna(pf["above"])
    pf = pf.sort_values("last").groupby("site_folder").tail(1)
    pf["building_id"] = pf["site_folder"].map(key_map("water_folder"))
    pf["sy"] = pf["last"].map(_sy)
    wg = pf.groupby("building_id").agg(
        water_outlets_tested=("tested", "sum"),
        water_outlets_above_action=("above", "sum"),
        water_sample_sy=("sy", "max"),
    )
    # facility condition: the building's own part of the site report
    fp = pd.read_parquet(CORE / "facility_condition_part.parquet")
    fs = pd.read_parquet(CORE / "facility_condition.parquet").set_index("site_code")
    fp = fp[fp["part_code"].str[0] == "B"].assign(
        building_id=lambda d: d["part_code"].map(key_map("fca_part_code"))
    )
    fp["fca_report_sy"] = (
        fp["site_code"]
        .map(fs["report_date"])
        .map(lambda d: _sy(pd.to_datetime(d, format="%B %d, %Y", errors="coerce")))
    )
    fg = fp.groupby("building_id").agg(
        fca_repair_cost=("repair_cost", "sum"),
        fca_replacement_value=("replacement_value", "sum"),
        fca_report_sy=("fca_report_sy", "max"),
    )
    fg["fca_fci_pct"] = (100 * fg["fca_repair_cost"] / fg["fca_replacement_value"]).round(2)
    out = b.merge(ag, on="building_id", how="left").merge(lg, on="building_id", how="left")
    out = out.merge(wg, on="building_id", how="left").merge(fg, on="building_id", how="left")
    cols = [c for c in MART_DOCS if c in out.columns]
    for c in out.columns:
        if c.endswith("_sy"):
            out[c] = out[c].astype("Int64")
    return out[cols]


def write_building_mart(t: dict) -> pd.DataFrame:
    from .marts import MARTS, write_documented, write_schema_json

    mart = build_building_mart(t)
    docs = {c: {"description": d} for c, d in MART_DOCS.items()}
    MARTS.mkdir(exist_ok=True)
    write_documented(mart, MARTS / "building.parquet", docs)
    write_schema_json("building", mart, "one row per building_id", docs)
    return mart
