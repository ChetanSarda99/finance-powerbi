# Build this dashboard on the Lenovo (real Power BI Desktop, Windows 11)

Status as of the investigation session below: **Power BI Desktop is now installed
and working on the Lenovo Legion** (`ssh lenovo`, Tailscale, Windows 11 Pro), and
the TMDL semantic model has been validated (and one real bug fixed) with an
open-source CLI tool - all without touching Chetan's Microsoft/Fabric login. This
supersedes the "Lenovo is dev-workload-free" default for Power BI specifically;
see the footprint note at the bottom.

This is a faster, cleaner path than the browser-based Track A/B in
`build-on-mac-online.md` because it's the real product (no AppSource-visual
tenant-policy risk, no web-editor feature gaps) - but building the 4 report
pages is still manual GUI work, and publishing still needs Chetan's own
interactive Microsoft login. Neither of those can be done by an agent on any
machine.

---

## What's ready right now

| Item | State |
|---|---|
| Power BI Desktop | Installed, version 2.156.951.0 (26.07), at `C:\Program Files\Microsoft Power BI Desktop` |
| Tabular Editor 2 (free/OSS CE) | Portable install at `C:\Users\Chetan Sarda\powerbi-portfolio\tools\TabularEditor\` - CLI-validates TMDL without needing Desktop or a login |
| TMDL semantic model | Copied to `C:\Users\Chetan Sarda\powerbi-portfolio\pbip\finance-powerbi\` and validates cleanly (see below) |
| Source data | Copied to `C:\Users\Chetan Sarda\powerbi-portfolio\data\processed\` (the six CSVs `dim_account`, `dim_period`, `dim_costcenter`, `dim_business_unit`, `dim_scenario`, `fact_capital_finance`, plus `finance_capital_flat.csv`) |
| Report pages / visuals / RLS | Not built. Untouched - this is the genuinely manual part. |

## How the model was validated

Tabular Editor 2.28.0 Community Edition (free, open-source, MIT-licensed, no
Power BI Desktop or login required) has a headless CLI mode: point it at a TMDL
`.SemanticModel/definition` folder plus a C# script, and it loads the model
through the real Tabular Object Model (TOM) deserializer and runs the script
against the in-memory model.

```
TabularEditor.exe "<path>\finance-powerbi.SemanticModel\definition" -S validate.csx
```

Result on the fixed model (see next section):

```
MODEL_NAME: Model
TABLE_COUNT: 6
  TABLE: fact_capital_finance | Columns=7 | Measures=17
  TABLE: dim_account | Columns=5 | Measures=0
  TABLE: dim_period | Columns=3 | Measures=0
  TABLE: dim_costcenter | Columns=5 | Measures=0
  TABLE: dim_business_unit | Columns=2 | Measures=0
  TABLE: dim_scenario | Columns=3 | Measures=0
TOTAL_MEASURES: 17
RELATIONSHIP_COUNT: 6
ROLE_COUNT: 0
```

Exit code 0 - the model parses and loads cleanly under a real TOM engine, not
just "looks right as text." `ROLE_COUNT: 0` independently confirms RLS genuinely
hasn't been set up yet (matches the known project state).

## One real bug found and fixed in the model source

`finance-powerbi.SemanticModel/definition/relationships.tmdl` had this, on the
one inactive `dim_costcenter` -> `dim_business_unit` snowflake relationship:

```tmdl
/// Inactive to avoid an ambiguous path to dim_business_unit. The fact table
/// already joins dim_business_unit directly; this dim-to-dim link is kept for
/// reference and can be activated with USERELATIONSHIP if needed.
relationship 9e9ba4bf-2732-48eb-8ecb-89948d19b501
```

The `///` (triple-slash) block was clearly intended as an explanatory comment,
but per Microsoft's own TMDL spec
([tmdl-overview](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview)),
`///` is exclusively the syntax for the object's **Description** property - it
is not a general-purpose comment. `Relationship` objects in the Tabular Object
Model do not expose a `Description` property at all (only `Table`, `Column`,
`Measure`, etc. do), which is exactly why Tabular Editor's parser rejected it:
`Property 'description' is unknown and is not expected in the situation it
appears`. No other file in the model uses this pattern - it was an isolated
authoring slip, not a systemic issue.

**Fix applied** (converted to an `annotation`, which is a generic TOM
extensibility property valid on any object - the same mechanism `model.tmdl`
already uses for `PBI_QueryOrder`):

```tmdl
relationship 9e9ba4bf-2732-48eb-8ecb-89948d19b501
	isActive: false
	fromColumn: dim_costcenter.business_unit_key
	toColumn: dim_business_unit.business_unit_key
	annotation Note = "Inactive to avoid an ambiguous path to dim_business_unit. The fact table already joins dim_business_unit directly; this dim-to-dim link is kept for reference and can be activated with USERELATIONSHIP if needed."
```

After this change, Tabular Editor's load went from a hard parse error to exit
code 0. This edit was made on the Mac source of truth
(`pbip/finance-powerbi/finance-powerbi.SemanticModel/definition/relationships.tmdl`)
and is **uncommitted** - review it and commit when you're satisfied
(`git diff` in `career-ops` will show exactly this one hunk).

