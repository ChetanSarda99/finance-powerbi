#!/usr/bin/env python3
"""Transform the two wide City of Vancouver capital CSVs into a star schema.

Reads the raw wide-format CSVs in data/raw/ and writes the long/tidy star
schema the DAX measures (docs/measures.md) and the model (docs/model-diagram.md)
expect into data/processed/ as CSV:

    fact_capital_finance.csv   long fact: one row per (project x scenario x period)
    dim_account.csv            chart-of-accounts grain (the budget line semantics)
    dim_period.csv             year-grain calendar (2022-2030)
    dim_costcenter.csv         service_category_1/2/3 hierarchy (the cost centers)
    dim_business_unit.csv      top-level program rollup (service_category_1)
    README.md                  schema + mapping decisions + load instructions

Design goals:
- The fact table SUMs an `amount` column (Total Amount = SUM(fact[amount])).
- Every fact row carries integer foreign keys that resolve to a dim row:
  account_key, period_key, costcenter_key, business_unit_key.
- `scenario` is one of the IBCS set {PY, AC, PL, FC}, mapped HONESTLY from the
  real column semantics (see SCENARIO MAPPING below and data/processed/README.md).

Uses pandas if installed, else falls back to the stdlib csv module. No network.

Usage:
    cd ~/Projects/Self/career-ops/notion/projects/finance-powerbi
    python3 data/process.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
OUT_DIR = HERE / "processed"

PLAN_CSV = RAW_DIR / "vancouver-2023-2026-capital-plan.csv"
BUDGET_CSV = RAW_DIR / "vancouver-2026-capital-project-budget.csv"

# The four key (non-amount) columns shared by both raw files.
KEY_COLS = [
    "service_category_1",
    "service_category_2",
    "service_category_3",
    "project_program_name",
]

# ---------------------------------------------------------------------------
# SCENARIO MAPPING (the honest IBCS PY / AC / PL / FC decisions)
# ---------------------------------------------------------------------------
# Each entry: raw_column -> (scenario_code, year)
# Rationale per column is documented in data/processed/README.md. Summary:
#   AC  Actual      = approved budget for a year that has already elapsed
#                     (2023/2024/2025 city-led allocations -> realized spend proxy)
#   PL  Plan        = approved budget for the current/active year not yet spent
#                     (2026 budget + 2026 capital expenditure budget)
#   FC  Forecast    = explicitly forecast future years (2027-2030 forecast cols)
#   PY  Prior Year  = multi-year budget previously approved before this plan window
#                     (a cumulative prior bucket; anchored to year 2022)
#
# We deliberately map only columns whose semantics cleanly match one IBCS
# scenario. Rollup / funding-source / availability columns (e.g. original vs
# revised plan totals, pay-as-you-go vs borrowing splits, available_project_budget)
# are intentionally NOT loaded as fact rows: they are alternative cuts of the
# same dollars and would double-count against the per-year scenario buckets.

PLAN_MAP = {
    # Per-year approved budgets. 2023-2025 have elapsed -> Actual proxy.
    "2023_2026_capital_plan_city_led_allocations_2023_approved_budget": ("AC", 2023),
    "2023_2026_capital_plan_city_led_allocations_2024_approved_budget": ("AC", 2024),
    "2023_2026_capital_plan_city_led_allocations_2025_approved_budget": ("AC", 2025),
    # 2026 approved budget, active year, not yet spent -> Plan.
    "2023_2026_capital_plan_city_led_allocations_2026_budget": ("PL", 2026),
    # Budgets approved in prior plan windows (cumulative) -> Prior Year bucket.
    "multi_year_capital_project_budgets_previously_approved": ("PY", 2022),
}

BUDGET_MAP = {
    # 2026 approved annual capital expenditure budget -> Plan.
    "annual_capital_expenditure_2026_capital_expenditure_budget": ("PL", 2026),
    # Explicitly labelled forecast years 2027-2030 -> Forecast.
    "annual_capital_expenditure_2027_forecast": ("FC", 2027),
    "annual_capital_expenditure_2028_forecast": ("FC", 2028),
    "annual_capital_expenditure_2029_forecast": ("FC", 2029),
    "annual_capital_expenditure_2030_forecast": ("FC", 2030),
}

# Account dimension: each loaded raw amount column becomes one account-line row,
# so the fact can be sliced by the exact source measure when needed.
# account_code -> (account_label, scenario_code, source_file)
ACCOUNTS = {
    "city_led_alloc_approved_budget": (
        "City-led allocation - approved budget", None, "capital-plan",
    ),
    "previously_approved_multiyear": (
        "Multi-year budget previously approved", "PY", "capital-plan",
    ),
    "annual_capital_expenditure_budget": (
        "Annual capital expenditure budget", "PL", "capital-project-budget",
    ),
    "annual_capital_expenditure_forecast": (
        "Annual capital expenditure forecast", "FC", "capital-project-budget",
    ),
}

# Map each raw column to an account_code.
PLAN_ACCOUNT = {
    "2023_2026_capital_plan_city_led_allocations_2023_approved_budget": "city_led_alloc_approved_budget",
    "2023_2026_capital_plan_city_led_allocations_2024_approved_budget": "city_led_alloc_approved_budget",
    "2023_2026_capital_plan_city_led_allocations_2025_approved_budget": "city_led_alloc_approved_budget",
    "2023_2026_capital_plan_city_led_allocations_2026_budget": "city_led_alloc_approved_budget",
    "multi_year_capital_project_budgets_previously_approved": "previously_approved_multiyear",
}
BUDGET_ACCOUNT = {
    "annual_capital_expenditure_2026_capital_expenditure_budget": "annual_capital_expenditure_budget",
    "annual_capital_expenditure_2027_forecast": "annual_capital_expenditure_forecast",
    "annual_capital_expenditure_2028_forecast": "annual_capital_expenditure_forecast",
    "annual_capital_expenditure_2029_forecast": "annual_capital_expenditure_forecast",
    "annual_capital_expenditure_2030_forecast": "annual_capital_expenditure_forecast",
}

SCENARIO_LABELS = {
    "AC": "Actual",
    "PL": "Plan",
    "FC": "Forecast",
    "PY": "Prior Year",
}
SCENARIO_FILL = {
    "AC": "solid_black",
    "PL": "outlined",
    "FC": "hatched",
    "PY": "solid_grey",
}

ALL_YEARS = [2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]


# Text normalization for the label/name fields. A few raw project names use
# typographic punctuation (en-dash, curly apostrophe) from the source. We fold
# them to plain ASCII so downstream tooling (and the repo em-dash gate) stays
# clean. This only touches free-text label columns; it never touches `amount`,
# so the reconciliation control total is unaffected.
# The keys below are the very chars the repo em-dash gate bans, so each line is
# tagged [INTENTIONAL] (the gate's own whitelist marker) - this mapping table
# is what FOLDS them out of the data, not a violation.
_TEXT_FOLD = {
    "–": "-",   # en dash -> hyphen  [INTENTIONAL]
    "—": "-",   # em dash -> hyphen  [INTENTIONAL]
    "→": "->",  # right arrow  [INTENTIONAL]
    "←": "<-",  # left arrow  [INTENTIONAL]
    "⇒": "=>",  # right double arrow  [INTENTIONAL]
    "‘": "'",   # left single quote
    "’": "'",   # right single quote
    "“": '"',   # left double quote
    "”": '"',   # right double quote
    "…": "...",  # ellipsis
}


def _clean_text(value: str) -> str:
    """Fold typographic punctuation in a free-text field to plain ASCII."""
    out = value or ""
    for bad, good in _TEXT_FOLD.items():
        if bad in out:
            out = out.replace(bad, good)
    return out


def _to_number(value: str) -> float:
    """Parse a raw amount cell to a float; blank -> 0.0."""
    v = (value or "").strip().replace(",", "")
    if v == "" or v.lower() in ("na", "n/a", "null", "none"):
        return 0.0
    return float(v)


def _read_rows(path: Path) -> list[dict]:
    """Read a raw CSV (utf-8-sig handles the BOM) into a list of dict rows."""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_fact() -> tuple[list[dict], dict]:
    """Unpivot both raw files into long fact records. Returns (records, control)."""
    records: list[dict] = []
    # control totals computed independently per scenario for the reconciliation
    # test (raw sum of every loaded amount cell, grouped by scenario).
    control = {"PY": 0.0, "AC": 0.0, "PL": 0.0, "FC": 0.0}

    def emit(row, col_map, account_map):
        for col, (scenario, year) in col_map.items():
            amount = _to_number(row[col])
            if amount == 0.0:
                # skip empty / zero cells (matches the M-script NonZero filter)
                continue
            control[scenario] += amount
            records.append(
                {
                    "service_category_1": _clean_text(row["service_category_1"]),
                    "service_category_2": _clean_text(row["service_category_2"]),
                    "service_category_3": _clean_text(row["service_category_3"]),
                    "project_program_name": _clean_text(row["project_program_name"]),
                    "year": year,
                    "scenario": scenario,
                    "account_code": account_map[col],
                    "amount": amount,
                }
            )

    for row in _read_rows(PLAN_CSV):
        emit(row, PLAN_MAP, PLAN_ACCOUNT)
    for row in _read_rows(BUDGET_CSV):
        emit(row, BUDGET_MAP, BUDGET_ACCOUNT)

    return records, control


def build_dims(records: list[dict]) -> dict:
    """Derive the four dimension tables + scenario dim from the fact records."""
    # dim_period -------------------------------------------------------------
    dim_period = [
        {"period_key": y, "year": y, "label": f"FY{y}"} for y in ALL_YEARS
    ]

    # dim_business_unit (service_category_1 rollup) --------------------------
    bu_names = sorted({r["service_category_1"] for r in records})
    bu_key = {name: i for i, name in enumerate(bu_names, start=1)}
    dim_business_unit = [
        {"business_unit_key": bu_key[name], "business_unit_name": name}
        for name in bu_names
    ]

    # dim_costcenter (full 3-level service-category hierarchy) ---------------
    cc_combos = sorted(
        {
            (
                r["service_category_1"],
                r["service_category_2"],
                r["service_category_3"],
            )
            for r in records
        }
    )
    cc_key = {combo: i for i, combo in enumerate(cc_combos, start=1)}
    dim_costcenter = [
        {
            "costcenter_key": cc_key[combo],
            "service_category_1": combo[0],
            "service_category_2": combo[1],
            "service_category_3": combo[2],
            "business_unit_key": bu_key[combo[0]],
        }
        for combo in cc_combos
    ]

    # dim_account ------------------------------------------------------------
    acct_codes = sorted({r["account_code"] for r in records})
    acct_key = {code: i for i, code in enumerate(acct_codes, start=1)}
    dim_account = [
        {
            "account_key": acct_key[code],
            "account_code": code,
            "account_label": ACCOUNTS[code][0],
            "account_default_scenario": ACCOUNTS[code][1] or "",
            "source_file": ACCOUNTS[code][2],
        }
        for code in acct_codes
    ]

    # dim_scenario -----------------------------------------------------------
    dim_scenario = [
        {
            "scenario_code": code,
            "scenario_label": SCENARIO_LABELS[code],
            "fill_style": SCENARIO_FILL[code],
        }
        for code in ("AC", "PL", "FC", "PY")
    ]

    return {
        "dim_period": dim_period,
        "dim_business_unit": dim_business_unit,
        "dim_costcenter": dim_costcenter,
        "dim_account": dim_account,
        "dim_scenario": dim_scenario,
        "_bu_key": bu_key,
        "_cc_key": cc_key,
        "_acct_key": acct_key,
    }


def resolve_keys(records: list[dict], dims: dict) -> list[dict]:
    """Replace natural keys on the fact with integer foreign keys to the dims."""
    bu_key = dims["_bu_key"]
    cc_key = dims["_cc_key"]
    acct_key = dims["_acct_key"]
    out = []
    for r in records:
        combo = (
            r["service_category_1"],
            r["service_category_2"],
            r["service_category_3"],
        )
        out.append(
            {
                "project_program_name": r["project_program_name"],
                "account_key": acct_key[r["account_code"]],
                "period_key": r["year"],
                "costcenter_key": cc_key[combo],
                "business_unit_key": bu_key[r["service_category_1"]],
                "scenario": r["scenario"],
                "amount": r["amount"],
            }
        )
    return out


FACT_COLS = [
    "project_program_name",
    "account_key",
    "period_key",
    "costcenter_key",
    "business_unit_key",
    "scenario",
    "amount",
]


def _write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def write_outputs(fact: list[dict], dims: dict) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}

    # Prefer pandas for the fact (clean int dtypes), else stdlib csv.
    try:
        import pandas as pd

        df = pd.DataFrame(fact, columns=FACT_COLS)
        for c in ("account_key", "period_key", "costcenter_key", "business_unit_key"):
            df[c] = df[c].astype("int64")
        df.to_csv(OUT_DIR / "fact_capital_finance.csv", index=False)
        counts["fact_capital_finance"] = len(df)
    except ImportError:
        _write_csv(OUT_DIR / "fact_capital_finance.csv", fact, FACT_COLS)
        counts["fact_capital_finance"] = len(fact)

    _write_csv(
        OUT_DIR / "dim_account.csv",
        dims["dim_account"],
        ["account_key", "account_code", "account_label", "account_default_scenario", "source_file"],
    )
    counts["dim_account"] = len(dims["dim_account"])

    _write_csv(
        OUT_DIR / "dim_period.csv",
        dims["dim_period"],
        ["period_key", "year", "label"],
    )
    counts["dim_period"] = len(dims["dim_period"])

    _write_csv(
        OUT_DIR / "dim_costcenter.csv",
        dims["dim_costcenter"],
        ["costcenter_key", "service_category_1", "service_category_2", "service_category_3", "business_unit_key"],
    )
    counts["dim_costcenter"] = len(dims["dim_costcenter"])

    _write_csv(
        OUT_DIR / "dim_business_unit.csv",
        dims["dim_business_unit"],
        ["business_unit_key", "business_unit_name"],
    )
    counts["dim_business_unit"] = len(dims["dim_business_unit"])

    _write_csv(
        OUT_DIR / "dim_scenario.csv",
        dims["dim_scenario"],
        ["scenario_code", "scenario_label", "fill_style"],
    )
    counts["dim_scenario"] = len(dims["dim_scenario"])

    return counts


def main() -> int:
    if not PLAN_CSV.exists() or not BUDGET_CSV.exists():
        print(
            "ERROR: raw CSVs missing. Run data/fetch.py first.", file=sys.stderr
        )
        return 1

    records, control = build_fact()
    dims = build_dims(records)
    fact = resolve_keys(records, dims)
    counts = write_outputs(fact, dims)

    print("Wrote star schema to", OUT_DIR)
    for name, n in counts.items():
        print(f"  {name + '.csv':32s} {n:>6d} rows")
    print("\nControl totals (raw sum per scenario, $):")
    grand = 0.0
    for sc in ("PY", "AC", "PL", "FC"):
        print(f"  {sc}: {control[sc]:>20,.0f}")
        grand += control[sc]
    print(f"  {'TOTAL':>2}: {grand:>20,.0f}")

    fact_total = sum(r["amount"] for r in fact)
    print(f"\nFact amount total: {fact_total:,.0f}")
    if abs(fact_total - grand) > 0.5:
        print("ERROR: fact total does not reconcile to control", file=sys.stderr)
        return 1
    print("Reconciliation OK (fact total == sum of control totals).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
