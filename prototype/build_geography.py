"""Lock down the geographies: catchments, assignment zones, neighborhoods, census tracts.

Inputs (raw/): SDP catchment shapefiles SY 2024-25 (ES, MS, HS), OpenDataPhilly
neighborhoods (open-geo-data), Census TIGER 2024 tracts for Pennsylvania.

Outputs (data/geo/):
  catchments_es|ms|hs.geojson   catchment polygons with ULCS ids
  assignment_zones.geojson      unique K-12 assignment paths (dissolved from the ES layer,
                                which lists the assigned school for every grade)
  zone_neighborhood.csv         which zones fall in which neighborhood, with area shares
  neighborhood_schools.csv      for each neighborhood: every assigned school by level, with share
  tract_catchment_weights.csv   area share of each tract in each ES/MS/HS catchment (for census joins)
  geo_checks.txt                consistency checks between layers
"""
import glob
import geopandas as gpd
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent
RAW, OUT = ROOT / "raw", ROOT / "data" / "geo"
OUT.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:2272"  # PA State Plane South, feet: the district's own projection
GRADES = ["K"] + [f"{g:02d}" for g in range(1, 13)]
MIN_SHARE = 0.02  # ignore slivers under 2% of a polygon's area (digitizing noise)

log = []


def say(s):
    print(s)
    log.append(s)


def shp(level):
    return gpd.read_file(glob.glob(str(RAW / f"catch2425/{level}/**/*.shp"), recursive=True)[0]).to_crs(CRS)


def overlay_shares(a, a_id, b, b_id):
    """Area share of each `a` polygon falling in each `b` polygon."""
    a = a[[a_id, "geometry"]].copy()
    a["a_area"] = a.area
    x = gpd.overlay(a, b[[b_id, "geometry"]], how="intersection", keep_geom_type=True)
    x["share"] = x.area / x["a_area"]
    return x[x["share"] >= MIN_SHARE].drop(columns="geometry")


