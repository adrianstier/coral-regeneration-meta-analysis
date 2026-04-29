from __future__ import annotations

import csv
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "pipeline"
DATA_DIR = ROOT / "data"
SCREENING_DIR = DATA_DIR / "screening"
EXTRACTION_DIR = DATA_DIR / "extraction"
LITERATURE_DATA_DIR = DATA_DIR / "literature"

SCREENING_LOG = SCREENING_DIR / "SCREENING_LOG_FINAL.csv"
HYPOTHESIS_MATRIX = SCREENING_DIR / "HYPOTHESIS_X_RESPONSE_MATRIX.csv"
MISSINGNESS_CSV = ROOT / "notebook_covariates" / "notebook_covariate_missingness_primary_geoaugmented.csv"
LITERATURE_MAP = LITERATURE_DATA_DIR / "LITERATURE_MAP.csv"

EXTRACTION_TABLES = {
    "rate": EXTRACTION_DIR / "EXTRACTION_RATES.csv",
    "growth": EXTRACTION_DIR / "EXTRACTION_FITNESS.csv",
    "reproduction": EXTRACTION_DIR / "EXTRACTION_FITNESS.csv",
    "survival": EXTRACTION_DIR / "EXTRACTION_SURVIVAL.csv",
}

RESPONSE_COLUMNS = {
    "rate": "response_rate",
    "growth": "response_growth",
    "reproduction": "response_reproduction",
    "survival": "response_survival",
    "mechanism": "response_mechanism",
}

PRIMARY_RESPONSES = ("rate", "growth", "reproduction", "survival")
WORKPLAN_RESPONSES = ("rate", "growth", "reproduction", "survival", "mechanism")

EXPECTED_FOLDERS = {
    "include_primary": {"META_ANALYSIS_POOL"},
    "include_mechanism_only": {"MECHANISMS_ONLY"},
    "exclude_scope": {"EXCLUDED_FINAL"},
    "exclude_review": {"EXCLUDED_FINAL"},
    "duplicate_alias": {"DUPLICATES"},
}


