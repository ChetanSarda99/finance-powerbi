# Build this dashboard on a Mac (no Windows) via the Power BI Service web authoring path

> Update 2026-11-10: the model now has 15 measures. `Actual SPLY` and `Forecast Accuracy Pct` were removed as duplicates and `Actual YTD` was renamed `Actual Cumulative`. Where this guide names those three, use `Prior Year`, `Variance Pct (AC vs PL)` and `Actual Cumulative`.

Power BI Desktop is Windows-only, but you do NOT need it for this project. As of
2026, **semantic-model editing in the Power BI Service (browser, app.powerbi.com)
is Generally Available**: in any modern browser on macOS you can create import
models, manage relationships, author DAX measures with IntelliSense, define
row-level security (RLS), build report pages, and add Deneb custom visuals from
AppSource. Power Query-heavy ingestion and `.pbix` file authoring still need
Desktop, but this project's data is already processed (the star schema in
`data/processed/` plus the denormalized `finance_capital_flat.csv`), so the web
path covers the whole build.

This guide has two tracks. Pick one:

- **TRACK A (recommended): the full star schema.** Upload the six
  `data/processed/*.csv`, wire relationships in the browser model editor, paste
  the DAX from `docs/measures.md`, build the 4 pages, add Deneb visuals, publish.
  This is the portfolio-grade artifact (time-intelligence, RLS, conformed dims).
- **TRACK B (fastest): the single flat table.** Upload only
  `data/processed/finance_capital_flat.csv`. Power BI auto-creates a one-table
  model, no relationships to manage. Build the pages with flat-table measures.
  Fastest path to a shippable link; trade-off noted below.

Both tracks end with **Publish to web (public)** for a free, embeddable portfolio
link you can drop into the Notion portfolio page.

Prerequisites for either track:

1. A Microsoft account with a Power BI (Fabric) free license. A personal
   `@outlook.com` / `@hotmail.com` consumer account does NOT get a Power BI
   license; you need a work/school-style account (a UBC alumni mailbox, a free
   Microsoft 365 Developer tenant, or a Fabric free trial all work). Sign in at
   https://app.powerbi.com and confirm you land on the Service home, not an
   upsell page.
2. The CSVs from this repo, downloaded to the Mac you are browsing from.
3. Chrome, Edge, Safari, or Firefox (current versions all work; Edge/Chrome are
   the smoothest for the Deneb visual editor).

---

## TRACK A: full star schema (recommended)

### A1. Create a workspace

1. app.powerbi.com -> left nav -> **Workspaces** -> **New workspace**.
2. Name it `finance-powerbi` (or similar). A workspace is required to author a
   semantic model in the browser; you cannot do model editing in **My workspace**
   for uploaded files in the same way.

### A2. Upload the six processed CSVs

Upload each of these from `data/processed/`:

- `fact_capital_finance.csv` (1981 rows, the fact)
- `dim_account.csv` (4 rows)
- `dim_period.csv` (9 rows)
- `dim_costcenter.csv` (120 rows)
- `dim_business_unit.csv` (13 rows)
- `dim_scenario.csv` (4 rows)

Per file: workspace -> **New** -> **Semantic model** (or **Upload** -> the CSV).
For CSVs the Service uses the lightweight uploader: **New** -> **Upload a file**
-> **Local file** -> pick the CSV. Each CSV becomes a table. Upload the fact
first, then the five dims, then combine them into one model (next step). If the
uploader creates a separate model per file, use **Get data** inside one model and
add the other tables, or recreate by importing all six into a single new model so
they share a model namespace. The goal: one semantic model containing all six
tables.

Verify the control total immediately: put a card visual on
`SUM(fact_capital_finance[amount])`. It must read **8,618,616,154**. If it does
not, a CSV did not import fully (re-upload that file).

### A3. Set relationships (browser model view)

Open the semantic model -> **Open data model** (the web model editor, the same
relationship canvas Desktop has). Create these relationships. Every one is
**many-to-one** (fact side = many) with **single** cross-filter direction
(dims filter the fact, never the reverse):

| From (many) | To (one) | Cardinality | Cross-filter |
|---|---|---|---|
| `fact_capital_finance[account_key]` | `dim_account[account_key]` | many-to-one | single |
| `fact_capital_finance[period_key]` | `dim_period[period_key]` | many-to-one | single |
| `fact_capital_finance[costcenter_key]` | `dim_costcenter[costcenter_key]` | many-to-one | single |
| `fact_capital_finance[business_unit_key]` | `dim_business_unit[business_unit_key]` | many-to-one | single |
| `fact_capital_finance[scenario]` | `dim_scenario[scenario_code]` | many-to-one | single |
| `dim_costcenter[business_unit_key]` | `dim_business_unit[business_unit_key]` | many-to-one | single (optional snowflake) |

