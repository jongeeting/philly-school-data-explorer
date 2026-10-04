"""Build the Philadelphia school ID crosswalk and per-year school facts.

Two keys:
  ulcs        the district's own school code; unique per school/program and stable over time.
              This is the spine.
  school_key  "<AUN>-<state school number>", the pair the state uses in every Future Ready
              file. NOT unique: alternative/contracted programs share placeholder numbers
              (0, 9999) and continuation academies report under their host school's number.
              `state_key_shared` flags those.

Outputs (data/):
  crosswalk.csv        one row per school_key: all IDs, names, governance, years seen
  school_years.csv     one row per school_key x year from the district list
  id_issues.csv        IDs that map to more than one school_key, or governance changes
  school_facts.parquet state fast facts per school_key x year (enrollment, % econ disadvantaged...)
"""
import glob
import re
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent
RAW, OUT = ROOT / "raw", ROOT / "data"
SDP_AUN = "126515001"


def clean_id(s):
    s = str(s).strip()
    if s in ("", "nan", "None"):
        return None
    return re.sub(r"\.0$", "", s)


def load_sdp_lists():
    rows = []
    for f in sorted(glob.glob(str(RAW / "sdp_list_*"))):
        sy = int(re.search(r"(\d{4})-(\d{4})", f).group(2))  # spring year
        if sy == 2018:
            continue  # 2017-18 file uses a different layout; state data covers that year
        d = (pd.read_excel(f, engine="calamine", dtype=str) if f.endswith("xlsx")
             else pd.read_csv(f, dtype=str, encoding="utf-8-sig", encoding_errors="replace"))
        d.columns = [c.strip() for c in d.columns]
        rows.append(pd.DataFrame({
            "year": sy,
            "aun": d["AUN Code"].map(clean_id),
            "schl": d["PA Code"].map(clean_id),
            "ulcs": d["ULCS Code"].map(clean_id),
            "src_id": d["SRC School ID"].map(clean_id),
            "nces": d["NCES Code"].map(clean_id),
            "name": d["Publication Name"].str.strip(),
            "governance": d["Governance"].str.strip(),
            "category": d["School Reporting Category"].str.strip(),
            "level": d.get("School Level"),
            "admission": d.get("Admission Type"),
            "council_district": d.get("City Council District"),
            "gps": d.get("GPS Location"),
        }))
    sy = pd.concat(rows, ignore_index=True)
    # NCES codes in some CSVs were saved in scientific notation (4.21899E+11); unusable as IDs.
    sy.loc[sy["nces"].fillna("").str.contains("E", case=False), "nces"] = None
    sy["school_key"] = sy["aun"] + "-" + sy["schl"]
    return sy[sy["aun"].notna() & sy["schl"].notna()]


def load_fast_facts():
    parts = []
    for f in sorted(glob.glob(str(RAW / "SchoolFastFacts*.xlsx"))):
        m = re.search(r"_(\d{4})(\d{4})", f)
        sy = int(m.group(2)) if m else 2018  # unlabeled file is SY 2017-18
        d = pd.read_excel(f, engine="calamine", dtype=str)
        d.columns = [str(c).strip() for c in d.columns]
        if "DataElement" in d.columns:  # 2017-18 to 2020-21 files are long: pivot to wide
            d = d.rename(columns={"SchoolName": "Name"})
            d["DataElement"] = d["DataElement"].str.strip()
            d = (d.drop_duplicates(["AUN", "Schl", "DataElement"])
                  .pivot(index=["AUN", "Schl", "Name"], columns="DataElement", values="DisplayValue")
                  .reset_index()
                  .rename(columns={"School Enrollment": "Enrollment", "School Address (City)": "City",
                                   "Black/African American": "Black"}))
        lower = {c.lower(): c for c in d.columns}

        def col(*names):
            for n in names:
                if n.lower() in lower:
                    return d[lower[n.lower()]]
            return None

        out = pd.DataFrame({"year": sy,
                            "aun": col("AUN").map(clean_id), "schl": col("Schl").map(clean_id),
                            "state_name": col("Name"), "city": col("City"),
                            "org_type": col("OrganizationTypeCode")})
        for key, names in {"enrollment": ["Enrollment"],
                           "pct_econ_dis": ["EconomicallyDisadvantaged", "Economically Disadvantaged"],
                           "pct_el": ["EnglishLearner", "English Learner"],
                           "pct_sped": ["SpecialEducation", "Special Education"],
                           "pct_black": ["Black"], "pct_hispanic": ["Hispanic"], "pct_white": ["White"],
                           "pct_asian": ["Asian"]}.items():
            c = col(*names)
            out[key] = pd.to_numeric(c, errors="coerce") if c is not None else None
        parts.append(out)
    ff = pd.concat(parts, ignore_index=True)
    ff["school_key"] = ff["aun"] + "-" + ff["schl"]
    return ff


