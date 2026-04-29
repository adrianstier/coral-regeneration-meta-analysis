from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCREENING_LOG = ROOT / "data" / "screening" / "SCREENING_LOG_FINAL.csv"

TARGET_FOLDERS = {
    "include_primary": "META_ANALYSIS_POOL",
    "include_mechanism_only": "MECHANISMS_ONLY",
    "exclude_scope": "EXCLUDED_FINAL",
    "exclude_review": "EXCLUDED_FINAL",
    "duplicate_alias": "DUPLICATES",
}


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_screening(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_screening(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def target_for_row(row: dict[str, str]) -> Path | None:
    relpath = row.get("local_relpath", "")
    filename = row.get("local_filename", "") or Path(relpath).name
    final_status = row.get("final_status", "")
    target_folder = TARGET_FOLDERS.get(final_status)
    if not relpath or not filename or not target_folder:
        return None
    return ROOT / "literature" / target_folder / filename


def organize(screening_path: Path, apply: bool) -> tuple[int, int, list[str]]:
    rows, fieldnames = read_screening(screening_path)
    moved = 0
    updated = 0
    warnings: list[str] = []

    for row in rows:
        if row.get("final_status") == "duplicate_alias" and row.get("alias_of") == row.get("paper_title"):
            if row.get("local_present") != "0" or row.get("local_relpath") or row.get("local_filename"):
                row["local_present"] = "0"
                row["local_relpath"] = ""
                row["local_filename"] = ""
                row["current_folder"] = "DUPLICATES"
                updated += 1
            continue

        target = target_for_row(row)
        relpath = row.get("local_relpath", "")
        source = ROOT / relpath if relpath else None
        if target is None:
            continue

        target_relpath = str(target.relative_to(ROOT))
        if relpath == target_relpath:
            continue

        if source is not None and source.exists():
            if target.exists():
                if file_digest(source) != file_digest(target):
                    warnings.append(f"target exists with different content: {target_relpath}")
                    continue
                if apply:
                    source.unlink()
            else:
                if apply:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source), str(target))
            moved += 1
        elif target.exists():
            pass
        else:
            warnings.append(f"missing source and target for {row.get('paper_title', '')}: {relpath}")
            continue

        row["local_relpath"] = target_relpath
        row["current_folder"] = target.parent.name
        updated += 1

    if apply:
        write_screening(screening_path, rows, fieldnames)

    return moved, updated, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screening-log", default=str(SCREENING_LOG))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    moved, updated, warnings = organize(Path(args.screening_log), args.apply)
    mode = "applied" if args.apply else "dry_run"
    print(f"mode={mode}")
    print(f"moved_files={moved}")
    print(f"updated_rows={updated}")
    print(f"warnings={len(warnings)}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
