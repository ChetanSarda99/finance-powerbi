# IBCS Standards Adherence

This project follows the IBCS (International Business Communication Standards) SUCCESS framework. Reference: https://www.ibcs.com/. Implementation in native Power BI + Deneb custom visuals (no Zebra BI commercial license required).

Last refreshed 2026-05-29.

---

## SUCCESS framework (the 7 IBCS principles)

| Letter | Principle | What it actually demands in this project |
|---|---|---|
| **S** | **SAY** | Every page has a one-line title that states the *message* (not the topic). E.g. "Q3 budget overshoot driven by Engineering Services" not "Q3 Budget Report". |
| **U** | **UNIFY** | Semantic notation - same thing always looks the same. Actual = solid black across every chart. Revenue is never green on one page + blue on another. |
| **C** | **CONDENSE** | Increase information density. Variance + actual + prior year in ONE chart, not three. No wasted whitespace + no decorative elements. |
| **C** | **CHECK** | Visual integrity - bars are length-proportional, axes start at zero unless explicitly broken, no 3D effects, no inverted axes. |
| **E** | **EXPRESS** | Right chart for the question. Variance = bar chart. Time series = line chart. Composition = stacked bar (rare) or treemap. NEVER pie charts for >3 segments. |
| **S** | **SIMPLIFY** | No gridlines unless they aid reading. No legend if the chart is self-explanatory. No 3D, no shadows, no gradients. |
| **S** | **STRUCTURE** | Hierarchical organization - summary -> detail. Every page has a fixed grid: title (top) -> message (subtitle) -> primary chart (left) -> variance/comment (right) -> footnote (bottom). |

## Visual notation grammar (this is the part Zebra-BI made famous)

### Scenario fills (the IBCS color/fill conventions)

| Scenario | Fill | Use case |
|---|---|---|
| **AC** (Actual) | Solid black | What actually happened |
| **PY** (Prior Year) | Solid grey | Comparison baseline |
| **PL** (Plan / Budget) | Outlined (white-filled, black border) | What was committed |
| **FC** (Forecast) | Hatched | What we now expect |

Every chart that compares scenarios uses these 4 fills consistently. No legend needed once the reader learns the grammar once.

### Variance bars (the IBCS variance pattern)

- **Green** = positive variance (better than reference)
- **Red** = negative variance (worse than reference)
- Color is determined by **direction relative to the metric meaning**, not raw sign. Example: cost line UNDER budget = green; revenue line UNDER budget = red.

### Variance chart types

| Type | Visual | When |
|---|---|---|
| **Absolute variance** | Solid bars (green / red) next to the actual bar | When you want to show dollars-off-budget |
| **Relative variance** | Pin / lollipop (line with dot) | When you want to show percent-off-budget |
| **Bridge / waterfall** | Stacked bars left-to-right | Decomposes opening -> changes -> closing |

### Time series

- Lines for trend, bars for periods
- Always include a reference line (PY OR PL) - never a single-series chart alone
- X-axis always time-ordered + labeled with consistent unit
- Y-axis starts at zero unless deliberately broken (and broken axes get a zig-zag marker)

## What IBCS bans (the anti-pattern list)