Drag the FK onto the PK to create each; then click the relationship line and
confirm cardinality + cross-filter in the properties pane. The last one (cost
center to business unit) is an optional snowflake link; keep it single-direction
so it does not create ambiguous filter paths.

### A4. Author the DAX measures (web DAX editor)

In the model editor, select the `fact_capital_finance` table -> **New measure**.
The web editor has IntelliSense. Paste the measures from `docs/measures.md`.

**Three fixes are required or those measures error.** `docs/measures.md` was
written against an earlier model and references columns (and a time-intel
pattern) this schema does not support:

1. **`dim_period[year_id]` does not exist.** This schema uses
   `dim_period[period_key]` (same year-grain integer values). Affected measures:
   `Prior Year`, `Actual YTD`, `Actual SPLY`. Either (a) rename the column to
   `year_id` on the `dim_period` table in the model editor, or (b) find-replace
   `dim_period[year_id]` with `dim_period[period_key]` in those three measures.
   Option (b) is cleaner (no schema drift). `data/processed/README.md` notes this
   same gap.
2. **`dim_service_category` does not exist as a table.** This schema's
   service-category hierarchy lives on `dim_costcenter`
   (`service_category_1/2/3`). Affected measures: `Category Share Pct`,
   `Cumulative Share Pct`. Replace `ALL ( dim_service_category )` with
   `ALL ( dim_costcenter[service_category_1] )` (or the deeper level you are
   slicing by). There is no standalone service-category dimension to clear; you
   clear the relevant `dim_costcenter` column(s) instead.
3. **`Prior Year` uses `DATEADD`, which needs a real Date table.** The shipped
   measure is
   `Prior Year = CALCULATE ( [Actual], DATEADD ( dim_period[year_id], -1, YEAR ) )`.
   `DATEADD` requires a date-typed column marked as the date table; this schema's
   period column is an INTEGER year (2022-2030), not a date, so the year_id rename
   in fix 1 is not enough -- `DATEADD` will still error / return blank.
   `Variance Abs (AC vs PY)` and `Variance Pct (AC vs PY)` both depend on
   `[Prior Year]`, so the entire AC-vs-PY variance strip on Pages 1 and 3 breaks
   until this is fixed. (Note: `docs/measures.md` already wrote `Actual SPLY` with
   an explicit `FILTER` shift to dodge exactly this; `Prior Year` was left on
   `DATEADD` by oversight.) Rewrite `Prior Year` to the same explicit-shift
   pattern:

   ```dax
   Prior Year =
   CALCULATE (
       [Actual],
       FILTER (
           ALL ( dim_period ),
           dim_period[period_key] = MAX ( dim_period[period_key] ) - 1
       )
   )
   ```

   (If you would rather match Track B's semantics, define `Prior Year` as the PY
   scenario bucket instead: `CALCULATE ( [Total Amount], dim_scenario[scenario_code] = "PY" )`.
   Pick one; the explicit-shift version above gives true year-over-year, the
   scenario-bucket version gives the cumulative pre-window PY total.) The proper
   fix is a real Date table (Get data -> blank query, generate a Date table, mark
   it as date, relate to the fact), after which you can use
   `SAMEPERIODLASTYEAR ( dim_date[date] )` cleanly -- but the explicit shift above
   ships without that.

After those edits, paste the rest verbatim:
`Total Amount`, `Actual`, `Plan`, `Forecast`, `Actual YTD`,
`Actual SPLY`, `Variance Abs (AC vs PL)`, `Variance Pct (AC vs PL)`,
`Variance Abs (AC vs PY)`, `Variance Pct (AC vs PY)`,
`Variance Color (Cost AC vs PL)`, `Year Label`, `Scenario Label`,
`Category Share Pct`, `Cumulative Share Pct`, `Forecast Accuracy Pct`
(`Prior Year` is the rewrite above, not verbatim).

Set the format strings from the table at the bottom of `docs/measures.md`
(amount measures `"$#,0;-$#,0;$0"`, percent measures `"0.0%;-0.0%;0.0%"`) via
each measure's **Format** in the properties pane.

### A5. (Optional) Row-level security

