"""Build a data release: tables, metadata, checksums, and a zip.

`uv run psd release --version 0.1.0` writes release/v0.1.0/ (git-ignored):

  philly-school-data-explorer-v0.1.0.zip   everything below in one file
  assets/                                  flat files for a GitHub release, so DuckDB and other
                                           tools can read each table from its release URL
  philly-school-data-explorer-v0.1.0/      the unzipped package:
      README.md  CHANGELOG.md  LICENSE-DATA  SHA256SUMS  datapackage.json
      core/  marts/  geo/  schema/  registry/  corrections/  docs/  queries/

The build runs validation first and stops if a hard check or reconciliation fails. Tables
are published as Parquet and CSV (gzipped when large; GeoJSON for the spatial tables).
Nothing from raw/, staging/, or private/ is included.
"""

import gzip
import hashlib
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from . import CORE, ROOT
from .marts import MARTS, TABLES, column_docs
from .metrics import MEASURES
from .validate import run_validation

NAME = "philly-school-data-explorer"
REPO = "jongeeting/philly-school-data-explorer"
SKIP_CORE = {"correction", "school_lineage", "issues", "enrollment_issues", "geo_issues"}
EXTRA_TABLES = {
    "school_placeholder": (
        "school_id",
        "Programs that appear only in state data (cyber charters, non-public special education, programs outside the district list), with their own school_id.",
    ),
}
LARGE_CSV_BYTES = 25_000_000
SOURCES = [
    {
        "title": "School District of Philadelphia open data",
        "path": "https://www.philasd.org/research/",
    },
    {
        "title": "Pennsylvania Department of Education (Future Ready PA Index, Fast Facts)",
        "path": "https://www.education.pa.gov/",
    },
    {
        "title": "U.S. Department of Education Office for Civil Rights (Civil Rights Data Collection)",
        "path": "https://civilrightsdata.ed.gov/",
    },
    {
        "title": "U.S. Census Bureau (American Community Survey, 2020 Census)",
        "path": "https://www.census.gov/",
    },
    {
        "title": "City of Philadelphia (parcels, OPA property records, boundaries)",
        "path": "https://opendataphilly.org/",
    },
]
TYPE_MAP = {
    "int": "integer",
    "uint": "integer",
    "float": "number",
    "double": "number",
    "bool": "boolean",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _field_type(arrow_type: str) -> str:
    for key, val in TYPE_MAP.items():
        if arrow_type.startswith(key):
            return val
    return "string"


def table_names() -> list[str]:
    return sorted(
        p.stem
        for p in CORE.glob("*.parquet")
        if "school_metric__" not in p.name and p.stem not in SKIP_CORE
    )


def describe_table(name: str) -> tuple[str, str]:
    if name in TABLES:
        return TABLES[name]
    return EXTRA_TABLES.get(name, ("", name))


def _csv(df_path: Path, dest: Path) -> Path:
    df = pd.read_parquet(df_path)
    plain = dest.with_suffix(".csv")
    df.to_csv(plain, index=False)
    if plain.stat().st_size > LARGE_CSV_BYTES:
        gz = plain.with_suffix(".csv.gz")
        with open(plain, "rb") as src, gzip.open(gz, "wb", compresslevel=6) as out:
            shutil.copyfileobj(src, out)
        plain.unlink()
        return gz
    return plain


def _geojson(src: Path, dest_dir: Path) -> Path:
    dest = dest_dir / src.name
    if src.stat().st_size > LARGE_CSV_BYTES:
        dest = dest_dir / f"{src.name}.gz"
        with open(src, "rb") as f, gzip.open(dest, "wb", compresslevel=6) as out:
            shutil.copyfileobj(f, out)
    else:
        shutil.copy2(src, dest)
    return dest


def _resource(
    layer: str, name: str, parquet: Path, docs: dict, url_prefix: str | None, flat: bool
) -> dict:
    schema = pq.read_schema(parquet)
    grain, what = describe_table(name) if layer == "core" else TABLES.get(name, ("", name))
    path = f"{layer}__{name}.parquet" if flat else f"{layer}/{name}.parquet"
    fields = []
    for f in schema:
        d = docs.get(f.name, {})
        field = {"name": f.name, "type": _field_type(str(f.type))}
        if d.get("description"):
            field["description"] = d["description"]
        for k in ("unit", "denominator"):
            if d.get(k):
                field[k] = d[k]
        fields.append(field)
    return {
        "name": f"{layer}-{name}".replace("_", "-"),
        "path": f"{url_prefix}/{path}" if url_prefix else path,
        "format": "parquet",
        "mediatype": "application/vnd.apache.parquet",
        "bytes": parquet.stat().st_size,
        "hash": f"sha256:{_sha256(parquet)}",
        "description": f"{what} Grain: {grain}." if grain else what,
        "schema": {"fields": fields},
    }


def datapackage(version: str, created: str, url_prefix: str | None = None) -> dict:
    measures = pd.read_csv(MEASURES)
    docs = column_docs(measures)
    flat = url_prefix is not None
    resources = []
    for layer, directory in [("core", CORE), ("marts", MARTS)]:
        names = (
            table_names() if layer == "core" else sorted(p.stem for p in MARTS.glob("*.parquet"))
        )
        for name in names:
            resources.append(
                _resource(layer, name, directory / f"{name}.parquet", docs, url_prefix, flat)
            )
    return {
        "profile": "data-package",
        "name": NAME,
        "title": "Philly School Data Explorer",
        "version": version,
        "created": created,
        "homepage": f"https://github.com/{REPO}",
        "description": (
            "Open, linked data on Philadelphia public schools: identity, enrollment, test scores, "
            "attendance, discipline, buildings, facility condition, lead, water, and asbestos "
            "records, catchments, and neighborhood context. Read `status` before `value`; see "
            "README.md and docs/DATA_DICTIONARY.md."
        ),
        "licenses": [
            {
                "name": "CC-BY-4.0",
                "path": "https://creativecommons.org/licenses/by/4.0/",
                "title": "Creative Commons Attribution 4.0 (our compilation and derived work only; upstream terms in docs/SOURCE_TERMS.md)",
            }
        ],
        "sources": SOURCES,
        "contributors": [{"title": "Jon Geeting", "role": "author"}],
        "keywords": [
            "Philadelphia",
            "schools",
            "education",
            "open data",
            "facilities",
            "enrollment",
        ],
        "resources": resources,
    }


def readme(version: str, created: str, n_tables: int, n_measures: int) -> str:
    return f"""# Philly School Data Explorer, version {version}

Released {created}. Open, linked data on Philadelphia's public schools, built to be read by people, dashboards, and AI agents alike. Project: https://github.com/{REPO}

## What is here

- `core/`: {n_tables} tables as Parquet and CSV (large CSVs are gzipped). Every school-level measure is in `core/school_metric` (long: school x school year x measure x student group, with a `status` and `source_id` on every row).
- `marts/`: wide tables for reading and charts: `school_year` (one row per school and year), `school_profile` (latest value of each measure per school), `building` (one row per physical building with its latest environmental and condition results and its parcel).
- `geo/`: catchments, assignment zones, and geographic units as GeoJSON.
- `schema/` and `datapackage.json`: every column described, with units and denominators. `docs/DATA_DICTIONARY.md` lists all {n_measures} measures with definitions, breaks, and usage notes.
- `registry/`: the permanent school and building IDs and the measure dictionary. `corrections/`: every hand fix, each with its reason.
- `docs/`: methods, validation report (`VALIDATION.md`), known gaps (`DATA_GAPS.md`), and `docs/queries/` (example DuckDB queries that are run in tests).

## Read these before you use a number

- `sy` is the spring year: 2025 means the 2024-25 school year.
- Read `status` before `value`. Suppressed, waived, not-applicable, and carried-forward values are not zeros or blanks.
- Read each measure's `denominator`, `breaks`, and `usage_notes`. Some measures are point-in-time records from one inspection (lead, water, asbestos, facility condition), not yearly series.
- Groups under 20 students are suppressed at the source. Never rebuild them by subtraction or combination.
- These are facts for fair comparison, not rankings. No composite score is provided; do not rank schools or state causes the data cannot support.
- The October 1 enrollment count is the state funding count and can be affected by how withdrawals are processed (see the note on `enrollment_count`).
- Building-to-parcel matches carry a `parcel_confidence`; check it, and `building_parcel_review.csv`, before relying on a parcel.
- `docs/DATA_GAPS.md` lists what is missing and why.

## Query it

```sql
-- DuckDB, straight from the release (replace the tag)
SELECT sy, name, enrollment_count, pct_proficient_ela
FROM read_parquet('https://github.com/{REPO}/releases/download/v{version}/marts__school_year.parquet')
WHERE school_id = 'sch_00323' ORDER BY sy;
```

## Sources, attribution, and terms

This release compiles data from: the School District of Philadelphia, the Pennsylvania Department of Education, the U.S. Department of Education Office for Civil Rights (Civil Rights Data Collection), the U.S. Census Bureau, and the City of Philadelphia. It is not endorsed by any of them. Cite as: Geeting, J. (2026). *Philly School Data Explorer* (version {version}). https://github.com/{REPO}

Our compilation and derived tables are licensed CC BY 4.0 (`LICENSE-DATA`). That license covers only what is ours: the data come from the sources above and remain subject to their terms. The School District's Terms of Use (February 2013) apply to the district-sourced data; the district grants use for governmental, accountability, and evaluative purposes and restricts copying of its data sets. This release repackages data the district publishes for public use, for evaluative and accountability purposes. See `docs/SOURCE_TERMS.md` for the terms, the Civil Rights Data Collection usage agreement (never link it with individually identifiable data), and each source's license in `core/source`.

No student-level data and no named employees are included.

## Check the files

`SHA256SUMS` lists a SHA-256 hash for every file here (`shasum -a 256 -c SHA256SUMS`).
"""


def _copy_tree(pattern_dir: Path, glob: str, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(pattern_dir.glob(glob)):
        shutil.copy2(p, dest / p.name)
        out.append(dest / p.name)
    return out


def build_release(version: str, skip_validation: bool = False) -> dict:
    if not skip_validation:
        hard, recon = run_validation()
        failed = [c["check"] for c in hard + recon if not c["ok"]]
        if failed:
            raise SystemExit(f"validation failed, not releasing: {failed}")
    created = datetime.now(UTC).date().isoformat()
    out = ROOT / "release" / f"v{version}"
    if out.exists():
        shutil.rmtree(out)
    pkg = out / f"{NAME}-v{version}"
    assets = out / "assets"
    for d in [
        pkg / "core",
        pkg / "marts",
        pkg / "geo",
        pkg / "schema",
        pkg / "registry",
        pkg / "corrections",
        pkg / "docs" / "queries",
        assets,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    names = table_names()
    for name in names:
        shutil.copy2(CORE / f"{name}.parquet", pkg / "core" / f"{name}.parquet")
        _csv(CORE / f"{name}.parquet", pkg / "core" / name)
    for p in sorted(MARTS.glob("*.parquet")):
        shutil.copy2(p, pkg / "marts" / p.name)
        _csv(p, pkg / "marts" / p.stem)
    for p in sorted(CORE.glob("*.geojson")):
        _geojson(p, pkg / "geo")
    review = CORE / "building_parcel_review.csv"
    if review.exists():
        shutil.copy2(review, pkg / "core" / review.name)
    _copy_tree(ROOT / "schema", "*.json", pkg / "schema")
    for f in ["measures.csv", "school_id_registry.csv", "building_id_registry.csv"]:
        shutil.copy2(ROOT / "registry" / f, pkg / "registry" / f)
    _copy_tree(ROOT / "corrections", "*.csv", pkg / "corrections")
    _copy_tree(ROOT / "docs", "*.md", pkg / "docs")
    _copy_tree(ROOT / "docs" / "queries", "*", pkg / "docs" / "queries")
    shutil.copy2(ROOT / "LICENSE-DATA", pkg / "LICENSE-DATA")
    shutil.copy2(ROOT / "CHANGELOG.md", pkg / "CHANGELOG.md")

    n_measures = len(pd.read_csv(MEASURES))
    (pkg / "README.md").write_text(readme(version, created, len(names), n_measures))
    (pkg / "datapackage.json").write_text(
        json.dumps(datapackage(version, created), indent=1) + "\n"
    )

    sums = []
    for p in sorted(pkg.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            sums.append(f"{_sha256(p)}  {p.relative_to(pkg)}")
    (pkg / "SHA256SUMS").write_text("\n".join(sums) + "\n")

    zip_path = out / f"{NAME}-v{version}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in sorted(pkg.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(out))

    # flat assets for a GitHub release: one file per table, readable from its URL
    for layer in ["core", "marts"]:
        for p in sorted((pkg / layer).glob("*.parquet")):
            shutil.copy2(p, assets / f"{layer}__{p.name}")
    base = f"https://github.com/{REPO}/releases/download/v{version}"
    (assets / "datapackage.json").write_text(
        json.dumps(datapackage(version, created, url_prefix=base), indent=1) + "\n"
    )
    for f in ["SHA256SUMS", "README.md", "CHANGELOG.md"]:
        shutil.copy2(pkg / f, assets / f)
    shutil.copy2(pkg / "docs" / "DATA_DICTIONARY.md", assets / "DATA_DICTIONARY.md")
    shutil.copy2(pkg / "docs" / "VALIDATION.md", assets / "VALIDATION.md")
    shutil.copy2(zip_path, assets / zip_path.name)
    asset_sums = [
        f"{_sha256(p)}  {p.name}" for p in sorted(assets.iterdir()) if p.name != "SHA256SUMS"
    ]
    (assets / "SHA256SUMS").write_text("\n".join(asset_sums) + "\n")
    return {
        "version": version,
        "dir": out,
        "zip": zip_path,
        "assets": sorted(assets.iterdir()),
        "tables": len(names),
        "package_files": len(sums),
    }
