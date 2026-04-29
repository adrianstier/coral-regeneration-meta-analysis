from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STOPWORDS = {
    "a",
    "an",
    "and",
    "after",
    "by",
    "during",
    "effect",
    "effects",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "under",
    "with",
}

HEAD_RE = re.compile(r"(?m)^(?:###\s*)?\*\*(.+?)\*\*$")
VERDICT_RE = re.compile(
    r"(?:\*\*)?Final Verdict:(?:\*\*)?\s*(?:\*\*)?(\[[^\]]+\]|Narrative/Mechanism Only)(?:\*\*)?",
    re.S,
)
REASON_RE = re.compile(
    r"(?:\*\*)?Final Verdict:(?:\*\*)?\s*(?:\*\*)?(?:\[[^\]]+\]|Narrative/Mechanism Only)(?:\*\*)?\.?\s*(.*)",
    re.S,
)

PRIMARY_BINS = {"rate", "growth", "reproduction", "survival"}
SOFT_REVIEW_MARKERS = (
    "provided text excerpt",
    "provided text excerpts",
    "provided text",
    "extractable",
    "figure digitization",
    "digitization",
    "supplementary material",
    "supplementary materials",
    "supplementary",
    "raw tables",
    "raw extractable",
    "missing from the data pool",
    "missing from the corpus",
    "missing from the notebook",
    "without access to the paper",
    "not included in the excerpts",
    "fails to report variance",
    "lacks a standardized daily",
    "total time to heal",
    "categorical healing endpoints",
    "proportional healing",
)
REVIEW_MARKERS = (
    "review paper",
    "literature review",
    "book chapter",
    "review summarizing",
)
SCOPE_EXCLUDE_MARKERS = (
    "sponges",
    "demospongiae",
    "gorgonian",
    "octocoral",
    "outside the scope",
    "does not evaluate wound healing",
    "does not meet the criteria for a wound-regeneration",
    "lacks any macroscopic tissue outcomes",
    "fish assemblages",
    "genomics",
    "transcriptomics study that lacks macroscopic",
)
SOURCE_LOCAL_THRESHOLD = 0.70
RECORD_LOCAL_THRESHOLD = 0.78
SOURCE_MATCH_THRESHOLD = 0.55
MANUAL_SOURCE_TO_LOCAL_HINTS = {
    "host and symbiont physiology during wound regenerat": "host and symbiont physiology during wound regeneration in acropora pulchra",
    "injury and regeneration of common reef crest corals": "injury and regeneration of common reef crest corals",
    "quantifying physiological responses to physical injury": "quantifying physiological responses to physical injury in porites lobata",
}


@dataclass
class AuditRecord:
    audit_title: str
    verdict: str
    reason: str
    response_bins: list[str]
    author: str
    year: str
    title_rest: str
    normalized: str


@dataclass
class NotebookSource:
    source_id: str
    title: str
    author: str
    year: str
    title_rest: str
    normalized: str


@dataclass
class LocalPdf:
    relpath: str
    filename: str
    folder: str
    author: str
    year: str
    title_rest: str
    normalized: str


@dataclass
class Entry:
    source: NotebookSource | None
    source_to_local_score: float
    pdf: LocalPdf | None
    audits: list[AuditRecord]


SCREENING_OUTPUT_FIELDS = [
    "source_id",
    "source_title",
    "notebook_present",
    "local_relpath",
    "local_filename",
    "current_folder",
    "local_present",
    "source_to_local_score",
    "audit_count",
    "audit_titles",
    "audit_verdicts",
    "candidate_bins",
    "conflicting_audits",
    "screening_bucket",
    "screening_notes",
]