The model diagram makes `dim_business_unit` the RLS boundary. In the model
editor -> **Manage roles** (web RLS authoring is GA): create a role, e.g.
`BU Owner`, with a table filter on `dim_business_unit`:

```dax
[business_unit_name] = USERPRINCIPALNAME()
```

(or a static demo filter such as `[business_unit_name] = "Housing"` for the
portfolio screenshot). Test with **View as role**. RLS is a deliberate
portfolio signal for healthcare-finance roles; keep at least one role defined.

### A6. Build the four report pages

From the semantic model -> **Create report** (blank). Add four pages. The Deneb
visual is added once per page where a spec is used (step A7 covers importing it).
Native visuals come from the standard visual gallery.

The per-page visual map below is authoritative: the Deneb spec-to-page
assignments come from each spec's own `description` (see `deneb/specs/*.json`
and `deneb/README.md`), and the native visuals come from the page scope in
`README.md`.

**Page 1 - Income statement explorer** (`README.md` page 1)
- Deneb: `01-variance-column-ac-pl-fc.vl.json` (scenario columns AC/PL/FC by
  year), `02-variance-table-inline-bars.vl.json` (variance table, one faceted
  row per service category), `03-waterfall-bridge.vl.json` (bridge building the
  Actual total up from each category).
- Native: a **Matrix** of `dim_costcenter[service_category_1/2/3]` (rows) by
  `dim_scenario[scenario_label]` (columns) on `[Total Amount]`, with
  `dim_business_unit` and `dim_period` slicers for the P&L-line x period x BU
  drill. Conditional-format a column on `Variance Color (Cost AC vs PL)`
  (good=green, bad=red, neutral=grey).

**Page 2 - Cash flow + working capital** (`README.md` page 2)
- Deneb: `04-trend-with-reference-line.vl.json` (Actual solid black line over a
  dashed grey Plan reference, by year).
- Native: a **Line chart** of `[Actual]` vs `[Plan]` over `dim_period[label]`;
  a 12-month-style **Matrix heatmap** of category x year on
  `Variance Pct (AC vs PL)` with green/red conditional formatting.
- Honesty note: this is the most data-constrained page. The Vancouver capital
  dataset has no AR/AP, DSO/DPO, or sub-annual cash-flow detail, so present
  Page 2 as a **capital-spend trend + period-over-period variance** view (the
  working-capital framing from `README.md` is aspirational for a transaction
  ledger this source does not provide). Say so in the page caption rather than
  faking AR/AP series.

**Page 3 - Budget vs actual** (`README.md` page 3)
- Deneb: `01-variance-column-ac-pl-fc.vl.json` (reused for the AC/PL/FC columns),
  `05-relative-variance-lollipop.vl.json` (percent-variance pins, green=under
  plan, red=over), `06-variance-heatmap.vl.json` (category x year diverging
  AC-vs-PL heatmap, single scale).
- Native: a **Clustered column / KPI** strip on `Forecast Accuracy Pct` by
  quarter/year; the price-volume-mix framing in `README.md` is approximated by
  the lollipop + heatmap decomposition of the AC-vs-PL variance (this source has
  no volume/price split, so the "3 honest drivers" reduce to category-level
  variance attribution; note the simplification).

**Page 4 - Cost-center attribution** (`README.md` page 4)
- Deneb: `07-small-multiples-by-category.vl.json` (one mini Actual-vs-Plan
  column chart per category, shared scale), `08-cost-allocation-sankey.vg.json`
  (Vega, NOT Vega-Lite: cost flows from `service_category_1` into
  `business_unit`, link thickness = sum of `amount` where `scenario = AC`).
- Native: a **Matrix** cost-by-BU comparison panel
  (`dim_business_unit[business_unit_name]` x `dim_scenario`) and a text/dynamic
  card for the annotations layer.

### A7. Add the Deneb custom visual + paste each spec

1. On a report page -> **Get more visuals** (the `...` on the visualizations
   pane) -> **AppSource** -> search **Deneb** -> **Add**. Deneb is a certified
   custom visual and runs in the Service. (Custom visuals from AppSource are
   allowed; if your tenant blocks org-store visuals, ask the tenant admin or use
   a Developer tenant where you are admin.)
