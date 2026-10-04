"""Geography: catchments by vintage, assignment zones, geo units, and a population-weighted crosswalk.

Population weights come from 2020 census blocks (redistricting file P1/H1). A block split
by a boundary is allocated by area share; blocks are small, so the error is small, and it is
far better than weighting whole tracts by area.

Grain of each table:
  catchment       one row per school x level (ES/MS/HS) x boundary year (sy)
  assignment_zone one row per K-12 assignment path x boundary year
  geo_unit        one row per polygon of any type (catchment, zone, neighborhood, tract)
  geo_xwalk       one row per (from unit, to unit) pair that share population or area
"""

import hashlib
import io
import re
import zipfile

import geopandas as gpd
import pandas as pd

from . import CORE, RAW, STAGING
from .identity import load_registry

CRS_WORK = "EPSG:2272"  # PA South, US feet: for areas and overlays
CRS_OUT = "EPSG:4326"
LEVELS = ["ES", "MS", "HS"]
GRADES = ["K"] + [f"{g:02d}" for g in range(1, 13)]
PHILLY = "42101"


# --- census blocks --------------------------------------------------------------------------


def block_population() -> pd.DataFrame:
    """2020 population and housing units for every Philadelphia block (keyless bulk file)."""
    z = zipfile.ZipFile(RAW / "census_blocks_2020" / "pa2020.pl.zip")
    geo = pd.read_csv(
        z.open("pageo2020.pl"),
        sep="|",
        header=None,
        usecols=[2, 7, 9],
        dtype=str,
        encoding="latin-1",
        names=None,
    )
    geo.columns = ["sumlev", "logrecno", "geocode"]
    geo = geo[(geo["sumlev"] == "750") & geo["geocode"].str.startswith(PHILLY)]

    def segment(name: str, index: int, col: str) -> pd.DataFrame:
        seg = pd.read_csv(z.open(name), sep="|", header=None, usecols=[4, index], dtype=str)
        seg.columns = ["logrecno", col]
        return seg

    # Segment 1 field 5 = P1_001N (total population); segment 2 field 149 = H1_001N (housing
    # units), after the P3 and P4 tables. Segment 3 is group quarters, not housing.
    out = geo.merge(segment("pa000012020.pl", 5, "pop20"), on="logrecno").merge(
        segment("pa000022020.pl", 149, "housing20"), on="logrecno"
    )
    out = out.rename(columns={"geocode": "geoid20"})[["geoid20", "pop20", "housing20"]]
    return out.astype({"pop20": int, "housing20": int})


def blocks() -> gpd.GeoDataFrame:
    shp = gpd.read_file(f"zip://{RAW / 'census_blocks_2020' / 'tl_2020_42101_tabblock20.zip'}")
    shp = shp[["GEOID20", "TRACTCE20", "geometry"]].rename(
        columns={"GEOID20": "geoid20", "TRACTCE20": "tract"}
    )
    b = shp.merge(block_population(), on="geoid20", how="left").fillna({"pop20": 0, "housing20": 0})
    b = b.to_crs(CRS_WORK)
    b["block_area"] = b.geometry.area
    return b


# --- catchments -----------------------------------------------------------------------------


