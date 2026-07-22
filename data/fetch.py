#!/usr/bin/env python3
"""Re-pull the 2 primary CSVs from the City of Vancouver Open Data API.

Idempotent + safe to re-run. Writes to data/raw/ only.

Source URLs use the Vancouver Open Data API REST endpoint pattern:
  https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/<id>/exports/csv

Both datasets are under the Open Government Licence - Vancouver (free reuse +
attribution). See ../data-sources.md for the canonical source-of-truth doc
+ attribution block to paste on the landing page.

Usage:
    cd ~/Projects/Self/career-ops/notion/projects/finance-powerbi
    python3 data/fetch.py
"""
from __future__ import annotations
import sys
import urllib.request
from pathlib import Path

DATASETS = {
    "vancouver-2026-capital-project-budget.csv":
        "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/"
        "2026-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/exports/csv?delimiter=%2C",
    "vancouver-2023-2026-capital-plan.csv":
        "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/"
        "2023-2026-capital-plan-and-2026-capital-budget-with-proposed-four-year-capital-plan-allocations/exports/csv?delimiter=%2C",
}

UA = "career-ops/finance-powerbi (Chetan Sarda; finance portfolio project)"
TIMEOUT = 30


def fetch_one(name: str, url: str, out_dir: Path) -> int:
    out = out_dir / name
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read()
    except Exception as e:
        print(f"  FAIL {name}: {e}", file=sys.stderr)
        return 0
    out.write_bytes(data)
    # Count rows (cheap, single pass)
    n_rows = data.count(b"\n")
    print(f"  OK   {name}: {len(data):,}b, ~{n_rows-1} rows")
    return n_rows


def main() -> int:
    raw_dir = Path(__file__).resolve().parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, url in DATASETS.items():
        total += fetch_one(name, url, raw_dir)
    if not total:
        print("ERROR: all fetches failed", file=sys.stderr)
        return 1
    print(f"\n  refreshed {len(DATASETS)} dataset(s) into {raw_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
