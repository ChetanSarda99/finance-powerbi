# Power Query M transformations

Paste each block into Power BI Desktop -> Transform Data -> Advanced Editor when building the PBIX. One query per table in the star schema. Source paths assume the PBIX file lives at `pbix/finance-portfolio.pbix` (sibling to `data/`).

Last refreshed 2026-05-29.

---

## fact_capital_finance (UNPIVOTED + UNIONED from both raw CSVs)

Wide source -> long fact table. One row per project × scenario × year. Three scenario codes: `AC` (actual = "city-led-allocations" columns), `PL` (planned/budgeted = "approved_budget" columns), `FC` (forecast = "forecast" columns from the 2026 capital project budget CSV).

```m
let
    // Source 1: 2023-2026 capital plan (AC + PL for 2023-2025, PL for 2026)
    Source_Plan = Csv.Document(
        File.Contents("..\data\raw\vancouver-2023-2026-capital-plan.csv"),
        [Delimiter = ",", Columns = 18, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promote_Plan = Table.PromoteHeaders(Source_Plan, [PromoteAllScalars = true]),
    // Keep only the year-allocation columns we care about
    Select_Plan = Table.SelectColumns(Promote_Plan, {
        "service_category_1", "service_category_2", "service_category_3", "project_program_name",
        "2023_2026_capital_plan_city_led_allocations_2023_approved_budget",
        "2023_2026_capital_plan_city_led_allocations_2024_approved_budget",
        "2023_2026_capital_plan_city_led_allocations_2025_approved_budget",
        "2023_2026_capital_plan_city_led_allocations_2026_budget"
    }),
    Unpivot_Plan = Table.UnpivotOtherColumns(
        Select_Plan,
        {"service_category_1", "service_category_2", "service_category_3", "project_program_name"},
        "year_col", "amount"
    ),
    // Derive year + scenario from the column name
    Plan_With_Year = Table.AddColumn(Unpivot_Plan, "year",
        each Number.From(Text.Middle([year_col], 55, 4)), Int64.Type),
    Plan_With_Scenario = Table.AddColumn(Plan_With_Year, "scenario",
        each if [year] <= 2025 then "AC" else "PL", type text),
    Plan_Final = Table.SelectColumns(Plan_With_Scenario, {
        "service_category_1", "service_category_2", "service_category_3",
        "project_program_name", "year", "scenario", "amount"
    }),

    // Source 2: 2026 capital project budget (PL for 2026, FC for 2027-2030)
    Source_Budget = Csv.Document(
        File.Contents("..\data\raw\vancouver-2026-capital-project-budget.csv"),
        [Delimiter = ",", Columns = 20, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promote_Budget = Table.PromoteHeaders(Source_Budget, [PromoteAllScalars = true]),
    Select_Budget = Table.SelectColumns(Promote_Budget, {
        "service_category_1", "service_category_2", "service_category_3", "project_program_name",
        "annual_capital_expenditure_2026_capital_expenditure_budget",
        "annual_capital_expenditure_2027_forecast",
        "annual_capital_expenditure_2028_forecast",
        "annual_capital_expenditure_2029_forecast",
        "annual_capital_expenditure_2030_forecast"
    }),
    Unpivot_Budget = Table.UnpivotOtherColumns(
        Select_Budget,
        {"service_category_1", "service_category_2", "service_category_3", "project_program_name"},
        "year_col", "amount"
    ),
    Budget_With_Year = Table.AddColumn(Unpivot_Budget, "year",
        each Number.From(Text.Middle([year_col], 28, 4)), Int64.Type),
    Budget_With_Scenario = Table.AddColumn(Budget_With_Year, "scenario",
        each if [year] = 2026 then "PL" else "FC", type text),
    Budget_Final = Table.SelectColumns(Budget_With_Scenario, {
        "service_category_1", "service_category_2", "service_category_3",
        "project_program_name", "year", "scenario", "amount"
    }),

    // Union + clean
    Unioned = Table.Combine({Plan_Final, Budget_Final}),
    Typed = Table.TransformColumnTypes(Unioned, {
        {"amount", Int64.Type},
        {"year", Int64.Type}
    }),
    NonZero = Table.SelectRows(Typed, each [amount] <> null and [amount] <> 0)
in
    NonZero
```

## dim_period

```m
let
    Source = Table.FromRecords({
        [year_id = 2023, year = 2023, label = "FY2023"],
        [year_id = 2024, year = 2024, label = "FY2024"],
        [year_id = 2025, year = 2025, label = "FY2025"],
        [year_id = 2026, year = 2026, label = "FY2026"],
        [year_id = 2027, year = 2027, label = "FY2027"],
        [year_id = 2028, year = 2028, label = "FY2028"],
        [year_id = 2029, year = 2029, label = "FY2029"],
        [year_id = 2030, year = 2030, label = "FY2030"]
    }),
    Typed = Table.TransformColumnTypes(Source, {
        {"year_id", Int64.Type}, {"year", Int64.Type}, {"label", type text}
    })
in
    Typed
```

## dim_scenario

```m
let
    Source = Table.FromRecords({
        [scenario_code = "AC", scenario_label = "Actual",   fill_style = "solid_black"],
        [scenario_code = "PL", scenario_label = "Plan",     fill_style = "outlined"],
        [scenario_code = "FC", scenario_label = "Forecast", fill_style = "hatched"],
        [scenario_code = "PY", scenario_label = "Prior Year", fill_style = "solid_grey"]
    }),
    Typed = Table.TransformColumnTypes(Source, {
        {"scenario_code", type text}, {"scenario_label", type text}, {"fill_style", type text}
    })
in
    Typed
```

(`fill_style` column is reference-only - Power BI doesn't read it; it's there so the visual designer can look up "what color/fill does AC get" without hunting the spec.)

## dim_service_category

```m
let
    Source = #"fact_capital_finance",
    Distinct = Table.Distinct(Table.SelectColumns(Source, {
        "service_category_1", "service_category_2", "service_category_3"
    })),
    Indexed = Table.AddIndexColumn(Distinct, "category_id", 1, 1, Int64.Type),
    Reordered = Table.SelectColumns(Indexed, {
        "category_id", "service_category_1", "service_category_2", "service_category_3"
    })
in
    Reordered
```

`service_category_1` is the top-level program (Housing, Transportation, Parks, etc.). `_2` is the sub-program. `_3` is the specific area. This is the natural drill hierarchy for the dashboard.

## Relationships (build manually in Power BI Model view)

| From | To | Cardinality | Cross-filter |
|---|---|---|---|
| fact_capital_finance[year] | dim_period[year_id] | many-to-one | single |
| fact_capital_finance[scenario] | dim_scenario[scenario_code] | many-to-one | single |
| fact_capital_finance[service_category_1] + [_2] + [_3] | dim_service_category[service_category_1] + [_2] + [_3] | many-to-one (composite key) | single |

The composite key on service_category is the easiest path; alternatively materialize a category_id in fact during M-script.

## See also

- [`measures.md`](measures.md) - the DAX measures that consume this model
- [`model-diagram.md`](model-diagram.md) - star schema sketch
- [`../data/README.md`](../data/README.md) - source CSVs + fetch script