def _shapefiles_in(zip_bytes: bytes, prefix: str = ""):
    """Yield (name, zipfile, member) for every .shp, descending into nested zips."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for member in z.namelist():
        if member.lower().endswith(".zip"):
            yield from _shapefiles_in(z.read(member), prefix + member + "/")
        elif member.lower().endswith(".shp"):
            yield prefix + member, z, member


def _read_shp(z: zipfile.ZipFile, member: str) -> gpd.GeoDataFrame:
    stem = member[:-4]
    parts = {m[len(stem) :].lower(): m for m in z.namelist() if m.startswith(stem + ".")}
    tmp = STAGING / "_shp"
    tmp.mkdir(parents=True, exist_ok=True)
    for ext, m in parts.items():
        (tmp / f"layer{ext}").write_bytes(z.read(m))
    g = gpd.read_file(tmp / "layer.shp")
    g.columns = [c.upper() if c != "geometry" else c for c in g.columns]
    return g


def vintage_sy(zip_name: str) -> int:
    """SDP_Catchment_1213.zip -> 2013 (spring year of SY 2012-13)."""
    m = re.search(r"_(\d{2})(\d{2})\.zip$", zip_name)
    return 2000 + int(m.group(2))


def read_catchments() -> gpd.GeoDataFrame:
    rows = []
    for path in sorted((RAW / "sdp_catchments").glob("SDP_Catchment_[0-9]*.zip")):
        sy = vintage_sy(path.name)
        for name, z, member in _shapefiles_in(path.read_bytes()):
            level = next(
                (lv for lv in LEVELS if re.search(rf"(^|[_/]){lv}[_/]", name.upper())), None
            )
            if level is None:
                continue
            g = _read_shp(z, member).to_crs(CRS_WORK)
            g["GEOMETRY_OK"] = g.geometry.notna()
            g = g[g["GEOMETRY_OK"]]
            keep = {
                "level": level,
                "sy": sy,
                "ulcs": g[f"{level}_ID"].astype(str).str.replace(r"\.0$", "", regex=True),
                "name": g.get(f"{level}_NAME"),
                "geometry": g.geometry.buffer(0),
            }
            if level == "ES":
                for gr in GRADES:
                    col = f"GR_ID_{gr}"
                    keep[f"gr_{gr.lower()}"] = (
                        g[col].astype(str).str.replace(r"\.0$", "", regex=True)
                        if col in g
                        else None
                    )
            rows.append(gpd.GeoDataFrame(keep, geometry="geometry", crs=CRS_WORK))
    return pd.concat(rows, ignore_index=True)


def build_catchments(
    raw: gpd.GeoDataFrame, registry: pd.DataFrame
) -> tuple[gpd.GeoDataFrame, list]:
    ulcs_to_id = registry.set_index("ulcs")["school_id"]
    c = raw.dissolve(by=["level", "sy", "ulcs"], aggfunc={"name": "first"}).reset_index()
    c["school_id"] = c["ulcs"].map(ulcs_to_id)
    issues = [
        {
            "type": "catchment ULCS not in school registry",
            "id": r.ulcs,
            "sy": r.sy,
            "detail": r.level,
        }
        for r in c[c["school_id"].isna()].itertuples()
    ]
    c["catchment_id"] = [
        f"ctm_{lv.lower()}_{sid if isinstance(sid, str) else 'ulcs' + u}_{sy}"
        for lv, sid, u, sy in zip(c["level"], c["school_id"], c["ulcs"], c["sy"], strict=True)
    ]
    cols = ["catchment_id", "school_id", "ulcs", "level", "sy", "name", "geometry"]
    return c[cols], issues


def zone_id_for(path: tuple[str, ...]) -> str:
    return "az_" + hashlib.sha1("|".join(path).encode()).hexdigest()[:10]


def build_assignment_zones(raw: gpd.GeoDataFrame, registry: pd.DataFrame) -> gpd.GeoDataFrame:
    """Zones: areas where every address has the same school for each grade K-12."""
    es = raw[raw["level"] == "ES"].copy()
    gr_cols = [f"gr_{g.lower()}" for g in GRADES]
    es = es.dropna(subset=gr_cols, how="all")
    es["path"] = es[gr_cols].fillna("").astype(str).agg("|".join, axis=1)
    z = es.dissolve(by=["sy", "path"]).reset_index()
    z["zone_id"] = [zone_id_for(tuple(p.split("|"))) for p in z["path"]]
    ulcs_to_id = registry.set_index("ulcs")["school_id"]
    for col in gr_cols:
        z[col.replace("gr_", "school_id_gr_")] = z[col].map(ulcs_to_id)
    keep = ["zone_id", "sy"] + [c.replace("gr_", "school_id_gr_") for c in gr_cols] + gr_cols
    return z[keep + ["geometry"]].rename(columns={c: c.replace("gr_", "ulcs_gr_") for c in gr_cols})


# --- reference geographies -----------------------------------------------------------------


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def neighborhoods() -> gpd.GeoDataFrame:
    n = gpd.read_file(RAW / "opendataphilly_neighborhoods" / "philadelphia-neighborhoods.geojson")
    n = n.to_crs(CRS_WORK)
    return gpd.GeoDataFrame(
        {"unit_id": "nbhd_" + n["NAME"].map(_slug), "name": n["MAPNAME"], "geometry": n.geometry},
        crs=CRS_WORK,
    )


def tracts() -> gpd.GeoDataFrame:
    t = gpd.read_file(f"zip://{RAW / 'census_tracts' / 'tl_2020_42101_tract20.zip'}").to_crs(
        CRS_WORK
    )
    return gpd.GeoDataFrame(
        {
            "unit_id": "tract_" + t["GEOID20"],
            "name": "Tract " + t["NAME20"],
            "geometry": t.geometry,
        },
        crs=CRS_WORK,
    )


# --- crosswalk ------------------------------------------------------------------------------


def allocate_blocks(b: gpd.GeoDataFrame, units: gpd.GeoDataFrame) -> pd.DataFrame:
    """Share of each block's population and area falling in each unit."""
    pieces = gpd.overlay(
        b[["geoid20", "pop20", "housing20", "block_area", "geometry"]],
        units[["unit_id", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    share = (pieces.geometry.area / pieces["block_area"]).clip(upper=1.0)
    return pd.DataFrame(
        {
            "geoid20": pieces["geoid20"],
            "unit_id": pieces["unit_id"],
            "pop": pieces["pop20"] * share,
            "housing": pieces["housing20"] * share,
            "area": pieces.geometry.area,
        }
    )


def crosswalk(from_alloc: pd.DataFrame, to_alloc: pd.DataFrame) -> pd.DataFrame:
    """Pairs of units with population and area shares in both directions.

    Within a block, people are assumed spread evenly by area (the only assumption).
    """
    f = from_alloc.rename(columns={"unit_id": "from_unit"})
    t = to_alloc.rename(columns={"unit_id": "to_unit"})
    # each block's share of population in the `to` unit
    t_share = t.assign(to_frac=t["area"] / t.groupby("geoid20")["area"].transform("sum"))[
        ["geoid20", "to_unit", "to_frac"]
    ]
    j = f.merge(t_share, on="geoid20")
    j["pop_both"] = j["pop"] * j["to_frac"]
    j["housing_both"] = j["housing"] * j["to_frac"]
    j["area_both"] = j["area"] * j["to_frac"]
    pair = j.groupby(["from_unit", "to_unit"], as_index=False)[
        ["pop_both", "housing_both", "area_both"]
    ].sum()
    from_tot = f.groupby("from_unit")[["pop", "area"]].sum()
    to_tot = t.groupby("to_unit")[["pop", "area"]].sum()
    pair["pop_share_of_from"] = pair["pop_both"] / pair["from_unit"].map(from_tot["pop"])
    pair["pop_share_of_to"] = pair["pop_both"] / pair["to_unit"].map(to_tot["pop"])
    pair["area_share_of_from"] = pair["area_both"] / pair["from_unit"].map(from_tot["area"])
    pair = pair[(pair["pop_both"] > 0.5) | (pair["area_share_of_from"] > 0.001)]
    pair = pair.rename(columns={"pop_both": "pop_2020", "housing_both": "housing_units_2020"})
    pair = pair.drop(columns="area_both")
    return pair.reset_index(drop=True)


# --- build ----------------------------------------------------------------------------------


def build_geography() -> dict:
    registry = load_registry()
    raw = read_catchments()
    catch, issues = build_catchments(raw, registry)
    zones = build_assignment_zones(raw, registry)

    units = [
        gpd.GeoDataFrame(
            {
                "unit_id": catch["catchment_id"],
                "unit_type": "catchment_" + catch["level"].str.lower(),
                "sy": catch["sy"],
                "name": catch["name"],
                "school_id": catch["school_id"],
                "geometry": catch.geometry,
            },
            crs=CRS_WORK,
        ),
        gpd.GeoDataFrame(
            {
                "unit_id": zones["zone_id"] + "_" + zones["sy"].astype(str),
                "unit_type": "assignment_zone",
                "sy": zones["sy"],
                "name": None,
                "school_id": None,
                "geometry": zones.geometry,
            },
            crs=CRS_WORK,
        ),
    ]
    nb, tr = neighborhoods(), tracts()
    units.append(nb.assign(unit_type="neighborhood", sy=pd.NA, school_id=None))
    units.append(tr.assign(unit_type="tract", sy=pd.NA, school_id=None))
    geo_unit = pd.concat(units, ignore_index=True)
    geo_unit["sy"] = geo_unit["sy"].astype("Int64")

    b = blocks()
    base = {"tract": allocate_blocks(b, tr), "neighborhood": allocate_blocks(b, nb)}
    xw = []
    for (utype, sy), group in geo_unit[geo_unit["sy"].notna()].groupby(["unit_type", "sy"]):
        alloc = allocate_blocks(b, group)
        for from_type, from_alloc in base.items():
            pair = crosswalk(from_alloc, alloc)
            pair.insert(0, "to_type", utype)
            pair.insert(0, "from_type", from_type)
            pair.insert(2, "sy", sy)
            xw.append(pair)
    pair = crosswalk(base["tract"], base["neighborhood"])
    pair.insert(0, "to_type", "neighborhood")
    pair.insert(0, "from_type", "tract")
    pair.insert(2, "sy", pd.NA)
    xw.append(pair)
    geo_xwalk = pd.concat(xw, ignore_index=True)
    geo_xwalk["sy"] = geo_xwalk["sy"].astype("Int64")
    geo_xwalk["method"] = "census_block_2020_pop_area_split_v1"

    return {
        "catchment": catch,
        "assignment_zone": zones,
        "geo_unit": geo_unit,
        "geo_xwalk": geo_xwalk,
        "geo_issues": pd.DataFrame(issues, columns=["type", "id", "sy", "detail"]),
        "_block_pop_total": int(b["pop20"].sum()),
    }


def write_geography(t: dict) -> None:
    CORE.mkdir(exist_ok=True)
    for name in ["catchment", "assignment_zone", "geo_unit"]:
        g = t[name].to_crs(CRS_OUT)
        g.to_parquet(CORE / f"{name}.parquet", index=False)
        g.to_file(CORE / f"{name}.geojson", driver="GeoJSON")
        pd.DataFrame(g.drop(columns="geometry")).to_csv(CORE / f"{name}.csv", index=False)
    for name in ["geo_xwalk", "geo_issues"]:
        t[name].to_parquet(CORE / f"{name}.parquet", index=False)
        t[name].to_csv(CORE / f"{name}.csv", index=False)
