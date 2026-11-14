#!/usr/bin/env python3
"""One-off model patch, 2026-11-12: make Plan like-for-like with Actual.

Usage: python3 patch_measures.py <fact_capital_finance.tmdl>
Works on the repo copy (LF) and the Desktop-saved copy (CRLF, lineageTags).
- Plan now = scenario PL on the capital-plan account only (was PL across two accounts).
- Adds Actual or Plan, Variance Abs (vs PY), Variance Pct (vs PY), Expenditure Budget.
- Removes the five AC vs PL / AC vs PY variance measures they replace.
"""
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")

def drop(name):
    global t
    pat = re.compile(r"(?:\t///[^\n]*\n)*\tmeasure '" + re.escape(name) + r"' =.*?\n\n", re.S)
    t, n = pat.subn("", t, count=1)
    assert n == 1, name

for m in ("Variance Abs (AC vs PL)", "Variance Pct (AC vs PL)", "Variance Abs (AC vs PY)",
          "Variance Pct (AC vs PY)", "Variance Color (Cost AC vs PL)"):
    drop(m)

old = re.compile(r"\t/// Budget / Plan - filtered to scenario=PL\n\tmeasure Plan = CALCULATE \( \[Total Amount\], dim_scenario\[scenario_code\] = \"PL\" \)\n")
new_plan = (
    "\t/// Plan = the FY2026 capital-plan allocation (scenario PL, account city_led_alloc_approved_budget).\n"
    "\t/// Same account as Actual, so Plan and Actual compare like-for-like. The separate FY2026 annual\n"
    "\t/// expenditure budget is its own measure and is never added in.\n"
    "\tmeasure Plan =\n"
    "\t\t\tCALCULATE (\n"
    "\t\t\t    [Total Amount],\n"
    "\t\t\t    dim_scenario[scenario_code] = \"PL\",\n"
    "\t\t\t    dim_account[account_code] = \"city_led_alloc_approved_budget\"\n"
    "\t\t\t)\n"
)
t, n = old.subn(lambda _: new_plan, t, count=1)
assert n == 1, "Plan"

FMT = '\t\tformatString: "$#,0;-$#,0;$0"\n\n'
PCT = '\t\tformatString: "0.0%;-0.0%;0.0%"\n\n'
added = (
    "\t/// The capital-plan allocation for the year: Actual for elapsed years (FY2023-25), Plan for FY2026.\n"
    "\t/// One account in every year, so any two years compare like-for-like.\n"
    "\tmeasure 'Actual or Plan' = [Actual] + [Plan]\n" + FMT +
    "\t/// Actual or Plan minus Prior Year. Blank when the year before has no approved budget at all.\n"
    "\tmeasure 'Variance Abs (vs PY)' =\n"
    "\t\t\tVAR c = [Actual or Plan]\n"
    "\t\t\tVAR p = [Prior Year]\n"
    "\t\t\tVAR pyExists = NOT ISBLANK ( CALCULATE ( [Prior Year], ALL ( dim_business_unit ), ALL ( dim_costcenter ) ) )\n"
    "\t\t\tRETURN\n"
    "\t\t\t    IF ( pyExists && NOT ( ISBLANK ( c ) && ISBLANK ( p ) ), c - p )\n" + FMT +
    "\t/// Same change as a percent of Prior Year.\n"
    "\tmeasure 'Variance Pct (vs PY)' = DIVIDE ( [Actual or Plan] - [Prior Year], [Prior Year] )\n" + PCT +
    "\t/// FY2026 annual capital expenditure budget (capital project budget dataset). A different budget line\n"
    "\t/// from the capital-plan allocation; shown on its own page with the FY2027-30 forecast.\n"
    "\tmeasure 'Expenditure Budget' =\n"
    "\t\t\tCALCULATE ( [Total Amount], dim_account[account_code] = \"annual_capital_expenditure_budget\" )\n" + FMT
)
anchor = "\t/// Year label for axis"
assert t.count(anchor) == 1
t = t.replace(anchor, added + anchor)
if crlf:
    t = t.replace("\n", "\r\n")
p.write_bytes(t.encode("utf-8"))
print("patched", p, "measures:", len(re.findall(r"^\tmeasure ", t, re.M)))