2. Drop a Deneb visual on the page. Into its **Values** well, add the dataset
   fields each spec's `description` lists. For the star-schema model use the
   dimension columns + the `amount` measure (or the `Actual` / `Plan` measures):
   - `01`, `04`: `dim_period[year]` (as `year`), `dim_scenario[scenario_code]`
     (as `scenario`), `[Total Amount]` (as `amount`).
   - `02`, `03`, `05`: `dim_costcenter[service_category_1]`,
     `dim_scenario[scenario_code]`, `[Total Amount]`.
   - `06`, `07`: `dim_costcenter[service_category_1]`, `dim_period[year]`,
     `dim_scenario[scenario_code]`, `[Total Amount]`.
   - `08` (Sankey): `dim_costcenter[service_category_1]`,
     `dim_business_unit[business_unit_name]` (as `business_unit`),
     `dim_scenario[scenario_code]`, `[Total Amount]`.

     Deneb references fields by the names the visual sees in the **Values** well.
     If a column name does not match the spec's expected field (e.g. the spec
     wants `business_unit` but your column is `business_unit_name`), rename the
     field in the Values well (double-click the field pill -> rename) so it
     matches the spec, or edit the spec's field references. The exact field names
     each spec expects are in its `description`.
3. Open the Deneb **Edit** (pencil) -> spec editor. Leave the provider on
   **Vega-Lite** for the seven `*.vl.json` specs; **switch the provider to Vega**
   for `08-cost-allocation-sankey.vg.json` (it is full Vega, not Vega-Lite).
   Paste the spec file's contents, **Apply**.
4. Paste `deneb/theme.json`'s `config` block into Deneb settings (Edit ->
   **Config**) so the IBCS scenario fills + variance colours stay consistent
   across all eight visuals (black=Actual, grey=Prior Year, outlined=Plan,
   hatched=Forecast; green=better / red=worse).

Tip: each spec uses `{"data": {"name": "dataset"}}`, the Deneb convention, so it
binds to whatever you put in the Values well; you do not edit the data block.

### A8. Publish + Publish to web (public)

1. **Save** the report into the workspace.
2. **File** -> **Publish to web (public)** -> generate the embed/public link.
   This creates a free, anonymous, public link suitable for a portfolio (anyone
   with the link can view; do not use it for confidential data, which this public
   Vancouver data is not). Use the link in the Notion portfolio page.
   - Note: **Publish to web** must be enabled in tenant settings (admin portal).
     On a Developer/own tenant you control this. If disabled and you cannot
     change it, fall back to a screenshot gallery + the `.pbix`/report file as the
     portfolio artifact, or use the fallback environment below.

---

## TRACK B: single flat table (fastest to a shippable link)

Use `data/processed/finance_capital_flat.csv` (1981 rows; SUM(amount) =
8,618,616,154; same control total as the star schema). It is the star schema
LEFT-joined to every dimension, so every attribute column sits on each fact row:
`project_program_name`, `year`, `period_label`, `year_label`, `scenario`,
`scenario_label`, `account_label`, `service_category_1/2/3`,
`business_unit_name`, plus Deneb-facing aliases `business_unit` and `year_label`,
plus `amount` and the original surrogate keys for traceability.

### B1. Upload one file, get a one-table model

1. app.powerbi.com -> workspace -> **New** -> **Upload a file** ->
   `finance_capital_flat.csv`. Power BI auto-creates a one-table semantic model.
   No relationships to manage.
2. Verify: a card on `SUM(finance_capital_flat[amount])` reads
   **8,618,616,154**.

### B2. Flat-table measures (rewrites, paste these)

On a flat table there is no `dim_scenario` table to filter, so the measures
filter the flat table's own `scenario` column. Paste these (they are the
`docs/measures.md` measures rewritten for the single table):

```dax
Total Amount = SUM ( finance_capital_flat[amount] )

Actual   = CALCULATE ( [Total Amount], finance_capital_flat[scenario] = "AC" )
Plan     = CALCULATE ( [Total Amount], finance_capital_flat[scenario] = "PL" )
Forecast = CALCULATE ( [Total Amount], finance_capital_flat[scenario] = "FC" )
Prior Year = CALCULATE ( [Total Amount], finance_capital_flat[scenario] = "PY" )

Variance Abs (AC vs PL) = [Actual] - [Plan]
Variance Pct (AC vs PL) = DIVIDE ( [Actual] - [Plan], [Plan] )
Variance Abs (AC vs PY) = [Actual] - [Prior Year]
Variance Pct (AC vs PY) = DIVIDE ( [Actual] - [Prior Year], [Prior Year] )

Variance Color (Cost AC vs PL) =
VAR v = [Variance Abs (AC vs PL)]
RETURN IF ( v < 0, "good", IF ( v > 0, "bad", "neutral" ) )

Category Share Pct =
DIVIDE ( [Actual], CALCULATE ( [Actual], ALL ( finance_capital_flat[service_category_1] ) ) )

Forecast Accuracy Pct = DIVIDE ( [Actual], [Plan] ) - 1
```

