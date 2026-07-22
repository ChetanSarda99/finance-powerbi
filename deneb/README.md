# deneb/ - AI-assisted Deneb custom-visual specs

The hardest, drop-first-if-slipping part of this project is the **Deneb custom visuals** in Week 3
(see [`../notes.md`](../notes.md) - the Sankey is explicitly the highest-effort, lowest-floor item,
and the project risk table says "if Week 2 slips, drop Page 4 (Deneb Sankey)").

This folder de-risks that work using the AI-assisted **"describe a chart, get a Vega-Lite spec"**
workflow from the reference video
([*AI Can Now Build ANY Power BI Chart You Want*](https://youtu.be/mBdStGiyT9c)) and the
[SQLBI article on AI-assisted Power BI custom visuals](https://www.sqlbi.com/articles/using-ai-assistance-to-create-power-bi-custom-visuals/).

[Deneb](https://deneb-viz.github.io/) lets you drop a [Vega / Vega-Lite](https://vega.github.io/vega-lite/)
JSON spec into Power BI as a custom visual, reproducing the IBCS / Zebra-BI patterns this project
targets **without** the ~$30/user/mo Zebra BI licence (keeps the dashboard free + portable, per the
[`../README.md`](../README.md) decisions). Hand-writing that JSON is the slow part. So:

- **`ai-spec-prompt.md`** is the reusable engine - a prompt with the data contract + IBCS grammar
  pre-baked, so any chart you describe comes back already consistent with the rest of the dashboard.
  Includes the Sankey as a worked example (the one Power BI can't draw natively).
- **`specs/`** is a starter set of eight IBCS-compliant specs, ready to paste into Deneb -
  so the Week-3 visuals start from working baselines instead of a blank editor.

## What's here

```
deneb/
├── README.md                 # this file
├── ai-spec-prompt.md         # the reusable AI prompt (the video's technique, IBCS pre-baked)
├── theme.json                # IBCS scenario fills + variance colours as a Deneb/Vega config block
├── specs/                    # 8 ready-to-paste specs (7 Vega-Lite v5 + 1 Vega v5 Sankey)
│   ├── 01-variance-column-ac-pl-fc.vl.json     # Pages 1 & 3 - scenario columns (AC/PL/FC)
│   ├── 02-variance-table-inline-bars.vl.json   # Page 1     - variance table with inline bars
│   ├── 03-waterfall-bridge.vl.json             # Page 1     - bridge / waterfall to the total
│   ├── 04-trend-with-reference-line.vl.json    # Page 2     - Actual line over Plan reference
│   ├── 05-relative-variance-lollipop.vl.json   # Page 3     - % variance pins (green/red)
│   ├── 06-variance-heatmap.vl.json             # Page 3     - AC-vs-PL diverging heatmap
│   ├── 07-small-multiples-by-category.vl.json  # Page 4     - small multiples, shared scale
│   └── 08-cost-allocation-sankey.vg.json       # Page 4     - cost-allocation Sankey (Vega, NOT Vega-Lite)
└── sample-data/
    └── deneb-preview-rows.json   # 48 rows of realistic Vancouver capital data for standalone preview
```

Each spec maps to a dashboard page and the IBCS pattern table in
[`../ibcs-standards.md`](../ibcs-standards.md). Spec 08 is the Page-4 cost-flow **Sankey**: it is the
one chart Vega-Lite cannot express (Vega-Lite has no sankey mark), so it is written as a full **Vega
v5** spec (`.vg.json`, not `.vl.json`) and the spec editor in Deneb must be toggled from Vega-Lite to
**Vega** before pasting it. It is the flagship worked example in `ai-spec-prompt.md`, because
generating it is the whole point of the AI workflow.

### About the Sankey (spec 08)

- **Provider: Vega (not Vega-Lite).** The filename ends `.vg.json` to flag this. In Deneb, switch the
  spec editor provider to **Vega** before pasting.
- **Flow direction:** `service_category_1` (program, left) into `business_unit` (cost-centre owner,
  right). Link thickness = sum of `amount` filtered to `scenario === "AC"` (Actual capital dollars).
  This matches Page 4's "cost-center attribution" intent and the project's `dim_business_unit`
  dimension. Note: the `ai-spec-prompt.md` worked example uses `service_category_1` into
  `service_category_2` as its illustration; this shipped spec deliberately targets `business_unit`
  instead, because cost allocation to the owning business unit is the Page-4 story. Either source/
  target pair works with the same spec; only the two field names change.
- **IBCS restraint:** greyscale only - solid black nodes (`#000000`), grey links (`#BDBDBD`). No
  variance accent colours are used here; the Sankey shows composition, not variance.
- **New dataset field:** the Sankey needs `business_unit`, which the other 7 specs do not use. The
  sample-data file carries it on the Actual (`AC`) rows only (see Preview note below), so adding it
  does not change what the other 7 specs aggregate.

## How to use a spec

1. In Power BI Desktop, add the **Deneb** visual (AppSource, search "Deneb") to the page.
2. Drop the fields each spec lists in its `description` into the Deneb **Values** well - for most
   specs that's `service_category_1`, `year`, `scenario`, and the `amount` measure (or `Actual` /
   `Plan` measures from [`../docs/measures.md`](../docs/measures.md)). The Sankey (08) also needs
   `business_unit`.
3. Open the Deneb spec editor, leave the provider on **Vega-Lite** (or switch it to **Vega** for the
   `.vg.json` Sankey), paste the file's contents, apply.
4. Optionally paste `theme.json`'s `config` object into Deneb settings so colours stay consistent.

## Preview a spec without Power BI (works on this Mac - Power BI Desktop is Windows-only)

Each spec references `{"data": {"name": "dataset"}}` (the Deneb convention). To render it standalone:

1. Open the [Vega-Lite editor](https://vega.github.io/editor/?mode=vega-lite) (or the
   [Vega editor](https://vega.github.io/editor/) for the `.vg.json` Sankey).
2. Paste the spec, then replace `"data": {"name": "dataset"}` with
   `"data": {"values": <paste the array from sample-data/deneb-preview-rows.json>}`. For the Vega
   Sankey, the `dataset` entry is the first item in the `data` array; give it a `"values"` key there.
3. It renders immediately with the realistic Vancouver capital figures.

## Generate a new chart

Open [`ai-spec-prompt.md`](ai-spec-prompt.md), copy the prompt block, fill in the one-line chart
request, paste the model's JSON into `specs/` with the next number, and add it to the list above.
The pytest in [`../../../../tests/test_deneb_specs.py`](../../../../tests/test_deneb_specs.py)
validates every Vega-Lite (`*.vl.json`) spec is well-formed JSON, targets the Vega-Lite v5 schema,
binds the Deneb `dataset`, and carries a `description`.

## Validation method (last run 2026-06-01)

- **Structural:** the stdlib pytest `tests/test_deneb_specs.py` (38 checks) passes - every `.vl.json`
  spec is valid JSON, pins the Vega-Lite v5 schema, binds `{"name": "dataset"}`, has a description,
  and references only known fact-table or transform-derived fields. The `.vg.json` Sankey is a Vega
  (not Vega-Lite) spec, so the `*.vl.json` glob in that test correctly does not pick it up.
- **Rendering:** all 8 specs were compiled to SVG with `vl-convert-python` 1.9.0 (Rust-backed Vega /
  Vega-Lite compiler) against the sample data, inlining `dataset`. The 7 Vega-Lite specs each emit a
  valid SVG. The Vega Sankey was checked further: it renders 6 source nodes and 4 business-unit nodes
  (10 black node rects), 6 grey links with positive, amount-proportional stroke widths, and angled
  flows where source and target stack positions differ - i.e. real geometry, not an empty canvas.

## References

- Reference video - *AI Can Now Build ANY Power BI Chart You Want*: https://youtu.be/mBdStGiyT9c
- SQLBI - Using AI assistance to create Power BI custom visuals: https://www.sqlbi.com/articles/using-ai-assistance-to-create-power-bi-custom-visuals/
- Deneb docs: https://deneb-viz.github.io/
- Vega-Lite docs: https://vega.github.io/vega-lite/
- Vega docs (for the Sankey): https://vega.github.io/vega/
- IBCS grammar this folder follows: [`../ibcs-standards.md`](../ibcs-standards.md)
