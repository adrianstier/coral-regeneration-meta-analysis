"""
One-shot Zotero hygiene fixes for the coral regeneration library.

Applies the spec from coral-regeneration-zotero-fixes.md against library 3655735
via the Zotero Web API. Designed to be idempotent — re-runs only touch items
whose current contents still differ from the target.

Run from the project root:

    python3 tools/zotero_hygiene_2026_05_21.py [--apply]

Without --apply this is a dry-run that prints the diff per item.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib import error, request

LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "3655735")
API_KEY = os.environ.get("ZOTERO_API_KEY")
API_ROOT = f"https://api.zotero.org/users/{LIBRARY_ID}"
HEADERS = {
    "Zotero-API-Key": API_KEY or "",
    "Zotero-API-Version": "3",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------

DUPLICATES_TO_DELETE = [
    ("5VNAL3WX", "Buck-Wiese 2018 — duplicate with abbreviated authors"),
    ("HV29456C", "Rodríguez-Villalobos 2016 — duplicate"),
    ("7RQFHV2A", "Traylor-Knowles 2016 — duplicate"),
]

# Each entry: item_key -> list of (current_last, current_first, new_last, new_first)
AUTHOR_FIXES: dict[str, list[tuple[str, str, str, str]]] = {
    "8NUEJQAV": [  # Raymundo et al. 2016
        ("Raymundo", "Lj", "Raymundo", "L. J."),
        ("Work", "Tm", "Work", "T. M."),
        ("Miller", "Rl", "Miller", "R. L."),
        ("Lozada-Misa", "Pl", "Lozada-Misa", "P. L."),
    ],
    "HII9WLN2": [  # Rodríguez-Villalobos et al. 2015
        ("Rodríguez-Villalobos", "Jc", "Rodríguez-Villalobos", "J. C."),
        ("Work", "Tm", "Work", "T. M."),
        ("Calderon-Aguilera", "Le", "Calderon-Aguilera", "L. E."),
    ],
    "H7YKN5WV": [  # Bak & Steward-Van 1980
        # Only obvious half-name → expand to "Steward-Van Es, Yvonne".
        ("Steward-Van", "Yvonne", "Steward-Van Es", "Yvonne"),
    ],
    "C7HNZZVZ": [  # Renegar et al. 2008
        ("Renegar", "D A", "Renegar", "D. A."),
        ("Blackwelder", "P L", "Blackwelder", "P. L."),
        ("Moulding", "A L", "Moulding", "A. L."),
    ],
}

TITLE_REWRITES: dict[str, tuple[str, str]] = {
    # current_title -> new_title; if current_title is empty we accept whatever is there.
    "JMCSF9C7": (
        "",
        "Partial mortality in <i>Porites</i> corals: variation among Philippine reefs",
    ),
    "C7HNZZVZ": (
        "",
        "Coral ultrastructural response to elevated pCO2 and nutrients during tissue repair and regeneration",
    ),
    "GW57HA2H": (
        "",
        "Coral tissue growth and regeneration conjoin the advent of adult stem cell-like cells",
    ),
    "RR3M9N59": (
        "",
        "Assembly dynamics for a coral-associated reef community: spatial and temporal patterns, and a test of priority effects",
    ),
    "SN2LRCVR": (
        "",
        "Ecology of fishes and invertebrates inhabiting the coral <i>Pocillopora grandis</i> in Hawaiʻi",
    ),
    "F54AJIS5": (
        "",  # full title is long; we just normalize PCO2 → pCO2
        None,  # sentinel: see edmunds_burgess_fix
    ),
}

# DOI add
DOI_ADDS: dict[str, str] = {
    "6MC64X8A": "10.7717/peerj.2544",  # Tsounis & Edmunds 2016
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def http(method: str, path: str, body: Any = None, extra_headers: dict | None = None) -> tuple[int, dict, dict]:
    url = path if path.startswith("http") else f"{API_ROOT}{path}"
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, dict(resp.headers), json.loads(payload) if payload else {}
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers or {}), {"_error": body_text}


def get_item(key: str) -> tuple[dict, int]:
    status, _, payload = http("GET", f"/items/{key}")
    if status != 200:
        raise RuntimeError(f"GET /items/{key} -> {status}: {payload}")
    return payload["data"], payload["version"]


def patch_item(key: str, version: int, patch: dict) -> None:
    status, _, payload = http(
        "PATCH",
        f"/items/{key}",
        body=patch,
        extra_headers={"If-Unmodified-Since-Version": str(version)},
    )
    if status not in (204, 200):
        raise RuntimeError(f"PATCH /items/{key} -> {status}: {payload}")


def delete_item(key: str, version: int) -> None:
    status, _, payload = http(
        "DELETE",
        f"/items/{key}",
        extra_headers={"If-Unmodified-Since-Version": str(version)},
    )
    if status not in (204, 200):
        raise RuntimeError(f"DELETE /items/{key} -> {status}: {payload}")


# ---------------------------------------------------------------------------
# Fix functions
# ---------------------------------------------------------------------------


def fix_authors(item: dict, edits: list[tuple[str, str, str, str]]) -> dict | None:
    creators = list(item.get("creators", []))
    changed = False
    for ed in edits:
        last_cur, first_cur, last_new, first_new = ed
        for c in creators:
            if c.get("lastName") == last_cur and c.get("firstName") == first_cur:
                c["lastName"] = last_new
                c["firstName"] = first_new
                changed = True
                break
        else:
            # try lastName-only match (case where current first is something else)
            for c in creators:
                if c.get("lastName") == last_cur and c.get("firstName") not in (first_new,):
                    if c.get("firstName") and c["firstName"].replace(" ", "").replace(".", "") == first_cur.replace(" ", "").replace(".", ""):
                        c["lastName"] = last_new
                        c["firstName"] = first_new
                        changed = True
                        break
    return {"creators": creators} if changed else None


def fix_title(item: dict, key: str) -> dict | None:
    if key not in TITLE_REWRITES:
        return None
    _, target = TITLE_REWRITES[key]
    if target is None:
        return None
    if item.get("title", "").strip() == target.strip():
        return None
    return {"title": target}


def fix_edmunds_burgess(item: dict) -> dict | None:
    t = item.get("title", "")
    if "PCO2" not in t:
        return None
    return {"title": t.replace("PCO2", "pCO2")}


def fix_doi(item: dict, key: str) -> dict | None:
    if key not in DOI_ADDS:
        return None
    target = DOI_ADDS[key]
    if item.get("DOI") == target:
        return None
    return {"DOI": target}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write to Zotero")
    args = ap.parse_args()

    if not API_KEY:
        print("ZOTERO_API_KEY not in environment.", file=sys.stderr)
        return 1

    summary = {
        "deleted": [],
        "patched": [],
        "skipped": [],
        "errors": [],
    }

    # 1. Deletes
    for key, reason in DUPLICATES_TO_DELETE:
        try:
            data, version = get_item(key)
        except RuntimeError as e:
            if "404" in str(e):
                summary["skipped"].append({"key": key, "reason": "already deleted"})
                continue
            raise
        print(f"DELETE {key}: {reason} (currently '{data.get('title', '')[:70]}')")
        if args.apply:
            delete_item(key, version)
            summary["deleted"].append(key)
            time.sleep(0.2)

    # 2. Author fixes
    for key, edits in AUTHOR_FIXES.items():
        try:
            data, version = get_item(key)
        except RuntimeError as e:
            summary["errors"].append({"key": key, "error": str(e)})
            continue
        patch = fix_authors(data, edits)
        if not patch:
            summary["skipped"].append({"key": key, "reason": "authors already fixed"})
            continue
        print(f"PATCH authors {key}: {[(c['lastName'], c.get('firstName')) for c in patch['creators']]}")
        if args.apply:
            patch_item(key, version, patch)
            summary["patched"].append({"key": key, "field": "creators"})
            time.sleep(0.2)

    # 3. Title rewrites
    for key in TITLE_REWRITES:
        try:
            data, version = get_item(key)
        except RuntimeError as e:
            summary["errors"].append({"key": key, "error": str(e)})
            continue
        patch = {}
        if key == "F54AJIS5":
            t = fix_edmunds_burgess(data)
            if t:
                patch.update(t)
        else:
            t = fix_title(data, key)
            if t:
                patch.update(t)
        if not patch:
            summary["skipped"].append({"key": key, "reason": "title already correct"})
            continue
        print(f"PATCH title {key}: {patch['title'][:100]}")
        if args.apply:
            patch_item(key, version, patch)
            summary["patched"].append({"key": key, "field": "title"})
            time.sleep(0.2)

    # 4. DOI additions
    for key in DOI_ADDS:
        try:
            data, version = get_item(key)
        except RuntimeError as e:
            summary["errors"].append({"key": key, "error": str(e)})
            continue
        patch = fix_doi(data, key)
        if not patch:
            summary["skipped"].append({"key": key, "reason": "DOI already present"})
            continue
        print(f"PATCH DOI {key}: {patch['DOI']}")
        if args.apply:
            patch_item(key, version, patch)
            summary["patched"].append({"key": key, "field": "DOI"})
            time.sleep(0.2)

    print()
    print("Summary:")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
