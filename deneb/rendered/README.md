# deneb/rendered/ - the published charts

The five IBCS charts embedded on the Notion page, rendered standalone from the
specs in `../specs/` against the real processed data via
`shared/scripts/dataviz-render.py` (no Power BI needed):

```
~/.venvs/dataviz/bin/python ~/Projects/sync/shared/scripts/dataviz-render.py \
  --specs deneb/specs --data data/processed/finance_capital_flat.csv \
  --theme deneb/theme.json --out deneb/rendered --scale 3.0
```

| File | Section on the page |
|---|---|
| 01-variance-column-ac-pl-fc.png | The data |
| 07-small-multiples-by-category.png, 08-cost-allocation-sankey.png | The model and the IBCS grammar |
| 09-yoy-plan-vs-actual.png, 03-waterfall-bridge.png | Results so far |

Specs 02 / 04 / 05 / 06 are intentionally not rendered here: they need a single
fiscal year carrying both an Actual and a Plan, which the City of Vancouver source
does not have (Actual = 2023-25, Plan = 2026). The honest like-for-like is the
year-over-year 09 chart. Charts are also hosted publicly at
github.com/ChetanSarda99/portfolio-assets for the Notion image blocks.
