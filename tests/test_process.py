"""Tests for the finance-powerbi data pipeline (data/process.py).

Runs the real pipeline against the real raw CSVs in data/raw/, then asserts the
star-schema invariants the DAX model depends on:

  1. the fact table is non-empty
  2. every scenario value is in the IBCS set {PY, AC, PL, FC}
  3. every fact foreign key resolves to a row in its dimension
  4. the fact amount total reconciles to a raw-CSV control total computed
     INDEPENDENTLY of process.py (re-parsing the raw files here)

Run from the project root:
    cd ~/Projects/Self/career-ops/notion/projects/finance-powerbi
    python3 -m pytest tests/ -v
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROC_DIR = DATA_DIR / "processed"

# Make data/process.py importable.
sys.path.insert(0, str(DATA_DIR))
import process  # noqa: E402

IBCS_SCENARIOS = {"PY", "AC", "PL", "FC"}

# The raw columns this pipeline loads (must mirror process.PLAN_MAP / BUDGET_MAP).
PLAN_LOADED_COLS = list(process.PLAN_MAP.keys())
BUDGET_LOADED_COLS = list(process.BUDGET_MAP.keys())


@pytest.fixture(scope="module", autouse=True)
def run_pipeline():
    """Build the star schema once for the whole module."""
    rc = process.main()
    assert rc == 0, "process.main() returned non-zero"
    yield


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_outputs_exist():
    for name in (
        "fact_capital_finance.csv",
        "dim_account.csv",
        "dim_period.csv",
        "dim_costcenter.csv",
        "dim_business_unit.csv",
        "dim_scenario.csv",
    ):
        assert (PROC_DIR / name).exists(), f"missing output {name}"


def test_fact_rows_positive():
    fact = _read_csv(PROC_DIR / "fact_capital_finance.csv")
    assert len(fact) > 0, "fact table is empty"


def test_every_scenario_is_ibcs():
    fact = _read_csv(PROC_DIR / "fact_capital_finance.csv")
    scenarios = {r["scenario"] for r in fact}
    assert scenarios, "no scenarios found"
    assert scenarios.issubset(IBCS_SCENARIOS), f"non-IBCS scenarios: {scenarios - IBCS_SCENARIOS}"


def test_all_four_scenarios_present():
    """Honest mapping should produce all four IBCS buckets from the real data."""
    fact = _read_csv(PROC_DIR / "fact_capital_finance.csv")
    scenarios = {r["scenario"] for r in fact}
    assert scenarios == IBCS_SCENARIOS, f"expected all of {IBCS_SCENARIOS}, got {scenarios}"


def test_foreign_keys_resolve():
    fact = _read_csv(PROC_DIR / "fact_capital_finance.csv")
    account_keys = {r["account_key"] for r in _read_csv(PROC_DIR / "dim_account.csv")}
    period_keys = {r["period_key"] for r in _read_csv(PROC_DIR / "dim_period.csv")}
    costcenter_keys = {r["costcenter_key"] for r in _read_csv(PROC_DIR / "dim_costcenter.csv")}
    bu_keys = {r["business_unit_key"] for r in _read_csv(PROC_DIR / "dim_business_unit.csv")}
    scenario_codes = {r["scenario_code"] for r in _read_csv(PROC_DIR / "dim_scenario.csv")}

    for r in fact:
        assert r["account_key"] in account_keys, f"account_key {r['account_key']} unresolved"
        assert r["period_key"] in period_keys, f"period_key {r['period_key']} unresolved"
        assert r["costcenter_key"] in costcenter_keys, f"costcenter_key {r['costcenter_key']} unresolved"
        assert r["business_unit_key"] in bu_keys, f"business_unit_key {r['business_unit_key']} unresolved"
        assert r["scenario"] in scenario_codes, f"scenario {r['scenario']} unresolved"


def test_costcenter_business_unit_consistent():
    """Each cost center's business_unit_key must resolve, tying the dims together."""
    bu_keys = {r["business_unit_key"] for r in _read_csv(PROC_DIR / "dim_business_unit.csv")}
    for cc in _read_csv(PROC_DIR / "dim_costcenter.csv"):
        assert cc["business_unit_key"] in bu_keys


def _independent_raw_total() -> float:
    """Re-parse the raw CSVs (NOT via process.py) and sum every loaded column."""
    total = 0.0

    def add(path: Path, cols: list[str]):
        nonlocal total
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                for c in cols:
                    v = (row[c] or "").strip().replace(",", "")
                    if v:
                        total += float(v)

    add(RAW_DIR / "vancouver-2023-2026-capital-plan.csv", PLAN_LOADED_COLS)
    add(RAW_DIR / "vancouver-2026-capital-project-budget.csv", BUDGET_LOADED_COLS)
    return total


def test_amount_reconciles_to_raw_control_total():
    fact = _read_csv(PROC_DIR / "fact_capital_finance.csv")
    fact_total = sum(float(r["amount"]) for r in fact)
    control = _independent_raw_total()
    assert control > 0, "control total is zero"
    assert fact_total == pytest.approx(control, rel=1e-9), (
        f"fact total {fact_total:,.2f} != raw control {control:,.2f}"
    )