def ascii_text(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def prep_title(text: str) -> str:
    text = ascii_text(text)
    text = re.sub(r"^\s*\d+(?:\s*(?:&|and)\s*\d+)?[.)]?\s*", "", text, flags=re.I)
    text = text.replace("_", " ")
    text = text.replace("&", " and ")
    text = text.replace("et al.", "et al")
    text = re.sub(r"doi[-: ]\S+", " ", text, flags=re.I)
    text = re.sub(r"\.pdf$", " ", text, flags=re.I)
    text = re.sub(r"\.{2,}", " ", text)
    return text


def normalize_title(text: str) -> str:
    text = prep_title(text)
    text = re.sub(r"^\d+(?:\s*&\s*\d+)?\.\s*", "", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\*", " ", text)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def split_author_year_title(text: str) -> tuple[str, str, str]:
    normalized = prep_title(text)
    normalized = re.sub(r"^\d+(?:\s*(?:&|and)\s*\d+)?[.)]?\s*", "", normalized, flags=re.I)
    normalized = re.sub(r"\*", " ", normalized)
    normalized = re.sub(r"[^A-Za-z0-9()]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    match = re.search(r"^(.*?)\b((?:19|20)\d{2})\b(.*)$", normalized)
    if not match:
        fallback = re.sub(r"[()]", " ", normalized)
        fallback = re.sub(r"\s+", " ", fallback).strip()
        return "", "", fallback
    left = re.sub(r"[()]", " ", match.group(1)).strip()
    left_words = left.split()
    if not left_words:
        author = ""
    elif len(left_words[0]) == 1 and len(left_words) > 1:
        author = f"{left_words[0]}{left_words[1]}"
    else:
        author = left_words[0]
    year = match.group(2)
    rest = re.sub(r"[()]", " ", match.group(3)).strip()
    return author, year, rest


def response_bins_from_verdict(verdict: str, reason: str) -> list[str]:
    bins: list[str] = []
    verdict_text = verdict.lower()
    include_match = re.search(r"include in bin(?:s)? ([^\]]+)", verdict_text)
    if include_match:
        raw = include_match.group(1)
        for part in re.split(r"[,/]| and ", raw):
            part = part.strip()
            if (part == "1" or part == "rate") and "rate" not in bins:
                bins.append("rate")
            if (part == "2" or part == "growth") and "growth" not in bins:
                bins.append("growth")
            if part in {"3", "reproduction", "repro"} and "reproduction" not in bins:
                bins.append("reproduction")
            if (part == "4" or part == "survival") and "survival" not in bins:
                bins.append("survival")
            if (part == "5" or part == "mechanism") and "mechanism" not in bins:
                bins.append("mechanism")
            if (part == "6" or part == "moderator") and "moderator" not in bins:
                bins.append("moderator")
    if "narrative/mechanism only" in verdict_text and "mechanism" not in bins:
        bins.append("mechanism")
    return bins


def parse_audit_records(audit_path: Path) -> list[AuditRecord]:
    text = audit_path.read_text(errors="ignore")
    sections = re.split(r"(?m)^#{2,3} .*\n", text)[1:]
    records: list[AuditRecord] = []
    for section_index, section in enumerate(sections, start=1):
        section = section.strip()
        if not section.startswith("{"):
            continue
        try:
            data = json.loads(section)
            answer = data["value"].get("answer", "")
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
            print(f"Skipping malformed audit section {section_index}: {exc}", file=sys.stderr)
            continue
        headers = list(HEAD_RE.finditer(answer))
        for index, header in enumerate(headers):
            start = header.end()
            end = headers[index + 1].start() if index + 1 < len(headers) else len(answer)
            block = answer[start:end]
            verdict_match = VERDICT_RE.search(block)
            reason_match = REASON_RE.search(block)
            if not verdict_match or not reason_match:
                continue
            audit_title = header.group(1).strip()
            verdict = verdict_match.group(1).strip()
            reason = reason_match.group(1).split("\n", 1)[0].strip()
            author, year, title_rest = split_author_year_title(audit_title)
            records.append(
                AuditRecord(
                    audit_title=audit_title,
                    verdict=verdict,
                    reason=reason,
                    response_bins=response_bins_from_verdict(verdict, reason),
                    author=author,
                    year=year,
                    title_rest=title_rest,
                    normalized=normalize_title(audit_title),
                )
            )
    return records


def load_notebook_sources(nlm_bin: str, notebook_alias: str) -> list[NotebookSource]:
    raw = subprocess.check_output(
        [nlm_bin, "list", "sources", notebook_alias, "--json"],
        text=True,
    )
    data = json.loads(raw)
    sources: list[NotebookSource] = []
    for row in data:
        title = row["title"]
        author, year, title_rest = split_author_year_title(title)
        sources.append(
            NotebookSource(
                source_id=row["id"],
                title=title,
                author=author,
                year=year,
                title_rest=title_rest,
                normalized=normalize_title(title),
            )
        )
    return sources


def load_local_pdfs(repo_root: Path) -> list[LocalPdf]:
    pdfs: list[LocalPdf] = []
    for path in sorted((repo_root / "literature").glob("**/*.pdf")):
        filename = path.name
        author, year, title_rest = split_author_year_title(filename)
        pdfs.append(
            LocalPdf(
                relpath=str(path.relative_to(repo_root)),
                filename=filename,
                folder=path.parent.name,
                author=author,
                year=year,
                title_rest=title_rest,
                normalized=normalize_title(filename),
            )
        )
    return pdfs


def token_set(text: str) -> set[str]:
    return {token for token in text.split() if token not in STOPWORDS}


def authors_compatible(author: str, other_author: str) -> bool:
    if not author or not other_author:
        return True
    if author == other_author:
        return True
    if len(author) <= 2 and (author in other_author or other_author in author):
        return True
    if author.startswith(other_author) or other_author.startswith(author):
        return True
    return False


def score_match(author: str, year: str, title_rest: str, normalized: str, other: tuple[str, str, str, str]) -> float:
    other_author, other_year, other_title_rest, other_normalized = other
    if year and other_year and year != other_year:
        return -1.0
    seq = __import__("difflib").SequenceMatcher(None, normalized, other_normalized).ratio()
    tokens_a = token_set(title_rest)
    tokens_b = token_set(other_title_rest)
    overlap = len(tokens_a & tokens_b) / len(tokens_a) if tokens_a else seq
    if tokens_a and tokens_b and overlap == 0 and seq < 0.4:
        return -1.0
    base = 0.0
    if authors_compatible(author, other_author):
        base += 0.30 if author and other_author else 0.15
    if year and other_year and year == other_year:
        base += 0.30
    elif year or other_year:
        base += 0.10
    return base + 0.30 * seq + 0.30 * overlap


def best_match_to_sources(record: AuditRecord, sources: Iterable[NotebookSource]) -> tuple[NotebookSource | None, float]:
    scored = [
        (
            score_match(
                record.author,
                record.year,
                record.title_rest,
                record.normalized,
                (source.author, source.year, source.title_rest, source.normalized),
            ),
            source,
        )
        for source in sources
    ]
    scored = [item for item in scored if item[0] >= 0]
    if not scored:
        return None, 0.0
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[0][0]


def best_match_to_local(source: NotebookSource, pdfs: Iterable[LocalPdf]) -> tuple[LocalPdf | None, float]:
    scored = [
        (
            score_match(
                source.author,
                source.year,
                source.title_rest,
                source.normalized,
                (pdf.author, pdf.year, pdf.title_rest, pdf.normalized),
            ),
            pdf,
        )
        for pdf in pdfs
    ]
    scored = [item for item in scored if item[0] >= 0]
    if not scored:
        return None, 0.0
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[0][0]


def score_source_to_local(source: NotebookSource, pdf: LocalPdf) -> float:
    manual_pdf, manual_score = manual_local_match(source.title, [pdf])
    if manual_pdf is not None:
        return manual_score
    return score_match(
        source.author,
        source.year,
        source.title_rest,
        source.normalized,
        (pdf.author, pdf.year, pdf.title_rest, pdf.normalized),
    )


def best_match_record_to_local(record: AuditRecord, pdfs: Iterable[LocalPdf]) -> tuple[LocalPdf | None, float]:
    scored = [
        (
            score_match(
                record.author,
                record.year,
                record.title_rest,
                record.normalized,
                (pdf.author, pdf.year, pdf.title_rest, pdf.normalized),
            ),
            pdf,
        )
        for pdf in pdfs
    ]
    scored = [item for item in scored if item[0] >= 0]
    if not scored:
        return None, 0.0
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[0][0]


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def manual_local_match(title: str, pdfs: Iterable[LocalPdf]) -> tuple[LocalPdf | None, float]:
    normalized_title = prep_title(title).lower()
    for key, hint in MANUAL_SOURCE_TO_LOCAL_HINTS.items():
        if key not in normalized_title:
            continue
        hint_normalized = normalize_title(hint)
        for pdf in pdfs:
            if hint_normalized in pdf.normalized:
                return pdf, 1.5
    return None, 0.0


def candidate_local_match(source: NotebookSource, pdfs: Iterable[LocalPdf]) -> tuple[LocalPdf | None, float]:
    pdf, pdf_score = best_match_to_local(source, pdfs)
    manual_pdf, manual_score = manual_local_match(source.title, pdfs)
    if manual_score > pdf_score:
        pdf, pdf_score = manual_pdf, manual_score
    if pdf_score < SOURCE_LOCAL_THRESHOLD:
        return None, 0.0
    return pdf, pdf_score


def assign_sources_to_local_pdfs(sources: Iterable[NotebookSource], pdfs: Iterable[LocalPdf]) -> dict[str, tuple[LocalPdf, float]]:
    candidates: list[tuple[int, float, str, str, NotebookSource, LocalPdf]] = []
    candidates_by_source: dict[str, int] = {}
    pdf_list = list(pdfs)
    for source in sources:
        source_candidates: list[tuple[float, LocalPdf]] = []
        for pdf in pdf_list:
            score = score_source_to_local(source, pdf)
            if score >= SOURCE_LOCAL_THRESHOLD:
                source_candidates.append((score, pdf))
        candidates_by_source[source.source_id] = len(source_candidates)
        for score, pdf in source_candidates:
            candidates.append((0, score, source.title.lower(), pdf.relpath, source, pdf))

    assigned: dict[str, tuple[LocalPdf, float]] = {}
    used_relpaths: set[str] = set()
    candidates = [
        (candidates_by_source[source.source_id], score, title, relpath, source, pdf)
        for _count, score, title, relpath, source, pdf in candidates
    ]
    for _count, score, _title, _relpath, source, pdf in sorted(candidates, key=lambda item: (item[0], -item[1], item[2], item[3])):
        if source.source_id in assigned or pdf.relpath in used_relpaths:
            continue
        assigned[source.source_id] = (pdf, score)
        used_relpaths.add(pdf.relpath)
    return assigned


def audit_bucket(audits: list[AuditRecord], title_hint: str) -> tuple[str, str, list[str], bool]:
    if not audits:
        return "review_needed", "No audit record yet.", [], False

    verdicts = dedupe_preserve_order(audit.verdict for audit in audits)
    reasons = dedupe_preserve_order(audit.reason for audit in audits)
    bins = dedupe_preserve_order(bin_name for audit in audits for bin_name in audit.response_bins)
    text = " ".join([title_hint, *verdicts, *reasons]).lower()

    include_primary = any(audit.verdict.startswith("[Include") and any(bin_name in PRIMARY_BINS for bin_name in audit.response_bins) for audit in audits)
    include_mechanism = any("Narrative/Mechanism Only" in audit.verdict for audit in audits)
    has_exclude = any(audit.verdict == "[Exclude]" for audit in audits)
    has_conflict = include_primary and has_exclude

    if include_primary:
        if has_conflict:
            bucket = "include_primary_conflicted"
        elif any(marker in text for marker in ("digitization", "supplementary", "provided text excerpt", "provided text excerpts")):
            bucket = "include_primary_needs_fulltext"
        else:
            bucket = "include_primary"
    elif include_mechanism:
        bucket = "include_mechanism_only"
    elif any(marker in text for marker in REVIEW_MARKERS):
        bucket = "exclude_review"
    elif any(marker in text for marker in SCOPE_EXCLUDE_MARKERS):
        bucket = "exclude_scope"
    elif any(marker in text for marker in SOFT_REVIEW_MARKERS):
        bucket = "review_fulltext_needed"
    else:
        bucket = "review_needed"

    note = " || ".join(f"{audit.verdict} {audit.reason}" for audit in audits)
    return bucket, note, bins, has_conflict


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: rebuild_screening_manifest.py <repo_root> <nlm_bin> <notebook_alias>",
            file=sys.stderr,
        )
        return 2

    repo_root = Path(sys.argv[1]).expanduser().resolve()
    nlm_bin = sys.argv[2]
    notebook_alias = sys.argv[3]

    audit_path = repo_root / "docs" / "audit" / "FULL_LIBRARY_AUDIT.md"
    if not audit_path.exists():
        audit_path = repo_root / "FULL_LIBRARY_AUDIT.md"
    records = parse_audit_records(audit_path)
    sources = load_notebook_sources(nlm_bin, notebook_alias)
    pdfs = load_local_pdfs(repo_root)
    source_pdf_assignments = assign_sources_to_local_pdfs(sources, pdfs)

    matched_locals: set[str] = set()
    entries: list[Entry] = []
    entry_by_source_id: dict[str, Entry] = {}
    entry_by_local_relpath: dict[str, Entry] = {}

    for source in sources:
        assignment = source_pdf_assignments.get(source.source_id)
        if assignment is None:
            pdf = None
            pdf_score = 0.0
        else:
            pdf, pdf_score = assignment
        entry = Entry(source=source, source_to_local_score=pdf_score, pdf=pdf, audits=[])
        entries.append(entry)
        entry_by_source_id[source.source_id] = entry
        if pdf is not None:
            matched_locals.add(pdf.relpath)
            entry_by_local_relpath[pdf.relpath] = entry

    for pdf in pdfs:
        if pdf.relpath in matched_locals:
            continue
        entry = Entry(source=None, source_to_local_score=0.0, pdf=pdf, audits=[])
        entries.append(entry)
        entry_by_local_relpath[pdf.relpath] = entry

    for record in records:
        local_direct, local_direct_score = best_match_record_to_local(record, pdfs)
        manual_pdf, manual_score = manual_local_match(record.audit_title, pdfs)
        if manual_score > local_direct_score:
            local_direct, local_direct_score = manual_pdf, manual_score
        source, source_score = best_match_to_sources(record, sources)

        entry: Entry | None = None
        if local_direct is not None and local_direct_score >= RECORD_LOCAL_THRESHOLD:
            entry = entry_by_local_relpath.get(local_direct.relpath)
        elif source is not None and source_score >= SOURCE_MATCH_THRESHOLD:
            entry = entry_by_source_id.get(source.source_id)

        if entry is None:
            pdf = local_direct if local_direct is not None and local_direct_score >= 0.70 else None
            entry = Entry(source=None, source_to_local_score=0.0, pdf=pdf, audits=[])
            entries.append(entry)
            if pdf is not None:
                entry_by_local_relpath[pdf.relpath] = entry
        entry.audits.append(record)

    consolidated: dict[str, Entry] = {}
    for entry in entries:
        if entry.source is not None:
            key = f"source:{entry.source.source_id}"
        elif entry.pdf is not None:
            key = f"local:{entry.pdf.relpath}"
        elif entry.audits:
            key = f"audit:{entry.audits[0].audit_title}"
        else:
            key = f"ghost:{id(entry)}"

        if key not in consolidated:
            consolidated[key] = entry
            continue

        current = consolidated[key]
        if current.source is None and entry.source is not None:
            current.source = entry.source
            current.source_to_local_score = entry.source_to_local_score
        if current.pdf is None and entry.pdf is not None:
            current.pdf = entry.pdf
        current.audits.extend(entry.audits)
    entries = list(consolidated.values())

    output_rows: list[dict[str, str]] = []
    for entry in sorted(
        entries,
        key=lambda item: (
            (item.source.title if item.source else item.pdf.filename if item.pdf else "").lower(),
            item.pdf.relpath if item.pdf else "",
        ),
    ):
        title_hint = entry.source.title if entry.source else entry.pdf.filename if entry.pdf else ""
        bucket, note, bins, conflict = audit_bucket(entry.audits, title_hint)
        output_rows.append(
            {
                "source_id": entry.source.source_id if entry.source else "",
                "source_title": entry.source.title if entry.source else "",
                "notebook_present": "1" if entry.source else "0",
                "local_relpath": entry.pdf.relpath if entry.pdf else "",
                "local_filename": entry.pdf.filename if entry.pdf else "",
                "current_folder": entry.pdf.folder if entry.pdf else "",
                "local_present": "1" if entry.pdf else "0",
                "source_to_local_score": f"{entry.source_to_local_score:.3f}" if entry.source and entry.pdf else "",
                "audit_count": str(len(entry.audits)),
                "audit_titles": " || ".join(dedupe_preserve_order(audit.audit_title for audit in entry.audits)),
                "audit_verdicts": " || ".join(dedupe_preserve_order(audit.verdict for audit in entry.audits)),
                "candidate_bins": "|".join(bins),
                "conflicting_audits": "1" if conflict else "0",
                "screening_bucket": bucket,
                "screening_notes": note,
            }
        )

    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=SCREENING_OUTPUT_FIELDS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(output_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
