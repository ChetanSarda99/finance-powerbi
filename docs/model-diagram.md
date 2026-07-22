# Star schema - finance-powerbi

ASCII sketch of the target Power BI data model. Source: [`power-query-m.md`](power-query-m.md) builds the 4 tables; relationships are wired manually in Power BI Model view.

Last refreshed 2026-05-29.

---

## Star schema (ASCII)

```
                          ┌─────────────────────────┐
                          │      dim_period         │
                          ├─────────────────────────┤
                          │ year_id   (PK)          │
                          │ year                    │
                          │ label    "FY2024"       │
                          └────────────┬────────────┘
                                       │  many-to-one
                                       │
┌─────────────────────────┐            │            ┌────────────────────────────┐
│   dim_service_category  │            │            │      dim_scenario          │
├─────────────────────────┤            │            ├────────────────────────────┤
│ category_id  (PK)       │            │            │ scenario_code  (PK)        │
│ service_category_1      │            │            │ scenario_label             │
│ service_category_2      │            │            │ fill_style "solid_black"   │
│ service_category_3      │            │            └─────────────┬──────────────┘
└────────────┬────────────┘            │                          │
             │                         │                          │
             │   many-to-one           │           many-to-one    │
             └────────────┬────────────┴──────────────┬───────────┘
                          │                           │
                          ▼                           ▼
            ┌───────────────────────────────────────────────────────┐
            │              fact_capital_finance                     │
            ├───────────────────────────────────────────────────────┤
            │ service_category_1  (FK -> dim_service_category)      │
            │ service_category_2  (FK -> dim_service_category)      │
            │ service_category_3  (FK -> dim_service_category)      │
            │ project_program_name                                  │
            │ year                (FK -> dim_period.year_id)        │
            │ scenario            (FK -> dim_scenario.scenario_code)│
            │ amount              (the dollar value)                │
            └───────────────────────────────────────────────────────┘
```

## Grain

ONE row in `fact_capital_finance` = ONE project × ONE year × ONE scenario (AC / PL / FC).

After Power Query M unpivot (see [`power-query-m.md`](power-query-m.md)), expect ~3-4K rows: ~1000 unique projects across ~4 years × ~3 scenarios.

## Dimension cardinality

| Dimension | Rows | Notes |
|---|---|---|
| dim_period | 8 (2023-2030) | Sparse Date table - year-grain only |
| dim_scenario | 4 (AC / PL / FC / PY) | PY is computed via DAX, not loaded |
| dim_service_category | ~300 unique 3-level combos | Pulled from fact distinct, indexed |

## Relationships matrix

| From | To | Type | Cross-filter | Why |
|---|---|---|---|---|
| fact[year] | dim_period[year_id] | many-to-one | single | Time slicers (year, label) drive every page |
| fact[scenario] | dim_scenario[scenario_code] | many-to-one | single | Scenario filter on every variance visual |
| fact[service_category_1] | dim_service_category[service_category_1] | composite-key MtoO | single | Drill from Program down to Project |

(Composite key on service_category is the simplest path; alternatively materialize a `category_id` in fact during M.)

## Row-Level Security (Page 4 + Week 2 task)

Implement RLS on `dim_service_category[service_category_1]` so different user-roles only see their assigned programs:

```dax
// In Power BI -> Modeling -> Manage Roles -> New Role
// Role: "Housing Lead"
[service_category_1] = "Housing"

// Role: "Transportation Lead"
[service_category_1] IN { "Transportation", "Engineering services" }

// Role: "All Access"
1 = 1
```

USERPRINCIPALNAME-driven mapping table can come later if we need per-email assignments instead of group-based roles.

## Star vs snowflake

Pure star here - no snowflake. The 3-level service-category hierarchy could be normalized into 3 dim tables, but the cardinality is low (~300 leaf categories) and Power BI's filter performance penalty for snowflake doesn't earn its keep at this scale.

## Why NOT a single wide table

Tempting at this size to skip the dims and just load the raw CSV after unpivot. Reasons we don't:

1. **DAX time-intelligence** wants a dim_period to navigate ("prior year", "YTD")
2. **Variance grammar** wants a dim_scenario so DAX measures can `CALCULATE ( [Actual], dim_scenario[scenario_code] = "AC" )` cleanly
3. **RLS** is column-level on a dim, not a fact-table predicate
4. **Recruiter readability** - hiring managers SCAN model diagrams in interviews; star schema reads as senior fluency, single-wide-table reads as junior

## See also

- [`power-query-m.md`](power-query-m.md) - the M code that materializes this model
- [`measures.md`](measures.md) - the DAX measures that consume it
- [`../ibcs-standards.md`](../ibcs-standards.md) - how the dim_scenario fill_style column maps to visuals