Use the same format strings as Track A (`"$#,0;-$#,0;$0"` for amounts,
`"0.0%;-0.0%;0.0%"` for percents).

### B3. Time-intelligence trade-off (name it honestly)

On the flat table, `Prior Year` is filtered by the `scenario = "PY"` bucket, not
shifted by a date table, so it behaves correctly for this data. But the
**year-over-year time-intelligence measures lose their elegance**:

- `Prior Year` here is the PY scenario bucket (cumulative pre-window budget
  anchored to FY2022), NOT a generic "the same measure one year earlier" shift.
- `Actual YTD` and `Actual SPLY` from `docs/measures.md` rely on shifting a
  `dim_period` year column; with no separate period dimension and no proper Date
  table, `DATEADD` / `SAMEPERIODLASTYEAR` will not behave. Drop those two
  measures on Track B, or add a real Date table (Track A territory).
- `Cumulative Share Pct` (the Pareto running total) still works but you reference
  `ALL ( finance_capital_flat[service_category_1] )` instead of a dim.

Net: Track B gets you the four pages and the variance grammar fast, but the
crisp time-intelligence story (the hardest, most resume-worthy DAX surface) is
better told on Track A's star schema with a Date table.

### B4. Build the pages + Deneb + publish

Same as Track A steps A6, A7, A8, except:
- In each Deneb visual's **Values** well, use the flat table's columns directly:
  `year` / `scenario` / `amount` for specs 01 and 04; add `service_category_1`
  for 02, 03, 05, 06, 07; and `business_unit` for the Sankey (08). The flat table
  already carries `business_unit` and `year_label` under the exact names the
  specs expect, so **no field renaming is needed** on Track B.
- For native visuals, use the flat columns (`service_category_1/2/3`,
  `business_unit_name`, `scenario_label`, `period_label`) in place of the dim
  columns.

---

## If you hit a web-authoring limit (fallback to real Power BI Desktop)

The web path covers everything this project needs, but if you hit a hard wall
(tenant blocks Publish to web or AppSource custom visuals, you need Power Query
transforms, or you want to ship the actual `.pbix` source file), run real Power
BI Desktop without leaving the Mac:

- **The Lenovo Legion, already set up.** Power BI Desktop is installed and the
  TMDL model + source CSVs are already staged there (see
  `build-on-lenovo.md`) - this is now the fastest fallback, no VM/cloud
  spin-up needed. RDP or sit at the console, open the `.pbip`, build the pages.
- **Parallels Desktop + Windows 11 ARM.** Install Parallels on the Apple-silicon
  Mac, run Windows 11 ARM, install Power BI Desktop (the ARM build runs natively;
  the x64 build runs under Windows-on-ARM emulation). Then follow Option A in
  `data/processed/README.md` to load the six CSVs and build the `.pbix`. This is
  the most self-contained fallback and gives you the publishable `.pbix`.
- **Azure Virtual Desktop (or a Windows 365 Cloud PC / any Windows VM).** Spin up
  a Windows host in the cloud, RDP in from the Mac, install Power BI Desktop
  there. No local install; pay-per-hour. Good if you only need Desktop briefly
  for the publish step.

Either way the model + measures + specs in this repo are identical; only the host
changes.

---

## Cross-reference index

- Star-schema load instructions (the Desktop equivalent of Track A):
  `data/processed/README.md` (Option A).
- DAX measures (and the two column-name caveats): `docs/measures.md`.
- Deneb specs + per-spec page assignments and required fields:
  `deneb/README.md` and each `deneb/specs/*.json` `description`.
- Deneb theme (IBCS fills + variance colours): `deneb/theme.json`.
- Standalone spec preview without Power BI (renders in the Vega/Vega-Lite editor
  on this Mac): the "Preview a spec without Power BI" section of
  `deneb/README.md`.
- IBCS visual grammar the pages follow: `ibcs-standards.md`.
- Page scope (the 4 pages): `README.md`.
- The flat table builder + control-total guard: `finance_capital_flat.csv` is
  derived from the six `data/processed/*.csv`; row count 1981, SUM(amount)
  8,618,616,154.
