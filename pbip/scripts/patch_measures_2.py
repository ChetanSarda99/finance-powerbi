#!/usr/bin/env python3
"""Model patch 2, 2026-11-12: one-year-on-one-year forecast view for page 3.
Usage: python3 patch_measures_2.py <fact_capital_finance.tmdl>   (idempotent; keeps CRLF if present)
Adds Forecast FY2027, Expenditure Change (FY27 vs FY26), Expenditure Change % (FY27 vs FY26).
"""
import sys
from pathlib import Path
p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8"); crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "measure 'Forecast FY2027'" in t:
    print("already patched", p); sys.exit(0)
FMT = '\t\tformatString: "$#,0;-$#,0;$0"\n\n'
PCT = '\t\tformatString: "0.0%;-0.0%;0.0%"\n\n'
add = (
    "\t/// Forecast for FY2027 only: the city's published FY2027 expected spending. Compared with the FY2026\n"
    "\t/// expenditure budget, one year on one year.\n"
    "\tmeasure 'Forecast FY2027' =\n\t\t\tCALCULATE ( [Forecast], dim_period[period_key] = 2027 )\n" + FMT +
    "\t/// FY2027 forecast minus FY2026 expenditure budget (both expected spending on approved projects).\n"
    "\tmeasure 'Expenditure Change (FY27 vs FY26)' = [Forecast FY2027] - [Expenditure Budget]\n" + FMT +
    "\t/// Same change as a percent of the FY2026 expenditure budget.\n"
    "\tmeasure 'Expenditure Change % (FY27 vs FY26)' = DIVIDE ( [Forecast FY2027] - [Expenditure Budget], [Expenditure Budget] )\n" + PCT
)
anchor = "\t/// Year label for axis"
assert t.count(anchor) == 1
t = t.replace(anchor, add + anchor)
p.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
print("patched", p)
