# DAX measures - finance-powerbi

> READ FIRST: `INTERVIEW-FINAL.md` (2026-11-12) is the complete, current guide. The report is now v4 (`pbip\finance-powerbi-v4` on the Lenovo): six pages, two of them Deneb custom visuals, 17 measures. Names are consistent everywhere: Actual, Plan, Prior Year, Actual or Plan, Expenditure Budget, Forecast.

All measures use the star schema in [`power-query-m.md`](power-query-m.md). Paste into the Power BI Service web model editor (New measure) or Power BI Desktop. Field names match the shipped processed schema in `data/processed/` (dim_period[period_key], dim_costcenter, no Date table). Each measure has a comment line at the top so the next session can grep for purpose.

Last refreshed 2026-11-12: 17 measures (three added later the same day for page 3: `Forecast FY2027`, `Expenditure Change (FY27 vs FY26)`, `Expenditure Change % (FY27 vs FY26)`, see `pbip/scripts/patch_measures_2.py`). Plan now filters to the capital-plan account so it is like-for-like with Actual; `Actual or Plan`, `Variance Abs (vs PY)`, `Variance Pct (vs PY)` and `Expenditure Budget` were added; the four `AC vs PL` / `AC vs PY` variance measures and `Variance Color (Cost AC vs PL)` were removed (the report colours bars with a rule on `Variance Abs (vs PY)` instead). Earlier, 2026-11-10: 15 measures. Removed two duplicates (`Actual SPLY` was the same as `Prior Year`; `Forecast Accuracy Pct` was the same as `Variance Pct (AC vs PL)`) and renamed `Actual YTD` to `Actual Cumulative`, because it is a running total across years, not a within-year YTD.

---

## Core amount measures (foundation)

```dax
// Total amount across the current filter context. Foundation for all variance work.
Total Amount =
SUM ( fact_capital_finance[amount] )
```

```dax
// Actuals - filtered to scenario=AC
Actual =
CALCULATE ( [Total Amount], dim_scenario[scenario_code] = "AC" )
```

```dax
// Plan = the FY2026 capital-plan allocation (scenario PL, account city_led_alloc_approved_budget).
// Same account as Actual, so Plan and Actual compare like-for-like. The separate FY2026 annual
// expenditure budget is its own measure and is never added in.
Plan =
CALCULATE (
    [Total Amount],
    dim_scenario[scenario_code] = "PL",
    dim_account[account_code] = "city_led_alloc_approved_budget"
)
```

```dax
// Approved capital-plan budget for the year: Actual for elapsed years (FY2023-25), Plan for FY2026.
// One account in every year, so any two years compare like-for-like.
Actual or Plan =
[Actual] + [Plan]
```

```dax
// FY2026 annual capital expenditure budget (capital project budget dataset). A different budget line
// from the capital-plan allocation; shown on its own page with the FY2027-30 forecast.
Expenditure Budget =
CALCULATE ( [Total Amount], dim_account[account_code] = "annual_capital_expenditure_budget" )
```

```dax
// Forecast - filtered to scenario=FC
Forecast =
CALCULATE ( [Total Amount], dim_scenario[scenario_code] = "FC" )
```

```dax
// Prior year actual = Actual shifted one fiscal year back. Explicit shift on
// dim_period[period_key] because this model is year-grain only (no Date table),
// so DATEADD / SAMEPERIODLASTYEAR are not available.
Prior Year =
CALCULATE (
    [Actual],
    FILTER (
        ALL ( dim_period ),
        dim_period[period_key] = MAX ( dim_period[period_key] ) - 1
    )
)
```

## Time-intelligence

```dax
// Running total of Actual across fiscal years, up to and including the selected year.
// Not a within-year YTD: the model is annual grain.
Actual Cumulative =
CALCULATE (
    [Actual],
    FILTER ( ALL ( dim_period ), dim_period[period_key] <= MAX ( dim_period[period_key] ) )
)
```

## Variance measures (the IBCS / Zebra-BI grammar)

```dax
// Actual or Plan minus Prior Year. Blank when the year before has no approved budget at all.
Variance Abs (vs PY) =
VAR c = [Actual or Plan]
VAR p = [Prior Year]
VAR pyExists = NOT ISBLANK ( CALCULATE ( [Prior Year], ALL ( dim_business_unit ), ALL ( dim_costcenter ) ) )
RETURN
    IF ( pyExists && NOT ( ISBLANK ( c ) && ISBLANK ( p ) ), c - p )
```