- ❌ Pie charts with more than 3 slices (humans can't compare angles)
- ❌ 3D bars / 3D pies of any kind
- ❌ Dual Y-axes on the same chart (misleads on scale comparison)
- ❌ Rainbow legends (use the 4 scenario fills + green/red variance only)
- ❌ Inconsistent color meaning across pages (revenue blue on page 1, revenue red on page 2)
- ❌ Decoration without information (background images, fancy fonts, drop shadows)
- ❌ Inverted axes to "make a bad metric look good"
- ❌ Title-as-topic (titles must say the MESSAGE: "Q3 cost overshoot" not "Q3 Costs")

## How this maps to the 4 dashboard pages

| Page | Primary IBCS pattern | Secondary patterns |
|---|---|---|
| 1. Income statement explorer | Variance table with inline bars (PY-AC-PL-FC columns per line item) | Bridge chart for net-income progression |
| 2. Cash flow + working capital | Trend line with PY reference line | Period-over-period heatmap (red/green 12mo grid) |
| 3. Budget vs Actual | Price-volume-mix waterfall | Variance heatmap |
| 4. Cost-center attribution | Small multiples (one mini-chart per cost center) | Deneb Sankey for cost flow |

Every page also has: title with message (not topic), dynamic comments layer, footer with data source + refresh date.

## Per-page checklist (use before shipping any page)

- [ ] Title states the MESSAGE, not the topic
- [ ] All scenario fills follow the AC/PY/PL/FC grammar
- [ ] All variance bars use green=better / red=worse semantic coloring
- [ ] No pie charts with >3 slices · no 3D · no dual Y-axes
- [ ] Y-axis starts at zero OR has explicit break marker
- [ ] Reference line on every trend chart (PY or PL)
- [ ] Max 3 colors + greyscale per page (no rainbow)
- [ ] Footnote with data source + refresh date

## IBCS template library (use as reference for the 4 dashboard pages)

The IBCS site publishes a curated template library at https://www.ibcs.com/resource_category/templates/ - each template is a worked example of a specific chart-table-dashboard pattern compliant with the SUCCESS framework. Use them as REFERENCE blueprints, not copy-paste artifacts (the official PPT / Excel templates are members-only; the publicly visible chart templates are images for design study).

### Template categories on the IBCS site

| IBCS resource | Pattern | Maps to our page |
|---|---|---|
| Chart template 12 (vertical waterfall for P&L) | P&L waterfall + absolute/relative variance tiers below the waterfall | Page 1 - Income statement (bridge chart for net-income progression) |
| Chart template (lollipop / pin for relative variance) | Pin diagram for percent variance | Page 3 - Budget vs Actual (relative variance pins) |
| Table template 04 (multi-scenario comparison table) | PY-AC-PL-FC columns per line item with inline bars + variance | Page 1 - Income statement explorer (variance-table-with-inline-bars) |
| Chart templates for small multiples | Repeating mini-chart per dimension member | Page 4 - Cost-center attribution (small multiples by department) |
| Chart templates for time-series + reference line | Trend chart with PY/PL overlay | Page 2 - Cash flow + working capital |

### Free public templates worth studying (NOT copy-paste, design reference only)

Zebra BI publishes free IBCS-compliant templates with attribution required:
- [Income Statement Dashboard for Power BI](https://zebrabi.com/template/income-statement-dashboard-in-power-bi/) - 3 scenario comparison variants (PY-AC-PL, PY-AC, AC-PL, PY-AC-PL-FC)
- [Annual Comparative Statement Power BI Template](https://zebrabi.com/template/annual-comparative-statement-power-bi-template/) - plus-minus + waterfall + pin charts
- [Income Statement Templates for Excel](https://zebrabi.com/template/income-statement-templates-excel/) - same patterns at lower fidelity
- [Inforiver "Build IBCS-Compliant Reports in Power BI" eBook](https://inforiver.com/ebooks/building-ibcs-compliant-reports-power-bi/) - step-by-step walkthrough

### How to use these in this project

1. **Week 2 design phase:** open IBCS chart template 12 + Zebra Income Statement Dashboard side-by-side; sketch the 4 page layouts on paper matching the SUCCESS structure (title says message, fixed grid per page).
2. **Week 3 build phase:** for each page, identify the 1-2 IBCS template patterns to reproduce. Build in native Power BI + Deneb, NEVER use a Zebra BI commercial visual (kills the free + portable goal).
3. **Week 4 polish phase:** run the per-page checklist (see this doc above) against each page. Common failures to watch: variance bars colored by raw sign instead of metric direction, missing reference line on trend charts, axis not starting at zero, more than 3 colors per page.
4. **Documentation:** every page screenshot in `docs/screenshots/` should be paired with a 1-line note citing which IBCS template pattern it's reproducing.

### Templates we won't use

- Pie charts (banned per IBCS even though some site templates use them historically - we follow the stricter "no pie > 3 slices" rule)
- Heatmaps with > 5 colors (the per-page color cap kills these; use 3-color sequential heatmaps only)
- 3D anything (banned)

## References

- IBCS official: https://www.ibcs.com/
- IBCS Standards (members only - the 150-page PDF): https://www.ibcs.com/standards/
- Zebra BI gallery (commercial implementation of IBCS in Power BI): https://zebrabi.com/gallery/
- Implementing IBCS in Power BI walkthrough: https://towardsdatascience.com/implementing-ibcs-rules-in-power-bi/
- Express to Impress (IBCS overview): https://medium.com/number-around-us/express-to-impress-leveraging-ibcs-standards-for-powerful-data-presentations-3c3a269f0ec0
- DataLabs IBCS resources: https://datalabsua.com/en/tag/ibcs/

## See also

- [`README.md`](README.md) - The why
- [`notes.md`](notes.md) - Week-by-week project plan with IBCS pattern per page
- [`data-sources.md`](data-sources.md) - City of Vancouver Open Data + dimensions table