def main():
    sy = load_sdp_lists()
    sy.to_csv(OUT / "school_years.csv", index=False)

    sy = sy.dropna(subset=["ulcs"])
    last = sy.sort_values("year").groupby("ulcs").last()
    span = sy.groupby("ulcs")["year"].agg(first_year="min", last_year="max", n_years="count")
    agg = sy.groupby("ulcs").agg(
        school_keys=("school_key", lambda s: "|".join(sorted(set(s.dropna())))),
        governances=("governance", lambda s: "|".join(sorted(set(s.dropna())))),
        names=("name", lambda s: "|".join(dict.fromkeys(s.dropna()))))
    cw = last[["school_key", "aun", "schl", "src_id", "nces", "name", "governance", "category", "level",
               "admission", "council_district", "gps"]].join(span).join(agg).reset_index()
    n_per_key = sy.groupby("school_key")["ulcs"].nunique()
    cw["state_key_shared"] = (cw["school_key"].map(n_per_key) > 1) | cw["schl"].isin(["0", "9999"])
    cw.to_csv(OUT / "crosswalk.csv", index=False)

    issues = []
    for idcol in ["ulcs", "src_id"]:
        multi = sy.dropna(subset=[idcol]).groupby(idcol)["school_key"].nunique()
        for v in multi[multi > 1].index:
            keys = sorted(sy.loc[sy[idcol] == v, "school_key"].unique())
            issues.append({"type": f"{idcol} maps to several school_keys", "id": v, "school_keys": "|".join(keys),
                           "names": "|".join(sy.loc[sy[idcol] == v, "name"].unique())})
    gov = cw[cw["governances"].str.contains(r"\|")]
    for _, r in gov.iterrows():
        issues.append({"type": "governance changed", "id": r["ulcs"], "school_keys": r["school_keys"],
                       "names": r["names"], "detail": r["governances"]})
    shared = sy.groupby("school_key")["ulcs"].nunique()
    for k in shared[shared > 1].index:
        sub = sy[sy["school_key"] == k]
        issues.append({"type": "state key shared by several programs", "id": k, "school_keys": k,
                       "names": "|".join(sub["name"].unique()[:6]), "detail": f"{sub['ulcs'].nunique()} ULCS codes"})
    pd.DataFrame(issues).to_csv(OUT / "id_issues.csv", index=False)

    ff = load_fast_facts()
    ff.to_parquet(OUT / "school_facts.parquet")

    # Coverage report
    keys = set(cw["school_key"])
    phl_ff = ff[ff["aun"].isin(set(cw["aun"])) | ff["city"].str.upper().eq("PHILADELPHIA")]
    unmatched = phl_ff[~phl_ff["school_key"].isin(keys)]
    print(f"shared state keys: {cw['state_key_shared'].sum()} programs")
    print(f"crosswalk schools: {len(cw)}  ({cw['governance'].value_counts().to_dict()})")
    print(f"id issues: {len(issues)}")
    print(f"state fast-facts rows for Philly AUNs or Philadelphia city: {len(phl_ff)}, not in crosswalk: {len(unmatched)}")
    print(unmatched.groupby("org_type")["school_key"].nunique().to_string())
    print(unmatched.drop_duplicates("school_key")[["school_key", "state_name", "org_type", "city"]].head(25).to_string())


if __name__ == "__main__":
    main()