**Caveat on confirmation strength:** this was validated against Tabular
Editor's TMDL parser (Microsoft.AnalysisServices.Tabular, a real TOM-compliant
library), and the reasoning is grounded directly in Microsoft's published TMDL
spec, not guesswork. It was **not** additionally confirmed against Power BI
Desktop's own bundled engine - attempts to drive Desktop headlessly over SSH
hit the same session-isolation wall that blocks `winget` (a GUI app launched
from a non-interactive SSH session doesn't reliably persist or render), and
Desktop's bundled AS assembly doesn't expose a public `TmdlSerializer` type to
reflect into directly. In practice this will self-confirm in the first couple
of seconds the moment the `.pbip` is opened in Desktop - if it were still
wrong, Desktop would show a load error immediately on open.

## Opening the project

1. RDP or sit at the Lenovo console, open `C:\Users\Chetan Sarda\powerbi-portfolio\pbip\finance-powerbi\finance-powerbi.pbip` in Power BI Desktop (double-click, or File > Open).
2. **Transform data > Manage parameters > DataFolder** - point it at
   `C:\Users\Chetan Sarda\powerbi-portfolio\data\processed` (the CSVs are
   already staged there). This parameter ships with a placeholder
   (`C:\data\processed`); it must be updated before the first refresh or the
   load fails. This was already a documented step (see `expressions.tmdl`'s own
   comment) - the only thing new here is the CSVs already being on this machine
   at a known path.
3. Refresh. Verify the control total: a card on `SUM(fact_capital_finance[amount])` should read **8,618,616,154** (same check as the web path).

## Building the 4 report pages (manual, needs Chetan's hands)

The page-by-page visual map in `build-on-mac-online.md` (section A6/A7 - Deneb
spec assignments, native visuals, field mappings) applies identically here; the
underlying model and Deneb specs (`deneb/specs/*.json`, `deneb/theme.json`) are
unchanged. The only difference authoring in Desktop vs. the browser:

- Deneb custom visual: **Insert > Get more visuals > AppSource** inside
  Desktop, same as the web Service (Desktop doesn't have tenant-policy risk the
  web path warns about).
- No Track A/B split needed - Desktop handles Power Query and relationships
  natively, so just follow Track A's page/visual map directly against the
  six-table star schema already in this project (no flat-table fallback
  needed).

This part is inherently GUI work - placing 8 Deneb visuals + native visuals
across 4 pages, wiring field wells, applying the IBCS theme. Nothing here is
safely automatable by hand-authoring the report JSON (that was already ruled
out as too risky to validate blind).

## Row-level security

Not set up (`ROLE_COUNT: 0`, confirmed above). Two options when you get to it:

- **GUI**: Modeling > Manage roles in Desktop, same DAX filter as documented in
  `build-on-mac-online.md` A5 (`[business_unit_name] = USERPRINCIPALNAME()` or a
  static demo filter). Test with **View as**.
- **TMDL text** (not applied by this session - this is a note, not a change):
  a `role` object with a `tablePermission` filter is plain TMDL text (Microsoft's
  own docs show `role Role_Store1` / `modelPermission: read` /
  `tablePermission Store = ...` as a first-class syntax). It would be
  technically possible to hand-author an RLS role directly in
  `relationships.tmdl`'s sibling `roles/` folder the same way the relationship
  bug above was diagnosed and fixed. This session deliberately did not do that
  - adding a new role is a feature addition, not a validation-error fix, and
  it can't be tested (`View as role`) without Desktop's GUI anyway. Worth
  doing by hand in Desktop, or flag it back if you want it attempted via TMDL
  text next time.

## Publishing (hard-gated on Chetan, regardless of machine)

**Publish to Power BI Service still requires an interactive Microsoft/Fabric
login in a real browser session.** This cannot be scripted or done headlessly
from any machine - Mac, Lenovo, or otherwise. Once the report is built:
`Home > Publish` in Desktop, sign in with your account, pick a workspace, done.

---

## Footprint note (Lenovo "zero dev workloads" policy)

Per the one-off Power-BI-only authorization: only two things were installed -
**Power BI Desktop** (`winget`/Store install was blocked by the same
session-isolation issue noted above, so it was installed via Microsoft's
direct offline installer instead, silent/unattended, no Store account needed)
and **Tabular Editor 2 Community Edition** as a portable unzipped folder (no
installer, no registry footprint, fully removable by deleting
`C:\Users\Chetan Sarda\powerbi-portfolio\tools\TabularEditor\`). Nothing else
was touched - no other dev tooling, no package managers configured, no
changes to the Plex/*arr/Steam/qBittorrent surface.

## Cross-reference

- Browser/web-authoring path (still valid, still the no-Windows-needed
  default if you'd rather not touch the Lenovo): `build-on-mac-online.md`.
- DAX measures + the two documented column-name caveats: `measures.md`.
- Deneb specs + page assignments: `../deneb/README.md`.
- Page scope (the 4 pages): `../README.md`.
