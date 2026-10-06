"""Package archived raw files for handoff (for example, Board records for a partner organization).

Writes <out_dir>/<name>.zip containing the files, MANIFEST.csv (URL, retrieval time, SHA-256
for every file, from sources/downloads.csv), and README.md. Files are stored untouched.
"""

import csv
import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from . import ROOT
from .fetch import read_downloads

ALREADY_COMPRESSED = {".pdf", ".zip", ".xlsx", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".mp4"}

README = """# {title}

Archived {date} by the Philly School Data Explorer project
(https://github.com/jongeeting/philly-school-data-explorer).

Every file is stored exactly as published. MANIFEST.csv gives, for each file: the source URL,
when it was retrieved (UTC), its SHA-256, and its size. Paths inside the zip match
`local_path` in the manifest.

Sources included: {sources}

{notes}

Use of School District data is subject to the district's Terms of Use (Feb 2013), included
under raw/sdp_data_terms/ when present. Nothing here is endorsed by the School District.
"""


def build_package(
    source_keys: list[str],
    out_dir: Path,
    name: str,
    title: str,
    notes: str = "",
    extra_files: list[Path] | None = None,
) -> Path:
    rows = [d for d in read_downloads() if d["source_key"] in source_keys]
    terms = [d for d in read_downloads() if d["source_key"] == "sdp_data_terms"]
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.zip"
    missing = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for d in rows + terms:
            path = ROOT / d["local_path"]
            if not path.exists():
                missing.append(d["local_path"])
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != d["sha256"]:
                raise ValueError(f"hash mismatch, refusing to package: {d['local_path']}")
            stored = path.suffix.lower() in ALREADY_COMPRESSED
            z.write(
                path,
                d["local_path"],
                compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED,
            )
        for extra in extra_files or []:
            z.write(extra, extra.name)
        buf = io.StringIO()
        fields = ["source_key", "url", "local_path", "retrieved_at_utc", "sha256", "bytes"]
        w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows + terms)
        z.writestr("MANIFEST.csv", buf.getvalue())
        z.writestr(
            "README.md",
            README.format(
                title=title,
                date=datetime.now(UTC).date().isoformat(),
                sources=", ".join(source_keys),
                notes=notes,
            ),
        )
    if missing:
        raise FileNotFoundError(f"{len(missing)} manifest files missing locally, e.g. {missing[0]}")
    return target
