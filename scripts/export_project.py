#!/usr/bin/env python3
"""Create a GitHub-ready source archive without credentials or hosting identity."""
from pathlib import Path
import argparse
import json
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "exports/mars-libs-github.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    selected = []
    for folder in [ROOT / "dist", ROOT / "data", ROOT / "scripts", ROOT / ".github"]:
        for file in folder.rglob("*"):
            if not file.is_file() or file.resolve() == output:
                continue
            rel = file.relative_to(ROOT)
            if any(part in {"raw", "__pycache__", "downloads", ".openai", "server", ".cache"} for part in rel.parts):
                continue
            if file.suffix == ".pyc" or file.name in {"data.json", "data.json.gz"}:
                continue
            selected.append(file)
    for name in ["README.md", "DATA_SOURCES.md", "LICENSE", "requirements.txt", ".gitignore", "VALIDATION.json", "CONTEXT_VALIDATION.json", "QA.md", "SCHEDULED_UPDATES.md", "PHONE_SETUP.md", "MAR_TO_GIS.md"]:
        path = ROOT / name
        if path.exists():
            selected.append(path)
    # Omit redundant gzip transport copies in this downloadable source bundle.
    # The complete plain JSON remains, and metadata selects that supported path.
    # This keeps the portable archive small enough for static hosting.
    count = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(selected):
            rel = file.relative_to(ROOT)
            if file.name.endswith(".json.gz"):
                continue
            content = file.read_bytes()
            if rel.as_posix() in {"dist/data/chemcam.json", "dist/data/supercam.json"}:
                meta = json.loads(content)
                meta.pop("point_files_gzip", None)
                meta.pop("traverse_files_gzip", None)
                meta["packaging"]["transport"] = "plain_json_portable_export"
                content = json.dumps(meta, separators=(",", ":"), ensure_ascii=False).encode()
            archive.writestr("mars-libs-explorer/" + rel.as_posix(), content)
            count += 1
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Archive integrity failure: {bad}")
        names = set(archive.namelist())
        for required in ["dist/index.html", "dist/app.js", "dist/styles.css", ".github/workflows/update-data.yml", "README.md"]:
            if "mars-libs-explorer/" + required not in names:
                raise ValueError(f"Missing {required}")
    content = output.read_bytes()
    print(json.dumps({"archive": str(output), "files": count, "bytes": len(content),
                      "sha256": hashlib.sha256(content).hexdigest()}))


if __name__ == "__main__":
    main()
