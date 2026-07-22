# Data folder

Real public-data CSVs powering the Finance Power BI portfolio dashboard. NOT synthetic. Per [`../data-sources.md`](../data-sources.md) — decision locked 2026-05-29.

Last refreshed: 2026-05-29.

---

## Folder layout

```
data/
├── raw/                  # Untouched CSVs as downloaded from City of Vancouver Open Data API
│   ├── vancouver-2026-capital-project-budget.csv     (630 rows × 20 cols)
│   └── vancouver-2023-2026-capital-plan.csv          (395 rows × 18 cols)
├── processed/            # Power-Query-cleaned parquet ready for Power BI load
│   └── (populated by Power BI on first refresh)
├── fetch.py              # Re-pull both CSVs from the Vancouver Open Data API
└── README.md             # This file
```

## Re-pull (whenever the source refreshes)

```bash
cd ~/Projects/Self/career-ops/notion/projects/finance-powerbi
python3 data/fetch.py
```

The fetch script is idempotent and writes to `data/raw/` only. It does NOT touch processed/.

## Source URLs (Vancouver Open Data API REST)

| Dataset | URL |
|---|---|
| 2026 Multi-Year Capital Project Budget | `https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/2026-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/exports/csv` |
| 2023-2026 Capital Plan | `https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/2023-2026-capital-plan-and-2026-capital-budget-with-proposed-four-year-capital-plan-allocations/exports/csv` |

Both endpoints work unauthenticated. No rate limit hit during testing (single fetch each completes in <2s).

## Licence

Open Government Licence - Vancouver (free reuse, attribution required). See [`../data-sources.md`](../data-sources.md) for the attribution block to paste on the landing page + Notion mirror.

## Star schema (target model in Power BI)

```
        ┌──────────────┐
        │  dim_period  │  (year, year_label e.g. "2024 AC", "2026 PL")
        └──────┬───────┘
               │
               ▼
┌──────────────────────────────────┐
│      fact_capital_finance        │
│ project_program_name             │
│ service_category_1 (FK)          │
│ amount                           │
│ scenario (AC / PL / FC)          │
│ year_id (FK -> dim_period)       │
└──┬──────────────┬────────────────┘
   │              │
   ▼              ▼
┌──────────────┐ ┌──────────────┐
│ dim_service  │ │ dim_scenario │
│ _category    │ │              │
└──────────────┘ └──────────────┘
```

`fact_capital_finance` is the UNPIVOTED view of the source CSVs. Source CSVs are wide (one column per year × scenario); Power Query M unpivots into long form so DAX time-intelligence + variance calcs work cleanly.

See [`../docs/measures.md`](../docs/measures.md) for the DAX measures.

## Refresh schedule

- Annual hard refresh: re-run `data/fetch.py` after City of Vancouver releases the new year's capital plan (typically Q1)
- Quarterly soft refresh: re-pull in case of mid-cycle budget addenda
- Power BI Service incremental refresh policy: last 12 months hot, older archived (per `notes.md` Week 3 task 7)

## What this folder is NOT

- Not a substitute for the BC public-sector full financials (use BC Public Accounts if you need that scope)
- Not transit operations data (TransLink Open Data covers that - kept as a secondary overlay layer per `data-sources.md`)
- Not labour-cost analytics (BC Public Salary Disclosure covers that - secondary layer)
