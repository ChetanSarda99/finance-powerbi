# Data Sources - Finance Power BI Portfolio

All datasets are real public data, not synthetic. Decision locked 2026-05-29 - cheaper to ship, more credible to BC public-sector hiring managers, removes the "is this realistic" question. The picks below were re-evaluated 2026-05-29 to ensure they support the IBCS / Zebra-BI variance + budget + actual + prior year patterns the dashboard demonstrates.

Last refreshed 2026-05-29.

---

## Primary source - City of Vancouver Open Data (BUDGET vs ACTUAL)

This is THE source. It's the only public source that gives us budget + actual + multi-year + multi-department in one CSV.

**Portal:** https://opendata.vancouver.ca/explore/
**API root:** https://opendata.vancouver.ca/api/datasets/1.0/
**Licence:** Open Government Licence - Vancouver (free reuse with attribution)
**Format:** CSV / JSON / GeoJSON via API; Excel via downloads page
**Refresh cadence:** Annual (Capital Plan refreshed each year; Capital Project Budget refreshed annually + quarterly addenda)

### The 2 datasets we use

| Dataset ID | What it gives | Records | Why it matters for IBCS |
|---|---|---|---|
| `2026-multi-year-capital-project-budget-requests-and-capital-expenditure-budget` | Per-project budget request + capital expenditure budget, by department / service area / year | 630 | Variance (budget vs actual via cross-year join) + small multiples by department + budget bars per project |
| `2023-2026-capital-plan-and-2026-capital-budget-with-proposed-four-year-capital-plan-allocations` | 4-year capital plan + the current-year capital budget by service category | 395 | Time series across 4 years (PY · AC · PL · FC pattern) + hierarchical structure (category -> project) |

CSV download URL pattern (works without login):
```
https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/<DATASET-ID>/exports/csv
```

### Why this beats TransLink + BC Salary

Earlier draft picked TransLink Open Data + BC Public Salary Disclosure. Both are great employer-matched but:
- TransLink Open Data has operational metrics (ridership, on-time) - no budget vs actual
- BC Salary Disclosure is single-dimension (compensation only) - no P&L hierarchy
- Neither supports the IBCS variance pattern that Zebra-BI / IBCS dashboards are FOR

City of Vancouver capital data has all 4 IBCS-required dimensions: time series (multi-year), hierarchy (category -> project), budget+actual comparison, departmental cost-center attribution.

Backup if Vancouver API rate-limits or goes down: use Kaggle "Financial Dataset [expenses]: Budget VS Actual" (https://www.kaggle.com/datasets/saharsyed/financial-dataset-expenses-budget-vs-actual).

## Secondary sources (optional / context)

### BC Public Accounts
**URL:** https://www2.gov.bc.ca/gov/content/governments/finances/public-accounts
**What:** Ministry-level actuals + budget at provincial scope (way bigger numbers than municipal)
**Fit:** Sidebar comparison page - "your $5M variance vs the province's $500M variance is the same shape"

### BC Public Salary Disclosure (kept for labour-cost layer)
**URL:** https://www2.gov.bc.ca/gov/content/governments/about-the-bc-government/open-government/open-information
**What:** Per-employee compensation across BC public-sector employers
**Fit:** Adds labour-cost dimension to the cost-center attribution page

### TransLink Open Data (kept for ops-context overlay)
**URL:** https://www.translink.ca/about-us/doing-business-with-translink/business-information/open-data
**What:** Ridership · revenue · operating cost per km
**Fit:** Operations-vs-finance overlay page if time allows

### Statistics Canada provincial finance tables
**URL:** https://www.statcan.gc.ca + https://open.canada.ca
**What:** Decades of BC government revenue + expenditure history
**Fit:** Macroeconomic context for the trend pages

### SEC EDGAR XBRL
**URL:** https://www.sec.gov/search-filings/edgar-application-programming-interfaces
**What:** Real public-company P&L / cash flow / balance sheet
**Fit:** Only useful for the SaaS-finance pivot (not the primary BC public-sector plan)

## IBCS-required dimensions vs our data coverage

| IBCS Dimension | Required for | Vancouver Capital | BC Salary | TransLink Ops |
|---|---|---|---|---|
| Time series (multi-year) | PY/AC/PL/FC variance | ✓ (2023-2026) | ✓ (annual) | ✓ (daily/monthly) |
| Hierarchy (category -> sub) | Drill-down + small multiples | ✓ (category -> project) | ✗ (flat) | partial |
| Budget vs actual | The flagship variance chart | ✓ (budget + expenditure) | ✗ (actual only) | ✗ (actual only) |
| Cost-center attribution | Per-FTE / per-BU cost | ✓ (service area / dept) | ✓ (employer) | partial |
| Geographic | Map-based variance | ✓ (project location) | partial | ✓ (route) |

Vancouver Capital wins on the IBCS test by a wide margin.

## Attribution block (required on landing page + Notion page)

```
Data sources:
- City of Vancouver Open Data Portal (Open Government Licence - Vancouver)
- BC Public Salary Disclosure (Open Government Licence - British Columbia)
- TransLink Open Data (TransLink Open Data Licence)
Last refresh: <YYYY-MM-DD>
```

## See also

- [`notes.md`](notes.md) - Week-by-week project plan
- [`README.md`](README.md) - The why + IBCS adherence statement
- [`ibcs-standards.md`](ibcs-standards.md) - IBCS SUCCESS rules + visual grammar this project follows
- [`notion-page.md`](notion-page.md) - Public Notion content (stub until ship)