```dax
// Same change as a percent of Prior Year.
Variance Pct (vs PY) =
DIVIDE ( [Actual or Plan] - [Prior Year], [Prior Year] )
```

```dax
// Forecast for FY2027 only: the city's published FY2027 expected spending.
Forecast FY2027 =
CALCULATE ( [Forecast], dim_period[period_key] = 2027 )
```

```dax
// FY2027 forecast minus FY2026 expenditure budget (both expected spending on approved projects).
Expenditure Change (FY27 vs FY26) =
[Forecast FY2027] - [Expenditure Budget]
```

```dax
// Same change as a percent of the FY2026 expenditure budget.
Expenditure Change % (FY27 vs FY26) =
DIVIDE ( [Forecast FY2027] - [Expenditure Budget], [Expenditure Budget] )
```

## Variance colour (IBCS green/red rule)

There is no colour measure any more. The report colours the variance bars with a rule on `Variance Abs (vs PY)`: below zero green (lower than prior year), above zero red (higher). Cost polarity, per IBCS.

## Page-1 income-statement helpers

```dax
// Year label for axis (so we can show "FY2026" not just "2026")
Year Label =
SELECTEDVALUE ( dim_period[label] )
```

```dax
// Scenario label for column headers (Actual / Plan / Forecast)
Scenario Label =
SELECTEDVALUE ( dim_scenario[scenario_label] )
```

## Page-2 / Page-4 attribution + category share

```dax
// What share of total this category contributes
Category Share Pct =
DIVIDE ( [Actual], CALCULATE ( [Actual], ALL ( dim_costcenter ) ) )
```

```dax
// Running total across the service-category hierarchy (Pareto-style)
Cumulative Share Pct =
VAR currentTotal = [Actual]
VAR cumulative =
    CALCULATE (
        [Actual],
        FILTER (
            ALL ( dim_costcenter ),
            CALCULATE ( [Actual] ) >= currentTotal
        )
    )
RETURN
    DIVIDE ( cumulative, CALCULATE ( [Actual], ALL ( dim_costcenter ) ) )
```

## Format strings (IBCS-friendly defaults)

| Measure | Format string |
|---|---|
| All amount measures | `"$#,0;-$#,0;$0"` (comma thousands, parentheses-free negatives so the green/red bar carries the sign) |
| All Pct measures | `"0.0%;-0.0%;0.0%"` |

## Performance notes

- `Cumulative Share Pct` uses `FILTER ( ALL ( ... ) )` and can be slow on the category cardinality (a few hundred rows). Acceptable on this dataset (~2000 rows after unpivot). If it slows down: replace with `TOPN` + `RANKX` pattern.
- `Variance Pct` uses `DIVIDE`, which handles divide-by-zero cleanly without IFERROR.
- `Prior Year` and `Actual Cumulative` both use an explicit `FILTER ( ALL ( dim_period ) ... )` shift instead of `DATEADD` / `SAMEPERIODLASTYEAR`, because `dim_period` is year-grain only (not a full Date table). If a full Date table is added later, swap both to `SAMEPERIODLASTYEAR ( dim_date[date] )` for cleaner semantics.
- The shift clears the whole `dim_period` table (`ALL ( dim_period )`), not just `period_key`. A slicer or axis on `dim_period[label]` filters a different column; clearing only `period_key` would leave `label = "FY2025"` in place and the shifted year would find no rows (blank Prior Year). A marked date table does this for you.

## Anti-patterns NOT used here

- No DAX iterators wrapped around full table scans (SUMX over fact_capital_finance with no filter is anti-pattern)
- No CALCULATETABLE materializing intermediate row sets the engine could fold
- No nested IF chains for variance direction - use the colour rule on `Variance Abs (vs PY)`
- No measure dependencies > 3 levels deep (current max: Variance Pct -> Variance Abs -> Plan + Actual = 3)

## See also

- [`power-query-m.md`](power-query-m.md) - the model these measures consume
- [`model-diagram.md`](model-diagram.md) - star schema visual
- [`../ibcs-standards.md`](../ibcs-standards.md) - visual grammar rules these measures support
- [`../notes.md`](../notes.md) - week-by-week task table mapping measures to pages
