# finance-powerbi - Power BI Project (PBIP)

This folder is a ready-to-open Power BI Project (PBIP). It ships the full data
model (six tables, 6 relationships, 17 DAX measures) already built in Tabular
Model Definition Language (TMDL). You open it on Windows Power BI Desktop, point
one parameter at the CSV folder, refresh, and then add visuals yourself.

## What is included vs not

Included (reliable, machine-built):

- Semantic model in TMDL: one table per processed CSV, typed columns
  (keys as int64, amount as double, labels as string).
- Power Query M to load each CSV (Csv.Document, Table.PromoteHeaders,
  explicit Table.TransformColumnTypes), driven by a single DataFolder parameter.
- 6 single-direction many-to-one relationships (the dim_costcenter to
  dim_business_unit link is shipped inactive to avoid an ambiguous join path).
- All 17 DAX measures from `../docs/measures.md`, defined on the
  fact_capital_finance table with IBCS-friendly format strings.

Not included (you add these in Desktop or the Service):

- Deneb visuals and RLS. The Deneb specs live in `../deneb/` and are not in the
  report. No RLS roles exist.

Added 2026-11-09 (generated, see Report pages below):

- Two report pages built from native visuals only: "Budget vs Actual" and
  "Cost-center attribution" (20 visuals). They replace the old blank
  "Finance Overview" page.

## How to open on Windows Power BI Desktop

1. Download two things from the repo onto a Windows machine:
   - this whole `pbip/finance-powerbi/` folder, and
   - the `data/processed/` folder (the six CSV files).
   Keep a short root path. Power BI Desktop has a 260-character path limit and
   long table or folder names can push the total path over it.
2. In Power BI Desktop, enable the preview features once (File > Options and
   settings > Options > Preview features):
   - "Power BI Project (.pbip) save option"
   - "Store semantic model using TMDL format"
   - "Store reports using enhanced metadata format (PBIR)"
   Restart Desktop after enabling them.
3. Open `finance-powerbi/finance-powerbi.pbip`. Desktop opens both the report
   and the semantic model in edit mode. If the .pbip does not open, open
   `finance-powerbi.Report/definition.pbir` directly instead; it opens the
   report and the semantic model the same way (the report points at the model
   by relative path).
4. Set the DataFolder parameter to your local processed folder:
   - Home > Transform data > Manage parameters (or Transform data >
     Edit parameters).
   - Set DataFolder to the FULL local path of the processed CSV folder, for
     example `C:\Users\you\finance-powerbi\data\processed`.
     Use a full path, no trailing slash, no quotes.
5. Close and apply, then Home > Refresh. All six tables load and the measures
   evaluate.
6. Add your visuals on the "Finance Overview" page.

## Report pages (generated 2026-11-09, design pass 2026-11-10)

Source of truth is `scripts/build_report.py` (writes the PBIR JSON), checked by
`scripts/validate_report.py`. Re-run both after any change:

```
python3 -I scripts/build_report.py finance-powerbi/finance-powerbi.Report/definition
python3 -I scripts/validate_report.py finance-powerbi <clone of microsoft/json-schemas>
```

- Page 1 "Budget vs Actual": fiscal-year slicer (default FY2025), business-unit
  slicer, 6 KPI cards, clustered column (Actual, Prior Year, Plan by fiscal year),
  two variance-by-business-unit bars (vs Plan, vs Prior Year), footnote.
- Page 2 "Cost-center attribution": business-unit slicer, matrix
  (business unit > service category > detail with Actual, Plan, variance), top 10
  service categories bar (Top N filter on Actual), footnote.
- Data caveat shown on the pages: Actual is FY2023-25 (approved-budget proxy), Plan
  is FY2026 only, so "AC vs PL" compares different years; "AC vs PY" is like-for-like.
- IBCS: Actual black, Prior Year grey, Plan light fill (native visuals cannot draw
  an outline or hatch), variance green (under) / red (over).
- Variance colours: green/red only on the like-for-like Prior Year bars. Actual vs Plan
  bars, cards and matrix variance are neutral, because Actual is 3 years of one account
  (3) and Plan is 1 year that also holds an account-1 budget line (about CAD 894M).