def main():
    es, ms, hs = shp("ES"), shp("MS"), shp("HS")
    for g, lvl in [(es, "es"), (ms, "ms"), (hs, "hs")]:
        g.to_crs(4326).to_file(OUT / f"catchments_{lvl}.geojson", driver="GeoJSON")
    say(f"Catchments SY2024-25: {len(es)} ES polygons, {len(ms)} MS, {len(hs)} HS")

    # 1. Does each ES polygon's stated MS/HS match the MS/HS layers?
    for other, oid, col in [(ms, "MS_ID", "MS_ID"), (hs, "HS_ID", "HS_ID")]:
        o = other.rename(columns={oid: "layer_id"})
        sh = overlay_shares(es.rename(columns={"OBJECTID": "es_poly"}), "es_poly", o, "layer_id")
        stated = es.set_index("OBJECTID")[col].astype(str)
        sh["stated"] = sh["es_poly"].map(stated)
        mism = sh[sh["layer_id"].astype(str) != sh["stated"]]
        split = sh.groupby("es_poly")["layer_id"].nunique()
        say(f"ES polygons crossing more than one {col[:2]} catchment (>{MIN_SHARE:.0%}): {(split > 1).sum()}; "
            f"area where stated {col} disagrees with the {col[:2]} layer: {mism['share'].sum():.2f} polygon-equivalents")

    # 2. Assignment zones: unique grade-by-grade paths from the ES layer
    es["path"] = es[[f"GR_ID_{g}" for g in GRADES]].astype(str).agg("-".join, axis=1)
    zones = es.dissolve(by="path", as_index=False, aggfunc="first")
    zones["zone_id"] = [f"Z{i:03d}" for i in range(1, len(zones) + 1)]
    keep = ["zone_id", "path", "ES_ID", "ES_Name", "MS_ID", "MS_Name", "HS_ID", "HS_Name",
            "ES_Grade", "MS_Grade", "HS_Grade"] + [f"GR_ID_{g}" for g in GRADES]
    zones = zones[keep + ["geometry"]]
    zones["acres"] = (zones.area / 43560).round(1)
    zones.to_crs(4326).to_file(OUT / "assignment_zones.geojson", driver="GeoJSON")
    multi_es = es.groupby("ES_ID")["path"].nunique()
    say(f"Assignment zones (unique K-12 paths): {len(zones)}; ES catchments split into more than one path: {(multi_es > 1).sum()}")
    say(f"Distinct schools a kid can be assigned to across K-12, per zone: "
        f"{zones[[f'GR_ID_{g}' for g in GRADES]].nunique(axis=1).value_counts().sort_index().to_dict()}")

    # 3. Neighborhoods
    nb = gpd.read_file(RAW / "nb.geojson").to_crs(CRS)
    name_col = next(c for c in nb.columns if c.lower() in ("name", "listname", "mapname"))
    nb = nb.rename(columns={name_col: "neighborhood"})[["neighborhood", "geometry"]]
    zn = overlay_shares(nb, "neighborhood", zones, "zone_id")
    zn.to_csv(OUT / "zone_neighborhood.csv", index=False)
    per = zn.groupby("neighborhood")["zone_id"].nunique()
    say(f"Neighborhoods: {len(nb)}; with more than one assignment zone: {(per > 1).sum()} "
        f"(median {per.median():.0f}, max {per.max()} in {per.idxmax()})")

    rows = []
    for lvl, layer, idc, namec in [("ES", es, "ES_ID", "ES_Name"), ("MS", ms, "MS_ID", "MS_Name"), ("HS", hs, "HS_ID", "HS_Name")]:
        sh = overlay_shares(nb, "neighborhood", layer, idc)
        names = layer.drop_duplicates(idc).set_index(idc)[namec]
        sh["level"], sh["school_name"] = lvl, sh[idc].map(names)
        rows.append(sh.rename(columns={idc: "ulcs"})[["neighborhood", "level", "ulcs", "school_name", "share"]])
    ns = pd.concat(rows).sort_values(["neighborhood", "level", "share"], ascending=[True, True, False])
    ns["share"] = ns["share"].round(3)
    ns.to_csv(OUT / "neighborhood_schools.csv", index=False)
    es_per_nb = ns[ns.level == "ES"].groupby("neighborhood")["ulcs"].nunique()
    say(f"Neighborhoods with more than one elementary catchment: {(es_per_nb > 1).sum()} of {len(es_per_nb)}")

    # 4. Census tracts -> catchment weights (for ACS joins later)
    tr = gpd.read_file(f"zip://{RAW / 'tracts.zip'}")
    tr = tr[tr["COUNTYFP"] == "101"].to_crs(CRS)[["GEOID", "geometry"]]
    w = []
    for lvl, layer, idc in [("ES", es.dissolve(by="ES_ID", as_index=False), "ES_ID"), ("MS", ms, "MS_ID"), ("HS", hs, "HS_ID")]:
        sh = overlay_shares(tr, "GEOID", layer, idc)
        sh["level"] = lvl
        w.append(sh.rename(columns={idc: "ulcs", "share": "tract_share"})[["GEOID", "level", "ulcs", "tract_share"]])
    pd.concat(w).to_csv(OUT / "tract_catchment_weights.csv", index=False)
    say(f"Census tracts in Philadelphia: {len(tr)}")

    # 5. Do catchment school ids match the crosswalk spine?
    cw = pd.read_csv(ROOT / "data" / "crosswalk.csv", dtype=str)
    ids = set(es["ES_ID"].astype(str)) | set(ms["MS_ID"].astype(str)) | set(hs["HS_ID"].astype(str))
    for g in GRADES:
        ids |= set(es[f"GR_ID_{g}"].astype(str))
    missing = sorted(ids - set(cw["ulcs"]))
    say(f"Catchment school ids: {len(ids)}; matched to crosswalk ULCS: {len(ids) - len(missing)}; unmatched: {missing}")

    (OUT / "geo_checks.txt").write_text("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
