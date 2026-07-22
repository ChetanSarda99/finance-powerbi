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

- Visuals. The report is one blank page named "Finance Overview". Authoring the
  Deneb / IBCS visuals in raw PBIR JSON is fragile, so it is intentionally left
  out. Build the 8 visuals interactively per `../docs/build-on-mac-online.md`.

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
