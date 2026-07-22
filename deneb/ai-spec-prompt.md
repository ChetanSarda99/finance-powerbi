# AI spec-generation prompt (the reusable engine)

This is the **"describe a chart → get a Deneb-ready Vega-Lite spec"** workflow from the reference
video ([*AI Can Now Build ANY Power BI Chart You Want*](https://youtu.be/mBdStGiyT9c)) and the
[SQLBI write-up on AI-assisted custom visuals](https://www.sqlbi.com/articles/using-ai-assistance-to-create-power-bi-custom-visuals/).

The idea: instead of hand-writing Vega/Vega-Lite JSON for a [Deneb](https://deneb-viz.github.io/)
custom visual, you hand an LLM **(a)** the data contract, **(b)** the house visual grammar, and
**(c)** the chart you want in plain English — and it returns a spec you paste straight into Deneb.

The value of this file is that the **data contract + IBCS grammar are pre-baked**, so every spec the
AI returns is already consistent with the other visuals in this dashboard. Copy the block below into
Claude / ChatGPT, fill in the one-line ask at the bottom, paste the result into Deneb's spec editor.

---

## The prompt template — copy everything in this block

````text
You are generating a Vega-Lite v5 specification to paste into the Deneb custom visual for Power BI.

DATA CONTRACT
The Deneb dataset is named "dataset". Each row is one project x year x scenario from a star-schema
fact table (fact_capital_finance). Available fields:
  - service_category_1 : string  (top-level program, e.g. "Transportation", "Utilities")
  - service_category_2 : string  (sub-program)
  - service_category_3 : string  (area)
  - project_program_name : string
  - year : integer  (2023..2030)
  - scenario : string  enum {"AC" actual, "PL" plan/budget, "FC" forecast, "PY" prior year}
  - amount : number  (capital dollars, CAD)
Reference it in the spec as {"data": {"name": "dataset"}}. Do NOT inline data.

IBCS VISUAL GRAMMAR (mandatory — this is the house style; follow it exactly)
  - Scenario fills: AC = solid black #000000 · PY = solid grey #9E9E9E ·
    PL = outlined (white #FFFFFF fill + #000000 stroke) · FC = grey #BDBDBD.
  - Variance colour is SEMANTIC, by metric direction (not raw sign). For capital/cost lines,
    UNDER plan = good = green #2E7D32, OVER plan = bad = red #C62828, on-plan = grey #F5F5F5.
  - Title states the MESSAGE, not the topic ("Engineering ran 12% over plan", not "Costs by dept").
  - Max 3 colours + greyscale per chart. No rainbow legends.
  - No pie charts > 3 slices. No 3D. No dual Y-axes. Y starts at zero unless an explicit break.
  - Every trend chart carries a reference line (PY or PL) — never a lone single series.
  - Right-align numbers; currency format "$,.0s" on axes, "$,.0f" in tooltips, ".0%" for variance.

OUTPUT
Return ONLY the JSON spec (no prose), starting with the "$schema" key for vega-lite v5. Include a
"description" field summarising the chart and listing the dataset fields it requires. Compute any
variance with a {pivot} transform on scenario, then a {calculate} for the % and the good/bad colour.

CHART REQUEST
<<< one line: describe the chart you want >>>
````

---

## Worked example — the Sankey (the visual Power BI can't do natively)

The Page-4 cost-flow **Sankey** is the project's drop-first-if-slipping item (see `../notes.md`,
Week 3) precisely because it has no native Power BI visual and needs full **Vega** (not Vega-Lite).
That is exactly the chart this AI workflow is for. Fill the request line with:

> Build a Sankey diagram in Vega (full Vega v5, not Vega-Lite — Vega-Lite has no sankey). Source
> nodes = `service_category_1`, target nodes = `service_category_2`, link thickness = sum of
> `amount` filtered to `scenario === "AC"`. Colour nodes solid black (#000000) with grey links
> (#BDBDBD) per the IBCS grammar above. Left-to-right flow, node labels outside the nodes. Return
> only the Vega JSON referencing {"data": {"name": "dataset"}}.

Paste the Vega it returns into Deneb (toggle the spec editor from Vega-Lite to **Vega**), drop
`service_category_1`, `service_category_2`, and `amount` into the Values well, and iterate by
telling the model what looks off ("labels overflow", "links too thin") — the loop the video demos.

Keep a record: when a generated spec works, save it under `specs/` with the same naming convention
so the next refresh starts from a known-good baseline instead of re-prompting from scratch.

## Tips that make the loop converge faster

1. **Give the model a data sample, not just the schema.** Paste 5–10 rows from
   `sample-data/deneb-preview-rows.json` so it sees real category names and magnitudes.
2. **Preview outside Power BI first.** Swap `{"data": {"name": "dataset"}}` for
   `{"data": {"values": <paste sample rows>}}` and drop it into the
   [Vega editor](https://vega.github.io/editor/) — instant render, no Power BI Desktop needed.
3. **Iterate on one thing at a time** ("now colour the over-plan bars red") — smaller diffs, fewer
   regressions, exactly the tight loop the video shows.
4. **Re-assert the grammar** if the model drifts (rainbow colours, a dual axis) — paste the IBCS
   block again; models forget house rules across long threads.
