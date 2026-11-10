# DAX measures - finance-powerbi

All measures use the star schema in [`power-query-m.md`](power-query-m.md). Paste into the Power BI Service web model editor (New measure) or Power BI Desktop. Field names match the shipped processed schema in `data/processed/` (dim_period[period_key], dim_costcenter, no Date table). Each measure has a comment line at the top so the next session can grep for purpose.

Last refreshed 2026-11-10: 15 measures. Removed two duplicates (`Actual SPLY` was the same as `Prior Year`; `Forecast Accuracy Pct` was the same as `Variance Pct (AC vs PL)`) and renamed `Actual YTD` to `Actual Cumulative`, because it is a running total across years, not a within-year YTD.

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
// Budget / Plan - filtered to scenario=PL
Plan =
CALCULATE ( [Total Amount], dim_scenario[scenario_code] = "PL" )
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
// Actual minus Plan (absolute variance). Sign is the actual difference.
Variance Abs (AC vs PL) =
[Actual] - [Plan]
```

```dax
// Relative variance Actual vs Plan, percent.
Variance Pct (AC vs PL) =
DIVIDE ( [Actual] - [Plan], [Plan] )
```

```dax
// Actual minus Prior Year (absolute, year-over-year)
Variance Abs (AC vs PY) =
[Actual] - [Prior Year]
```

```dax
// Same but relative
Variance Pct (AC vs PY) =
DIVIDE ( [Actual] - [Prior Year], [Prior Year] )
```

## Variance color flag (IBCS green/red rule, direction-aware)

```dax
// Returns "good" or "bad" based on variance direction AND metric polarity.
// For capital expenditure, UNDER budget = good (less spent). Color the bar
// green when variance < 0 (spent less), red when > 0 (spent more).
// For revenue (not applicable in capital plan but pattern reusable): inverted.
Variance Color (Cost AC vs PL) =
VAR v = [Variance Abs (AC vs PL)]
RETURN
    IF ( v < 0, "good", IF ( v > 0, "bad", "neutral" ) )
```

Wire this in conditional formatting: column "Color" = Field value, "Variance Color (Cost AC vs PL)", map `good -> green`, `bad -> red`, `neutral -> grey`.

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
| Variance Color | `"0"` (text - leave default) |

## Performance notes

- `Cumulative Share Pct` uses `FILTER ( ALL ( ... ) )` and can be slow on the category cardinality (a few hundred rows). Acceptable on this dataset (~2000 rows after unpivot). If it slows down: replace with `TOPN` + `RANKX` pattern.
- `Variance Pct` uses `DIVIDE`, which handles divide-by-zero cleanly without IFERROR.
- `Prior Year` and `Actual Cumulative` both use an explicit `FILTER ( ALL ( dim_period ) ... )` shift instead of `DATEADD` / `SAMEPERIODLASTYEAR`, because `dim_period` is year-grain only (not a full Date table). If a full Date table is added later, swap both to `SAMEPERIODLASTYEAR ( dim_date[date] )` for cleaner semantics.
- The shift clears the whole `dim_period` table (`ALL ( dim_period )`), not just `period_key`. A slicer or axis on `dim_period[label]` filters a different column; clearing only `period_key` would leave `label = "FY2025"` in place and the shifted year would find no rows (blank Prior Year). A marked date table does this for you.

## Anti-patterns NOT used here

- No DAX iterators wrapped around full table scans (SUMX over fact_capital_finance with no filter is anti-pattern)
- No CALCULATETABLE materializing intermediate row sets the engine could fold
- No nested IF chains for variance direction - use the `Variance Color` measure
- No measure dependencies > 3 levels deep (current max: Variance Pct -> Variance Abs -> Plan + Actual = 3)

## See also

- [`power-query-m.md`](power-query-m.md) - the model these measures consume
- [`model-diagram.md`](model-diagram.md) - star schema visual
- [`../ibcs-standards.md`](../ibcs-standards.md) - visual grammar rules these measures support
- [`../notes.md`](../notes.md) - week-by-week task table mapping measures to pages