- Model fix made 2026-11-09: `Prior Year`, `Actual YTD` and `Actual SPLY` now clear
  `ALL ( dim_period )` instead of `ALL ( dim_period[period_key] )`. With a slicer or axis
  on `dim_period[label]`, the old form left the label filter in place and returned blank.
  Measure count unchanged (17). Found by review of DAX semantics, not by an observed render.
- Not built: small multiples, RLS, Deneb visuals.
- Schema versions used: visualContainer 2.10.0, page 2.1.0, pagesMetadata 1.0.0,
  report 3.0.0, versionMetadata version 2.0.0, .pbip version 1.0. Desktop 26.07 ships
  schemas up to visualContainer 2.11.0, page 2.1.0, pagesMetadata 1.1.0, report 3.3.0.

## Verification (2026-11-10)

Opened in Power BI Desktop 2.156.951.0 on Windows on 2026-11-10. Both pages load and
render with data, and the project saves. Checked on screen with FY2025 selected:
Actual $778.2M, Prior Year $651.3M, variance $126.9M (19.5%), Plan FY2026 $1,591.6M.
Screenshots: `../screenshots/page1-budget-vs-actual.png` and
`../screenshots/page2-cost-center-attribution.png`.

Three file-format faults were found and fixed on the first real open:
- `.pbip` had `"version": "1.0.0"`; Desktop accepts `"1.0"`.
- `version.json` said 1.0.0 while the pages used the 2.x page and visual schemas, so
  Desktop loaded the model but silently showed no pages. It is now 2.0.0 with report 3.0.0.
- `report.json` carried `layoutOptimization`, which report 3.0.0 rejects. Removed.

Also verified offline: every report JSON file parses, and all field references match a
real column or measure in the TMDL. Tabular Editor 2.28 loads the model (6 tables,
17 measures, 6 relationships, 0 roles).

First open on a new machine: set the `DataFolder` parameter to your `data/processed`
path, then Refresh and Apply changes.

## Folder layout

```
pbip/finance-powerbi/
  finance-powerbi.pbip
  .gitignore
  finance-powerbi.SemanticModel/
    .platform
    definition.pbism
    definition/
      database.tmdl
      model.tmdl
      expressions.tmdl            (DataFolder parameter)
      relationships.tmdl          (6 relationships)
      tables/
        fact_capital_finance.tmdl (columns + 17 measures)
        dim_account.tmdl
        dim_period.tmdl
        dim_costcenter.tmdl
        dim_business_unit.tmdl
        dim_scenario.tmdl
  finance-powerbi.Report/
    .platform
    definition.pbir               (byPath to the SemanticModel)
    definition/
      version.json
      report.json
      pages/
        pages.json
        financeOverview/
          page.json               (one blank page)
```

## Notes

- The model is year-grain only (no Date table). Prior Year and SPLY use an
  explicit FILTER shift on dim_period[period_key]; see `../docs/measures.md`.
- Scenario filtering uses dim_scenario[scenario_code] (AC / PL / FC / PY).
- Edit any file as UTF-8 without BOM. Power BI Desktop uses CRLF line endings;
  if you re-save these files, keep that in mind for clean diffs.

## Validation status

These files were generated and machine-checked on macOS (no Power BI Desktop,
which is Windows-only):

- All JSON files (.pbip, .pbir, .pbism, .platform, report/page JSON) are
  well-formed and carry every required property and enum value from the
  published Microsoft Fabric JSON schemas.
- TMDL files were checked structurally only (tab indentation, balanced let/in,
  single-quoted measure names, expression vs property indentation depth). They
  were NOT compiled by a TMDL parser, and the M was NOT executed.
- Full validation (TMDL parse, .pbip open, data refresh) requires Power BI
  Desktop on Windows. Two things a Windows open should confirm: that the .pbip
  `artifacts[].report.path` resolves (if not, use the definition.pbir fallback
  above), and that the report.json base theme name is recognized (a stale theme
  name falls back to the default theme and is non-blocking).