def ascii_text(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")


def normalize_key(text: str) -> str:
    text = ascii_text(text).lower()
    text = text.replace("_", " ")
    text = re.sub(r"\.pdf$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_git(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]


def git_blob_for_file(path: Path) -> str:
    proc = subprocess.run(
        ["git", "hash-object", str(path.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def parse_tracked_literature_blobs() -> dict[str, str]:
    blobs: dict[str, str] = {}
    for line in run_git(["ls-tree", "-r", "HEAD", "literature"]):
        if "\t" not in line:
            continue
        meta, relpath = line.split("\t", 1)
        parts = meta.split()
        if len(parts) >= 3:
            blobs[relpath] = parts[2]
    return blobs


def staged_literature_renames() -> dict[str, str]:
    renames: dict[str, str] = {}
    for line in run_git(["diff", "--cached", "--name-status", "--find-renames", "--", "literature"]):
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].startswith("R"):
            continue
        old_relpath, new_relpath = parts[1], parts[2]
        if old_relpath.endswith(".pdf") and new_relpath.endswith(".pdf"):
            renames[old_relpath] = new_relpath
    return renames


def existing_pdf_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    literature = ROOT / "literature"
    if not literature.exists():
        return index
    for path in literature.rglob("*.pdf"):
        index[path.name].append(path)
    return index


def literature_pdf_count() -> int:
    literature = ROOT / "literature"
    return sum(1 for _ in literature.rglob("*.pdf")) if literature.exists() else 0


def summarize_literature_reorg_rows(rows: list[dict[str, str]]) -> dict[str, int]:
    hash_status_counts = Counter(row.get("hash_status", "") for row in rows)
    return {
        "deleted_flat_pdf_count": len(rows),
        "current_literature_pdf_count": literature_pdf_count(),
        "matched_deleted_to_organized_by_filename": sum(
            1 for row in rows if row.get("filename_match_count") == "1"
        ),
        "hash_matches": hash_status_counts["hash_match"],
        "hash_mismatches": hash_status_counts["hash_mismatch"],
        "missing_organized_copy": hash_status_counts["missing_organized_copy"],
        "duplicate_organized_filename": hash_status_counts["duplicate_organized_filename"],
    }


def read_historical_literature_reorg_audit() -> list[dict[str, str]]:
    current_audit = OUTPUT_DIR / "LITERATURE_REORG_AUDIT.csv"
    current_rows = read_csv(current_audit)
    if current_rows:
        return current_rows

    proc = subprocess.run(
        ["git", "show", "HEAD:pipeline/LITERATURE_REORG_AUDIT.csv"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    return list(csv.DictReader(proc.stdout.splitlines()))


def build_literature_reorg_audit() -> tuple[list[dict[str, str]], dict[str, int]]:
    deleted = [line for line in run_git(["ls-files", "--deleted", "literature"]) if line.endswith(".pdf")]
    staged_renames = staged_literature_renames()
    deleted_or_renamed = sorted(set(deleted) | set(staged_renames))
    if not deleted_or_renamed:
        rows = read_historical_literature_reorg_audit()
        return rows, summarize_literature_reorg_rows(rows)

    tracked_blobs = parse_tracked_literature_blobs()
    pdf_index = existing_pdf_index()
    rows: list[dict[str, str]] = []

    for relpath in deleted_or_renamed:
        filename = Path(relpath).name
        if relpath in staged_renames:
            staged_path = ROOT / staged_renames[relpath]
            candidates = [staged_path] if staged_path.exists() else []
        else:
            candidates = pdf_index.get(filename, [])
        organized_relpath = ""
        current_blob = ""
        if len(candidates) == 1:
            organized_relpath = str(candidates[0].relative_to(ROOT))
            current_blob = git_blob_for_file(candidates[0])
        tracked_blob = tracked_blobs.get(relpath, "")
        if not candidates:
            hash_status = "missing_organized_copy"
        elif len(candidates) > 1:
            hash_status = "duplicate_organized_filename"
        elif tracked_blob and current_blob == tracked_blob:
            hash_status = "hash_match"
        elif tracked_blob and current_blob:
            hash_status = "hash_mismatch"
        else:
            hash_status = "not_checked"
        rows.append(
            {
                "deleted_flat_relpath": relpath,
                "organized_relpath": organized_relpath,
                "filename_match_count": str(len(candidates)),
                "tracked_blob_sha": tracked_blob,
                "organized_blob_sha": current_blob,
                "hash_status": hash_status,
            }
        )

    return rows, summarize_literature_reorg_rows(rows)


def response_types(row: dict[str, str], include_mechanism: bool = True) -> list[str]:
    responses = []
    for response in WORKPLAN_RESPONSES:
        if response == "mechanism" and not include_mechanism:
            continue
        if truthy(row.get(RESPONSE_COLUMNS[response], "")):
            responses.append(response)
    return responses


def covariate_missingness_by_source() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in read_csv(MISSINGNESS_CSV):
        missing_fields = [
            field.replace("missing_", "")
            for field, value in row.items()
            if field.startswith("missing_") and truthy(value)
        ]
        out[row.get("source_id", "")] = {
            "covariate_missing_count": str(len(missing_fields)),
            "covariate_missing_fields": "|".join(missing_fields),
        }
    return out


def extraction_index_for_response() -> dict[str, dict[str, set[str]]]:
    out: dict[str, dict[str, set[str]]] = {}
    for response, path in EXTRACTION_TABLES.items():
        source_ids: set[str] = set()
        author_year_keys: set[str] = set()
        for row in read_csv(path):
            row_response = row.get("response_type", "").strip()
            if row_response and row_response != response:
                continue
            source_id = row.get("source_id", "").strip()
            if source_id:
                source_ids.add(source_id)
            author = row.get("Author", "")
            year = row.get("Year", "")
            if author or year:
                author_year_keys.add(normalize_key(f"{author} {year}"))
        out[response] = {"source_ids": source_ids, "author_year_keys": author_year_keys}
    return out


def source_key(row: dict[str, str]) -> str:
    title = row.get("paper_title") or row.get("local_filename") or ""
    match = re.search(r"^(.*?)\b((?:19|20)\d{2})\b", normalize_key(title))
    if not match:
        return normalize_key(title).split(" ")[0] if title else ""
    left = match.group(1).strip().split()
    author = left[0] if left else ""
    return normalize_key(f"{author} {match.group(2)}")


def existing_extraction_match(
    row: dict[str, str],
    response: str,
    extraction_index: dict[str, dict[str, set[str]]],
) -> str:
    response_index = extraction_index.get(response, {})
    if row.get("source_id") in response_index.get("source_ids", set()):
        return "source_id_match"
    key = source_key(row)
    if not key:
        return "not_checked_no_author_year"
    if key in response_index.get("author_year_keys", set()):
        return "author_year_match"
    return "no_author_year_match"


def local_pdf_status(row: dict[str, str]) -> str:
    local_relpath = row.get("local_relpath", "")
    if local_relpath and (ROOT / local_relpath).exists():
        return "local_pdf_available"
    if truthy(row.get("local_present", "")):
        return "declared_present_but_missing"
    return "missing_local_pdf"


def expected_folder_status(row: dict[str, str]) -> tuple[str, str]:
    status = row.get("final_status", "")
    folder = row.get("current_folder", "")
    expected = EXPECTED_FOLDERS.get(status, set())
    if not expected:
        return "", "unknown_final_status"
    if not truthy(row.get("local_present", "")) and not row.get("local_relpath", ""):
        return "|".join(sorted(expected)), "ok"
    if folder in expected:
        return "|".join(sorted(expected)), "ok"
    return "|".join(sorted(expected)), "folder_needs_review"


def build_literature_organization_audit(screening_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in screening_rows:
        expected, folder_status = expected_folder_status(row)
        local_relpath = row.get("local_relpath", "")
        local_file_exists = "1" if local_relpath and (ROOT / local_relpath).exists() else "0"
        local_present = "1" if truthy(row.get("local_present", "")) else "0"
        rows.append(
            {
                "source_id": row.get("source_id", ""),
                "paper_title": row.get("paper_title", ""),
                "final_status": row.get("final_status", ""),
                "extraction_readiness": row.get("extraction_readiness", ""),
                "local_relpath": local_relpath,
                "current_folder": row.get("current_folder", ""),
                "notebook_present": "1" if truthy(row.get("notebook_present", "")) else "0",
                "local_present": local_present,
                "local_file_exists": local_file_exists,
                "expected_folder_group": expected,
                "folder_status": folder_status,
                "local_presence_status": (
                    "ok"
                    if (local_present == local_file_exists)
                    else "declared_present_but_missing"
                    if local_present == "1"
                    else "exists_but_not_declared_present"
                ),
            }
        )
    return rows


def priority_for(row: dict[str, str], response: str) -> tuple[int, str]:
    status = row.get("final_status", "")
    readiness = row.get("extraction_readiness", "")
    if status == "include_primary" and local_pdf_status(row) != "local_pdf_available":
        return 0, "retrieve_local_pdf_before_extraction"
    if status == "include_primary" and readiness == "ready_extract":
        return 1, "extract_from_tables_or_text"
    if status == "include_primary" and readiness == "needs_digitization":
        return 2, "digitize_figures_or_graphs"
    if status == "include_primary":
        return 3, "primary_check_readiness"
    if status == "include_mechanism_only" and response == "mechanism":
        return 4, "mechanism_narrative"
    return 9, "not_in_workplan"


def build_extraction_workplan(screening_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    cov_missing = covariate_missingness_by_source()
    extraction_index = extraction_index_for_response()
    rows: list[dict[str, str]] = []

    for row in screening_rows:
        status = row.get("final_status", "")
        if status not in {"include_primary", "include_mechanism_only"}:
            continue
        for response in response_types(row):
            if status == "include_mechanism_only" and response != "mechanism":
                continue
            if status == "include_primary" and response == "mechanism":
                continue
            priority_rank, action = priority_for(row, response)
            file_status = local_pdf_status(row)
            missing = cov_missing.get(row.get("source_id", ""), {})
            requires_digitization = (
                status == "include_primary"
                and response in PRIMARY_RESPONSES
                and row.get("extraction_readiness", "") == "needs_digitization"
            )
            extraction_match = (
                existing_extraction_match(row, response, extraction_index)
                if response in PRIMARY_RESPONSES
                else "not_applicable"
            )
            extraction_status = (
                "started" if extraction_match in {"source_id_match", "author_year_match"} else "not_started"
            )
            if status == "include_primary" and file_status != "local_pdf_available":
                extraction_status = "blocked_missing_local_pdf"
            if response == "mechanism":
                extraction_status = "narrative_not_effect_size"
            rows.append(
                {
                    "priority_rank": str(priority_rank),
                    "recommended_action": action,
                    "extraction_status": extraction_status,
                    "requires_digitization": "1" if requires_digitization else "0",
                    "source_id": row.get("source_id", ""),
                    "paper_title": row.get("paper_title", ""),
                    "local_relpath": row.get("local_relpath", ""),
                    "source_file_status": file_status,
                    "current_folder": row.get("current_folder", ""),
                    "final_status": status,
                    "extraction_readiness": row.get("extraction_readiness", ""),
                    "response_type": response,
                    "covariate_missing_count": missing.get("covariate_missing_count", ""),
                    "covariate_missing_fields": missing.get("covariate_missing_fields", ""),
                    "notebook_present": "1" if truthy(row.get("notebook_present", "")) else "0",
                    "local_present": "1" if truthy(row.get("local_present", "")) else "0",
                    "existing_extraction_match": extraction_match,
                    "figure_queue_needed": "1" if requires_digitization else "0",
                    "final_rationale": row.get("final_rationale", ""),
                }
            )

    rows.sort(key=lambda r: (int(r["priority_rank"]), r["paper_title"], r["response_type"]))
    return rows


def build_digitization_queue(workplan_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in workplan_rows:
        if row.get("requires_digitization") != "1":
            continue
        queue_id = f"DIG-{(row.get('source_id') or 'source')[:8]}-{row.get('response_type', 'response')}"
        file_status = row.get("source_file_status", "")
        blocked = file_status != "local_pdf_available"
        rows.append(
            {
                "queue_id": queue_id,
                "digitization_status": "blocked_missing_local_pdf" if blocked else "needs_figure_id",
                "source_id": row.get("source_id", ""),
                "paper_title": row.get("paper_title", ""),
                "response_type": row.get("response_type", ""),
                "source_file_status": file_status,
                "local_relpath": row.get("local_relpath", ""),
                "figure_or_table_label": "",
                "page": "",
                "panel_label": "",
                "expected_metric": row.get("response_type", ""),
                "x_axis": "",
                "y_axis": "",
                "units": "",
                "variance_type": "",
                "sample_size_source": "",
                "clip_path": "",
                "digitized_data_path": "",
                "digitizer": "",
                "qa_reviewer": "",
                "qa_status": "blocked" if blocked else "not_started",
                "notes": (
                    "Retrieve the local PDF before figure/table identification and clipping."
                    if blocked
                    else "Identify the exact figure/table label, page, panel, axes, units, variance, and sample-size source before clipping."
                ),
            }
        )
    return rows


def build_literature_map(screening_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in screening_rows:
        rows.append(
            {
                "source_id": row.get("source_id", ""),
                "paper_title": row.get("paper_title", ""),
                "final_status": row.get("final_status", ""),
                "extraction_readiness": row.get("extraction_readiness", ""),
                "notebook_present": "1" if truthy(row.get("notebook_present", "")) else "0",
                "local_present": "1" if truthy(row.get("local_present", "")) else "0",
                "local_relpath": row.get("local_relpath", ""),
                "local_filename": row.get("local_filename", ""),
                "current_folder": row.get("current_folder", ""),
                "alias_of": row.get("alias_of", ""),
                "response_types": "|".join(response_types(row)),
                "final_rationale": row.get("final_rationale", ""),
            }
        )
    return rows


def markdown_table(counter: Counter[str] | dict[str, int], label_name: str = "Category") -> str:
    lines = [f"| {label_name} | Count |", "| --- | ---: |"]
    for key, value in sorted(counter.items()):
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines)


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def build_prisma_counts(screening_rows: list[dict[str, str]], reorg_summary: dict[str, int]) -> str:
    final_status = Counter(row.get("final_status", "") for row in screening_rows)
    readiness = Counter(row.get("extraction_readiness", "") for row in screening_rows)
    local_present = Counter("present" if truthy(row.get("local_present", "")) else "missing" for row in screening_rows)
    primary_local_present = Counter(
        "present" if local_pdf_status(row) == "local_pdf_available" else "missing"
        for row in screening_rows
        if row.get("final_status") == "include_primary"
    )
    notebook_present = Counter(
        "present" if truthy(row.get("notebook_present", "")) else "missing" for row in screening_rows
    )
    response_counts = Counter()
    for row in screening_rows:
        for response in WORKPLAN_RESPONSES:
            if truthy(row.get(RESPONSE_COLUMNS[response], "")):
                response_counts[response] += 1

    primary = final_status["include_primary"]
    mechanism = final_status["include_mechanism_only"]
    excluded = final_status["exclude_scope"] + final_status["exclude_review"]
    duplicate = final_status["duplicate_alias"]
    screened = len(screening_rows)

    return "\n".join(
        [
            "# PRISMA Counts",
            "",
            "Generated from `data/screening/SCREENING_LOG_FINAL.csv` by `tools/build_pipeline_outputs.py`.",
            "",
            "## Flow Summary",
            "",
            f"- Records in adjudicated full-text library: {screened}",
            f"- Duplicate aliases retained only for traceability: {duplicate}",
            f"- Full-text records excluded from the primary synthesis: {excluded}",
            f"- Mechanism-only records retained for narrative synthesis: {mechanism}",
            f"- Primary quantitative records included in the meta-analysis pool: {primary}",
            f"- Primary records ready for table/text extraction: {readiness['ready_extract']}",
            f"- Primary records needing figure/table digitization: {readiness['needs_digitization']}",
            f"- Primary records currently missing a local PDF: {primary_local_present['missing']}",
            "",
            "## Final Status",
            "",
            markdown_table(final_status, "Final status"),
            "",
            "## Extraction Readiness",
            "",
            markdown_table(readiness, "Readiness"),
            "",
            "## Response Coverage",
            "",
            markdown_table(response_counts, "Response"),
            "",
            "## Source Availability",
            "",
            "NotebookLM coverage:",
            "",
            markdown_table(notebook_present, "NotebookLM status"),
            "",
            "Local PDF coverage:",
            "",
            markdown_table(local_present, "Local PDF status"),
            "",
            "Primary local PDF coverage:",
            "",
            markdown_table(primary_local_present, "Primary local PDF status"),
            "",
            "## Literature Reorganization Check",
            "",
            f"- Deleted flat tracked PDFs reported by git: {reorg_summary['deleted_flat_pdf_count']}",
            f"- Current PDFs under `literature/`: {reorg_summary['current_literature_pdf_count']}",
            f"- Deleted flat PDFs matched to one organized filename: {reorg_summary['matched_deleted_to_organized_by_filename']}",
            f"- Exact blob hash matches among matched files: {reorg_summary['hash_matches']}",
            f"- Hash mismatches: {reorg_summary['hash_mismatches']}",
            f"- Missing organized copies: {reorg_summary['missing_organized_copy']}",
            f"- Duplicate organized filenames needing manual resolution: {reorg_summary['duplicate_organized_filename']}",
            "",
        ]
    )


def build_qa_report(
    screening_rows: list[dict[str, str]],
    org_rows: list[dict[str, str]],
    workplan_rows: list[dict[str, str]],
    digitization_rows: list[dict[str, str]],
    reorg_summary: dict[str, int],
) -> str:
    final_status = Counter(row.get("final_status", "") for row in screening_rows)
    response_workplan = Counter(row.get("response_type", "") for row in workplan_rows)
    action_counts = Counter(row.get("recommended_action", "") for row in workplan_rows)

    duplicate_source_ids = [
        source_id
        for source_id, count in Counter(row.get("source_id", "") for row in screening_rows if row.get("source_id")).items()
        if count > 1
    ]
    folder_needs_review = [row for row in org_rows if row.get("folder_status") != "ok"]
    missing_files = [row for row in org_rows if row.get("local_presence_status") == "declared_present_but_missing"]
    primary_missing_local = [
        row
        for row in org_rows
        if row.get("final_status") == "include_primary" and row.get("local_file_exists") != "1"
    ]
    workplan_blocked_missing_local = [
        row for row in workplan_rows if row.get("extraction_status") == "blocked_missing_local_pdf"
    ]
    digitization_blocked_missing_local = [
        row for row in digitization_rows if row.get("digitization_status") == "blocked_missing_local_pdf"
    ]
    digitization_needs_figure_id = [
        row for row in digitization_rows if row.get("digitization_status") == "needs_figure_id"
    ]
    primary_without_response = [
        row
        for row in screening_rows
        if row.get("final_status") == "include_primary" and not response_types(row, include_mechanism=False)
    ]

    warnings: list[str] = []
    if duplicate_source_ids:
        warnings.append(f"{len(duplicate_source_ids)} duplicate source IDs found.")
    if missing_files:
        warnings.append(f"{len(missing_files)} rows declare a local PDF but the file is missing.")
    if primary_missing_local:
        count = len(primary_missing_local)
        warnings.append(f"{count} included primary {pluralize(count, 'record')} {'is' if count == 1 else 'are'} missing a local PDF.")
    if workplan_blocked_missing_local:
        warnings.append(f"{len(workplan_blocked_missing_local)} extraction workplan rows are blocked by missing local PDFs.")
    if digitization_blocked_missing_local:
        warnings.append(f"{len(digitization_blocked_missing_local)} digitization rows are blocked by missing local PDFs.")
    if digitization_needs_figure_id:
        warnings.append(
            f"{len(digitization_needs_figure_id)} digitization rows still need exact figure/table labels before clipping."
        )
    if primary_without_response:
        warnings.append(f"{len(primary_without_response)} primary rows have no primary response flag.")
    if folder_needs_review:
        warnings.append(f"{len(folder_needs_review)} rows have folder placement that should be reviewed.")
    if reorg_summary["hash_mismatches"]:
        warnings.append(f"{reorg_summary['hash_mismatches']} reorganized PDFs differ from their tracked blobs.")
    if reorg_summary["missing_organized_copy"]:
        warnings.append(f"{reorg_summary['missing_organized_copy']} deleted flat PDFs have no organized filename match.")

    warning_block = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- No blocking QA warnings."

    top_folder_review = "\n".join(
        f"- `{row['final_status']}` in `{row['current_folder'] or '(blank)'}`: {row['paper_title']}"
        for row in folder_needs_review[:20]
    )
    if not top_folder_review:
        top_folder_review = "- None."

    missing_source_review = "\n".join(
        f"- `{row['extraction_readiness']}`: {row['paper_title']}" for row in primary_missing_local[:20]
    )
    if not missing_source_review:
        missing_source_review = "- None."

    digitization_status = Counter(row.get("digitization_status", "") for row in digitization_rows)

    return "\n".join(
        [
            "# Pipeline QA Report",
            "",
            "Generated from the current repository state by `tools/build_pipeline_outputs.py`.",
            "",
            "## Status",
            "",
            markdown_table(final_status, "Final status"),
            "",
            "## Extraction Workplan",
            "",
            f"- Workplan rows: {len(workplan_rows)}",
            f"- Digitization figure queue rows: {len(digitization_rows)}",
            "",
            markdown_table(response_workplan, "Response"),
            "",
            markdown_table(action_counts, "Recommended action"),
            "",
            "Digitization status:",
            "",
            markdown_table(digitization_status, "Digitization status"),
            "",
            "## QA Warnings",
            "",
            warning_block,
            "",
            "## Folder Placements To Review",
            "",
            top_folder_review,
            "",
            "## Included Primary Sources To Retrieve",
            "",
            missing_source_review,
            "",
            "## Literature Reorganization",
            "",
            f"- Deleted flat tracked PDFs: {reorg_summary['deleted_flat_pdf_count']}",
            f"- Current PDFs under `literature/`: {reorg_summary['current_literature_pdf_count']}",
            f"- Hash-matched organized copies: {reorg_summary['hash_matches']}",
            f"- Hash mismatches: {reorg_summary['hash_mismatches']}",
            f"- Missing organized copies: {reorg_summary['missing_organized_copy']}",
            "",
        ]
    )


def build_manifest() -> str:
    return "\n".join(
        [
            "# Generated Pipeline Outputs",
            "",
            "These files are generated by `python3 tools/build_pipeline_outputs.py`.",
            "",
            "Upstream source-of-truth files live under `data/screening/` and `data/extraction/`.",
            "`data/literature/LITERATURE_MAP.csv` is also refreshed from the screening source of truth.",
            "",
            "- `PRISMA_COUNTS.md`: manuscript-facing PRISMA/full-text count summary.",
            "- `LITERATURE_ORGANIZATION_AUDIT.csv`: row-level check of screening status, local files, and folder placement.",
            "- `LITERATURE_REORG_AUDIT.csv`: git-aware check that deleted flat PDFs have organized copies with matching blob hashes.",
            "- `EXTRACTION_WORKPLAN.csv`: response-level extraction queue for included primary and mechanism-only studies.",
            "- `DIGITIZATION_FIGURE_QUEUE.csv`: figure/table clipping and digitization manifest for primary studies that need digitization.",
            "- `PIPELINE_QA_REPORT.md`: compact QA warnings and next actions.",
            "",
            "Do not edit generated files as the source of truth. Edit the upstream screening/extraction inputs, then rebuild.",
            "",
        ]
    )


def main() -> int:
    screening_rows = read_csv(SCREENING_LOG)
    if not screening_rows:
        raise SystemExit(f"Missing or empty source file: {SCREENING_LOG.relative_to(ROOT)}")

    org_rows = build_literature_organization_audit(screening_rows)
    reorg_rows, reorg_summary = build_literature_reorg_audit()
    workplan_rows = build_extraction_workplan(screening_rows)
    digitization_rows = build_digitization_queue(workplan_rows)
    literature_map_rows = build_literature_map(screening_rows)

    write_csv(
        LITERATURE_MAP,
        [
            "source_id",
            "paper_title",
            "final_status",
            "extraction_readiness",
            "notebook_present",
            "local_present",
            "local_relpath",
            "local_filename",
            "current_folder",
            "alias_of",
            "response_types",
            "final_rationale",
        ],
        literature_map_rows,
    )

    write_csv(
        OUTPUT_DIR / "LITERATURE_ORGANIZATION_AUDIT.csv",
        [
            "source_id",
            "paper_title",
            "final_status",
            "extraction_readiness",
            "local_relpath",
            "current_folder",
            "notebook_present",
            "local_present",
            "local_file_exists",
            "expected_folder_group",
            "folder_status",
            "local_presence_status",
        ],
        org_rows,
    )
    write_csv(
        OUTPUT_DIR / "LITERATURE_REORG_AUDIT.csv",
        [
            "deleted_flat_relpath",
            "organized_relpath",
            "filename_match_count",
            "tracked_blob_sha",
            "organized_blob_sha",
            "hash_status",
        ],
        reorg_rows,
    )
    write_csv(
        OUTPUT_DIR / "EXTRACTION_WORKPLAN.csv",
        [
            "priority_rank",
            "recommended_action",
            "extraction_status",
            "requires_digitization",
            "source_id",
            "paper_title",
            "local_relpath",
            "source_file_status",
            "current_folder",
            "final_status",
            "extraction_readiness",
            "response_type",
            "covariate_missing_count",
            "covariate_missing_fields",
            "notebook_present",
            "local_present",
            "existing_extraction_match",
            "figure_queue_needed",
            "final_rationale",
        ],
        workplan_rows,
    )
    write_csv(
        OUTPUT_DIR / "DIGITIZATION_FIGURE_QUEUE.csv",
        [
            "queue_id",
            "digitization_status",
            "source_id",
            "paper_title",
            "response_type",
            "source_file_status",
            "local_relpath",
            "figure_or_table_label",
            "page",
            "panel_label",
            "expected_metric",
            "x_axis",
            "y_axis",
            "units",
            "variance_type",
            "sample_size_source",
            "clip_path",
            "digitized_data_path",
            "digitizer",
            "qa_reviewer",
            "qa_status",
            "notes",
        ],
        digitization_rows,
    )
    write_text(OUTPUT_DIR / "PRISMA_COUNTS.md", build_prisma_counts(screening_rows, reorg_summary))
    write_text(
        OUTPUT_DIR / "PIPELINE_QA_REPORT.md",
        build_qa_report(screening_rows, org_rows, workplan_rows, digitization_rows, reorg_summary),
    )
    write_text(OUTPUT_DIR / "PIPELINE_MANIFEST.md", build_manifest())

    print(f"Wrote pipeline outputs to {OUTPUT_DIR.relative_to(ROOT)}")
    print(f"Screening records: {len(screening_rows)}")
    print(f"Extraction workplan rows: {len(workplan_rows)}")
    print(f"Digitization queue rows: {len(digitization_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
