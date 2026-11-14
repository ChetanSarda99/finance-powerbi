#!/usr/bin/env python3
"""Generate the four PBIR report pages for finance-powerbi (native visuals only).

Usage:  python3 build_report.py <path to finance-powerbi.Report/definition> [--deneb]

--deneb adds two pages of Deneb custom visuals (specs from ../deneb/specs) and registers
the AppSource Deneb visual in report.json.

Writes four pages (budgetVsPriorYear, costCenterAttribution, expenditureOutlook,
changeBridge) and rewrites pages.json; the pages folder is replaced wholesale. Field names match the TMDL model
exactly (checked by validate_report.py). Plain hyphens only.
"""
import json
import shutil
import sys
from pathlib import Path

VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.10.0/schema.json"
PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"

FACT = "fact_capital_finance"
BU_T = "dim_business_unit"
CC_T = "dim_costcenter"
PER_T = "dim_period"

# IBCS palette (native approximation, see FALLBACK/WALKTHROUGH notes)
BLACK = "#000000"      # Actual
GREY = "#808080"       # Prior Year
LIGHT = "#D9D9D9"      # Plan / Budget (native visuals cannot draw an outlined fill)
NEUTRAL = "#595959"   # no good/bad colour where the comparison is not like-for-like
GOOD = "#2E7D32"       # green, lower than prior year (IBCS cost polarity)
BAD = "#C62828"        # red, higher than prior year
TXT = "#252423"


# ---------- helpers ----------
def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def s(text):
    return lit("'" + text.replace("'", "''") + "'")


def col(table, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def mea(prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": FACT}}, "Property": prop}}


def proj(field, active=None, name=None):
    kind = "Column" if "Column" in field else "Measure"
    e = field[kind]
    p = {
        "field": field,
        "queryRef": f"{e['Expression']['SourceRef']['Entity']}.{e['Property']}",
        "nativeQueryRef": e["Property"],
    }
    if active is not None:
        p["active"] = active
    if name:
        p["displayName"] = name
    return p


def qref(field):
    kind = "Column" if "Column" in field else "Measure"
    e = field[kind]
    return f"{e['Expression']['SourceRef']['Entity']}.{e['Property']}"


def sort_def(field, direction):
    return {"sortDefinition": {"sort": [{"field": field, "direction": direction}], "isDefaultSort": False}}


def container_objects(title=None, subtitle=None):
    o = {
        "background": [{"properties": {"show": lit("true")}}],
        "border": [{"properties": {"show": lit("false")}}],
    }
    if title:
        o["title"] = [{"properties": {
            "show": lit("true"),
            "text": s(title),
            "fontColor": {"solid": {"color": s(TXT)}},
            "fontSize": lit("11D"),
            "bold": lit("true"),
        }}]
    else:
        o["title"] = [{"properties": {"show": lit("false")}}]
    return o


def visual(name, x, y, w, h, z, vtype, query=None, objects=None, cobj=None, filters=None):
    v = {"visualType": vtype}
    if query:
        v["query"] = query
    if objects:
        v["objects"] = objects
    v["visualContainerObjects"] = cobj if cobj is not None else container_objects()
    v["drillFilterOtherVisuals"] = True
    d = {
        "$schema": VC,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": v,
    }
    if filters:
        d["filterConfig"] = {"filters": filters}
    return d


def textbox(name, x, y, w, h, z, text, size="10pt", bold=False, color=TXT):
    run = {"value": text, "textStyle": {"fontSize": size, "color": color}}
    if bold:
        run["textStyle"]["fontWeight"] = "bold"
    return visual(
        name, x, y, w, h, z, "textbox",
        objects={"general": [{"properties": {"paragraphs": [{"textRuns": [run]}]}}]},
        cobj={"background": [{"properties": {"show": lit("false")}}],
              "border": [{"properties": {"show": lit("false")}}],
              "title": [{"properties": {"show": lit("false")}}]},
    )


def slicer(name, x, y, w, h, z, field, title, multi, default=None):
    kind = "Column"
    tbl = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    objs = {
        "data": [{"properties": {"mode": s("Dropdown")}}],
        "header": [{"properties": {"show": lit("false")}}],
        "items": [{"properties": {"fontSize": lit("10D")}}],
    }
    if not multi:
        objs["selection"] = [{"properties": {"strictSingleSelect": lit("true")}}]
    else:
        objs["selection"] = [{"properties": {"selectAllCheckboxEnabled": lit("true")}}]
    if default:
        objs["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "p", "Entity": tbl, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "p"}}, "Property": prop}}],
                "Values": [[{"Literal": {"Value": "'" + default + "'"}}]],
            }}}],
        }}}}]
    q = {"queryState": {"Values": {"projections": [proj(field, True)]}}}
    return visual(name, x, y, w, h, z, "slicer", q, objs, container_objects(title))


def card(name, x, y, w, h, z, measure, title):
    q = {"queryState": {"Values": {"projections": [proj(mea(measure))]}}}
    is_pct = "Pct" in measure or "%" in measure
    labels = {"fontSize": lit("22D"), "color": {"solid": {"color": s(TXT)}}}
    if not is_pct:
        labels["labelDisplayUnits"] = lit("1000000D")
        labels["labelPrecision"] = lit("1L")
    objs = {
        "labels": [{"properties": labels}],
        "categoryLabels": [{"properties": {"show": lit("false")}}],
    }
    return visual(name, x, y, w, h, z, "card", q, objs, container_objects(title))


def variance_fill(measure, selector_metadata):
    """Rules-based colour on the measure: <0 green (under), >0 red (over). Cost polarity."""
    left = mea(measure)
    cases = [
        {"Condition": {"Comparison": {"ComparisonKind": 3, "Left": left, "Right": {"Literal": {"Value": "0D"}}}},
         "Value": {"Literal": {"Value": "'" + GOOD + "'"}}},
        {"Condition": {"Comparison": {"ComparisonKind": 1, "Left": left, "Right": {"Literal": {"Value": "0D"}}}},
         "Value": {"Literal": {"Value": "'" + BAD + "'"}}},
    ]
    return {"expr": {"Conditional": {"Cases": cases, "DefaultValue": {"Literal": {"Value": "'" + GREY + "'"}}}}}


def series_fill(color, metadata):
    return {"properties": {"fill": {"solid": {"color": s(color)}}}, "selector": {"metadata": metadata}}


def data_labels(size="9D"):
    return {"show": lit("true"), "labelDisplayUnits": lit("1000000D"), "labelPrecision": lit("0L"),
            "fontSize": lit(size), "color": {"solid": {"color": s(TXT)}}}


def axes_clean(cat_size="9D"):
    return {
        "categoryAxis": [{"properties": {"fontSize": lit(cat_size), "showAxisTitle": lit("false"),
                                         "maxMarginFactor": lit("40L")}}],
        "valueAxis": [{"properties": {"show": lit("false"), "showAxisTitle": lit("false"),
                                      "gridlineShow": lit("false")}}],
    }


def legend(show, pos="Bottom"):
    return {"legend": [{"properties": {"show": lit("true" if show else "false"), "position": s(pos),
                                       "fontSize": lit("9D")}}]}


# ---------- shared ----------
ACC_T = "dim_account"
FC_GREY = "#A6A6A6"    # Forecast (native visuals cannot draw a hatched fill)
FY_ALLOWED = ("FY2024", "FY2025", "FY2026")   # years that have a prior year to compare with
FY_DEFAULT = "FY2026"


def fy_filter():
    """Limit the fiscal-year slicer to years that have both a budget and a prior year."""
    return {
        "name": "fyWithPriorYear",
        "field": col(PER_T, "label"),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "p", "Entity": PER_T, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "p"}}, "Property": "label"}}],
                "Values": [[{"Literal": {"Value": "'" + y + "'"}}] for y in FY_ALLOWED],
            }}}],
        },
        "howCreated": "User",
    }


def fy_slicer(x=16, z=200):
    v = slicer("slicerFiscalYear", x, 72, 200, 58, z, col(PER_T, "label"), "Fiscal year", False, FY_DEFAULT)
    v["filterConfig"] = {"filters": [fy_filter()]}
    return v


def bar(name, x, y, w, h, z, cat, measures, colors, title, sort_measure, show_legend, filters=None,
        vtype="clusteredBarChart", size="8D"):
    q = {
        "queryState": {
            "Category": {"projections": [proj(cat, True)]},
            "Y": {"projections": [proj(mea(m)) for m in measures]},
        },
        **(sort_def(mea(sort_measure), "Descending") if sort_measure else sort_def(cat, "Ascending")),
    }
    o = {
        "dataPoint": [series_fill(c, f"{FACT}.{m}") for m, c in zip(measures, colors)],
        "labels": [{"properties": data_labels(size)}],
        **axes_clean("9D" if vtype != "clusteredBarChart" else size), **legend(show_legend),
    }
    return visual(name, x, y, w, h, z, vtype, q, o, container_objects(title), filters=filters)


# ---------- Page 1: Budget vs Prior Year ----------
def page1():
    V = []
    V.append(textbox("pageTitle", 16, 2, 1100, 46, 100,
                     "Plan vs Prior Year - City of Vancouver capital plan (CAD)", "18pt", True))
    V.append(textbox("pageSubtitle", 16, 42, 1248, 30, 110,
                     "Actual black, Prior Year grey, Plan light. Green = lower than prior year, red = higher. "
                     "Pick a fiscal year: FY2026 compares Plan with FY2025 Actual.",
                     "10pt", False, "#605E5C"))

    V.append(fy_slicer())
    V.append(slicer("slicerBusinessUnit", 228, 72, 330, 58, 210, col(BU_T, "business_unit_name"),
                    "Business unit", True))

    cw, gap, x0, y0, ch = 198, 12, 16, 138, 78
    cards = [
        ("cardSelected", "Actual or Plan", "Selected FY (Actual or Plan)"),
        ("cardPriorYear", "Prior Year", "Prior Year (FY before)"),
        ("cardVarPY", "Variance Abs (vs PY)", "Change vs Prior Year"),
        ("cardVarPyPct", "Variance Pct (vs PY)", "Change vs Prior Year %"),
        ("cardPlan", "Plan", "Plan FY2026 (capital plan)"),
        ("cardExpBudget", "Expenditure Budget", "Expenditure budget FY2026"),
    ]
    for i, (n, m, t) in enumerate(cards):
        V.append(card(n, x0 + i * (cw + gap), y0, cw, ch, 300 + i, m, t))

    V.append(bar("chartBudgetByYear", 16, 226, 470, 400, 400, col(PER_T, "label"),
                 ["Actual", "Prior Year", "Plan"], [BLACK, GREY, LIGHT],
                 "Actual, Prior Year and Plan by fiscal year (CAD M)", None, True,
                 vtype="clusteredColumnChart", size="9D"))

    V.append(bar("chartBudgetByBu", 498, 226, 385, 400, 410, col(BU_T, "business_unit_name"),
                 ["Actual or Plan", "Prior Year"], [BLACK, GREY],
                 "Selected FY vs Prior Year by business unit (CAD M)", "Actual or Plan", True))

    m = "Variance Abs (vs PY)"
    q = {
        "queryState": {
            "Category": {"projections": [proj(col(BU_T, "business_unit_name"), True)]},
            "Y": {"projections": [proj(mea(m))]},
        },
        **sort_def(mea(m), "Descending"),
    }
    o = {
        "dataPoint": [{"properties": {"fill": {"solid": {"color": variance_fill(m, f"{FACT}.{m}")}}},
                       "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
        "labels": [{"properties": data_labels("8D")}],
        **axes_clean("8D"), **legend(False),
    }
    V.append(visual("chartVarianceByBuPY", 895, 226, 385, 400, 420, "clusteredBarChart", q, o,
                    container_objects("Change vs Prior Year by business unit (CAD M)")))

    V.append(textbox(
        "footnote", 16, 634, 1248, 78, 500,
        "Source: City of Vancouver open data (Open Government Licence). Terms: Actual = the capital-plan allocation "
        "approved for a past year (FY2023-25); the city publishes no spending ledger. Plan = the same allocation for "
        "FY2026. Prior Year = Actual one year back. One line in every year, so years compare like-for-like. "
        "Expenditure budget = expected FY2026 spending on approved projects, from a different dataset; it is shown "
        "separately (see Expenditure outlook) and never added to Plan.",
        "9pt", False, "#605E5C"))

    interactions = [
        {"source": "slicerFiscalYear", "target": t, "type": "NoFilter"}
        for t in ("chartBudgetByYear", "cardPlan", "cardExpBudget")
    ]
    return "planVsPriorYear", "Plan vs Prior Year", V, interactions


# ---------- Page 2: Cost-center attribution ----------
def topn_filter(measure):
    return {
        "name": "top10ServiceCategory",
        "field": col(CC_T, "service_category_2"),
        "type": "TopN",
        "filter": {
            "Version": 2,
            "From": [
                {"Name": "subquery", "Expression": {"Subquery": {"Query": {
                    "Version": 2,
                    "From": [{"Name": "c", "Entity": CC_T, "Type": 0}, {"Name": "f", "Entity": FACT, "Type": 0}],
                    "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "service_category_2"},
                                "Name": "field"}],
                    "OrderBy": [{"Direction": 2, "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": "f"}},
                                                                             "Property": measure}}}],
                    "Top": 10}}}, "Type": 2},
                {"Name": "c", "Entity": CC_T, "Type": 0},
            ],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "service_category_2"}}],
                "Table": {"SourceRef": {"Source": "subquery"}}}}}],
        },
        "howCreated": "User",
    }


def page2():
    V = []
    V.append(textbox("pageTitle", 16, 2, 1100, 46, 100,
                     "Cost-center attribution - where the capital plan allocation sits (CAD)", "18pt", True))
    V.append(textbox("pageSubtitle", 16, 42, 1248, 30, 110,
                     "Business unit > service category (cost center group) > service category detail. "
                     "Expand rows with the + icons. Selected year black, Prior Year grey.",
                     "10pt", False, "#605E5C"))
    V.append(fy_slicer())
    V.append(slicer("slicerBusinessUnit", 228, 72, 330, 58, 210, col(BU_T, "business_unit_name"),
                    "Business unit", True))

    mq = {
        "queryState": {
            "Rows": {"projections": [proj(col(BU_T, "business_unit_name"), True, "Business unit / cost center"),
                                     proj(col(CC_T, "service_category_2"), True),
                                     proj(col(CC_T, "service_category_3"), True)]},
            "Values": {"projections": [proj(mea("Actual or Plan"), None, "Selected FY"),
                                       proj(mea("Prior Year")),
                                       proj(mea("Variance Abs (vs PY)"), None, "Change"),
                                       proj(mea("Variance Pct (vs PY)"), None, "Change %")]},
        },
    }
    mobj = {
        "columnHeaders": [{"properties": {"fontSize": lit("10D"), "bold": lit("true")}}],
        "rowHeaders": [{"properties": {"fontSize": lit("10D")}}],
        "grid": [{"properties": {"gridVertical": lit("false")}}],
    }
    V.append(visual("matrixBuCostCenter", 16, 138, 760, 506, 300, "pivotTable", mq, mobj,
                    container_objects("Business unit and cost center: selected FY, Prior Year and change (CAD)")))

    V.append(bar("chartTop10ServiceCategory", 792, 138, 472, 506, 400, col(CC_T, "service_category_2"),
                 ["Actual or Plan", "Prior Year"], [BLACK, GREY],
                 "Top 10 service categories, selected FY vs Prior Year (CAD M)", "Actual or Plan", True,
                 filters=[topn_filter("Actual or Plan")]))

    V.append(textbox(
        "footnote", 16, 650, 1248, 62, 500,
        "Cost center = a service category within a business unit (120 cost centers, 13 business units). Selected FY is "
        "the capital-plan allocation for the chosen year (Actual for FY2024-25, Plan for FY2026) and Prior Year is "
        "Actual for the year before. Change % is the change as a percent of Prior Year. The top 10 groups cost "
        "centers by service category across business units.",
        "9pt", False, "#605E5C"))
    return "costCenterAttribution", "Cost-center attribution", V, []


# ---------- Page 3: Expenditure outlook ----------
def page3():
    V = []
    V.append(textbox("pageTitle", 16, 2, 1100, 46, 100,
                     "Expenditure outlook - FY2027 forecast vs FY2026 expenditure budget (CAD)", "18pt", True))
    V.append(textbox("pageSubtitle", 16, 42, 1248, 30, 110,
                     "From the city's capital project budget dataset: cash the city expects to spend on projects already "
                     "approved. Expenditure budget (FY2026) light, Forecast (FY2027) mid grey.",
                     "10pt", False, "#605E5C"))
    V.append(slicer("slicerBusinessUnit", 16, 72, 330, 58, 200, col(BU_T, "business_unit_name"),
                    "Business unit", True))
    cw, gap, x0, y0, ch = 198, 12, 16, 138, 78
    cards = [
        ("cardExpBudget", "Expenditure Budget", "Expenditure budget FY2026"),
        ("cardForecast27", "Forecast FY2027", "Forecast FY2027"),
        ("cardExpChange", "Expenditure Change (FY27 vs FY26)", "Change FY27 vs FY26"),
        ("cardExpChangePct", "Expenditure Change % (FY27 vs FY26)", "Change FY27 vs FY26 %"),
    ]
    for i, (n, m, t) in enumerate(cards):
        V.append(card(n, x0 + i * (cw + gap), y0, cw, ch, 300 + i, m, t))

    ms, cs = ["Expenditure Budget", "Forecast FY2027"], [LIGHT, FC_GREY]
    V.append(bar("chartOutlookByBu", 16, 226, 760, 410, 410, col(BU_T, "business_unit_name"), ms, cs,
                 "By business unit: Expenditure budget FY2026 vs Forecast FY2027 (CAD M)",
                 "Expenditure Budget", True))

    m = "Expenditure Change (FY27 vs FY26)"
    q = {
        "queryState": {
            "Category": {"projections": [proj(col(BU_T, "business_unit_name"), True)]},
            "Y": {"projections": [proj(mea(m))]},
        },
        **sort_def(mea(m), "Descending"),
    }
    o = {
        "dataPoint": [{"properties": {"fill": {"solid": {"color": variance_fill(m, f"{FACT}.{m}")}}},
                       "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
        "labels": [{"properties": data_labels("8D")}],
        **axes_clean("8D"), **legend(False),
    }
    V.append(visual("chartOutlookChange", 792, 226, 472, 410, 420, "clusteredBarChart", q, o,
                    container_objects("Change FY27 vs FY26 by business unit (CAD M)")))
    V.append(textbox(
        "footnote", 16, 644, 1248, 68, 500,
        "Expenditure budget (FY2026) and Forecast (FY2027) are the city's own published figures for expected cash "
        "spending on approved projects; this report does not calculate a forecast. The forecast falls because it only "
        "covers projects already approved, so it is not a prediction of future budgets. Plan on the other pages is "
        "the capital-plan allocation, a different dataset; the two are never added together.",
        "9pt", False, "#605E5C"))
    return "expenditureOutlook", "Expenditure outlook", V, []


# ---------- Page 4: Change bridge ----------
def page4():
    V = []
    V.append(textbox("pageTitle", 16, 2, 1100, 46, 100,
                     "Change bridge - which business units move the plan vs Prior Year (CAD)", "18pt", True))
    V.append(textbox("pageSubtitle", 16, 42, 1248, 30, 110,
                     "Each bar is one business unit's change from the prior year; the last bar is the total change. "
                     "Red = higher than prior year, green = lower.",
                     "10pt", False, "#605E5C"))
    V.append(fy_slicer())
    cw, gap, x0, y0, ch = 198, 12, 228, 72, 62
    m = "Variance Abs (vs PY)"
    q = {
        "queryState": {
            "Category": {"projections": [proj(col(BU_T, "business_unit_name"), True)]},
            "Y": {"projections": [proj(mea(m))]},
        },
        **sort_def(mea(m), "Descending"),
    }
    o = {
        "sentimentColors": [{"properties": {
            "increaseFill": {"solid": {"color": s(BAD)}},
            "decreaseFill": {"solid": {"color": s(GOOD)}},
            "totalFill": {"solid": {"color": s(BLACK)}},
        }}],
        "labels": [{"properties": data_labels("9D")}],
        **axes_clean("9D"), **legend(False),
    }
    V.append(visual("chartBridge", 16, 138, 1248, 500, 400, "waterfallChart", q, o,
                    container_objects("Change vs Prior Year by business unit, with total (CAD M)")))
    V.append(textbox(
        "footnote", 16, 646, 1248, 62, 500,
        "Same measure as the green and red bars on page 1 (Actual or Plan, minus Prior Year), drawn as a bridge. "
        "With FY2026 selected it explains the move from FY2025 Actual to FY2026 Plan.",
        "9pt", False, "#605E5C"))
    return "changeBridge", "Change bridge", V, []


# ---------- Deneb pages (optional, --deneb) ----------
DENEB = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"   # certified AppSource visual
SPECS = Path(__file__).resolve().parent.parent.parent / "deneb" / "specs"
# Programs by FY2023-25 Actual, largest first (computed from data/processed on 2026-11-12)
BRIDGE_ORDER = ["Water, sewers & drainage", "Streets", "Housing", "Arts, culture & heritage", "Parks & public open spaces", "Public Safety", "Community facilities", "Waste collection, diversion & dispos", "Technology", "Civic facilities & equipment", "Emerging priorities, contingency & p", "Renewable energy", "Childcare"]
FACT_SCEN = {"Column": {"Expression": {"SourceRef": {"Entity": FACT}}, "Property": "scenario"}}


def deneb(name, x, y, w, h, z, spec_file, fields, overrides=None, title=None, bridge=False):
    """One Deneb visual. fields = [(model field, dataset name)]; the dataset name is what the spec reads."""
    spec = json.loads((SPECS / spec_file).read_text(encoding="utf-8"))
    spec.update(overrides or {})
    if bridge:   # Vega-Lite ignores a field sort on a shared layered x, so pin the order explicitly
        spec["encoding"]["x"]["sort"] = None
        spec["encoding"]["x"]["scale"] = {"domain": BRIDGE_ORDER}
    provider = "vega" if spec_file.endswith(".vg.json") else "vegaLite"
    q = {"queryState": {"dataset": {"projections": [proj(f, None, n) for f, n in fields]}}}
    objs = {"vega": [{"properties": {
        "provider": s(provider),
        "jsonSpec": s(json.dumps(spec, indent=2)),
        "jsonConfig": s("{}"),
        "renderMode": s("svg"),
        "enableTooltips": lit("true"),
        "enableContextMenu": lit("true"),
        "enableHighlight": lit("false"),
        "enableSelection": lit("false"),
    }}]}
    return visual(name, x, y, w, h, z, DENEB, q, objs, container_objects(title))


LONG = [(col(CC_T, "service_category_1"), "service_category_1"), (col(PER_T, "year"), "year"),
        (FACT_SCEN, "scenario"), (mea("Actual or Plan"), "amount")]
DENEB_NOTE = ("Deneb custom visuals (Vega-Lite), drawn from the same model and the same measure as page 1: Actual for "
              "FY2023-25 and Plan for FY2026, one line. Plan is outlined, the IBCS notation native visuals cannot draw.")


def page5():
    V = []
    V.append(textbox("pageTitle", 16, 2, 1100, 46, 100,
                     "IBCS views (Deneb) - Plan 2026 vs Actual 2025, and each program over time (CAD)", "18pt", True))
    V.append(deneb("denebYoY", 16, 56, 560, 590, 300, "09-yoy-plan-vs-actual.vl.json", LONG,
                   {"width": 330, "height": 440}))
    V.append(deneb("denebSmallMultiples", 592, 56, 672, 590, 310, "07-small-multiples-by-category.vl.json", LONG,
                   {"columns": 4}))
    V.append(textbox("footnote", 16, 654, 1248, 56, 500, DENEB_NOTE, "9pt", False, "#605E5C"))
    return "denebPlanVsActual", "IBCS views (Deneb)", V, []


def page6():
    V = []
    V.append(textbox("pageTitle", 16, 2, 1100, 46, 100,
                     "Cost allocation (Deneb) - how FY2023-25 Actual builds up and flows (CAD)",
                     "18pt", True))
    V.append(deneb("denebBridge", 16, 56, 640, 590, 300, "03-waterfall-bridge.vl.json", LONG,
                   {"width": 520, "height": 360}, bridge=True))
    sank = [(col(CC_T, "service_category_1"), "service_category_1"),
            (col(CC_T, "service_category_2"), "service_category_2"),
            (FACT_SCEN, "scenario"), (mea("Actual or Plan"), "amount")]
    V.append(deneb("denebSankey", 672, 56, 592, 590, 310, "08-cost-allocation-sankey.vg.json", sank,
                   {"width": 240, "height": 430}))
    V.append(textbox("footnote", 16, 654, 1248, 56, 500,
                     "Left: each program's share of FY2023-25 Actual, as a running total. Right: a Sankey "
                     "(Vega, since Vega-Lite has no Sankey mark) from program to sub-program. Both use scenario AC only.",
                     "9pt", False, "#605E5C"))
    return "denebAllocation", "Cost allocation (Deneb)", V, []


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main(defn, with_deneb=False):
    defn = Path(defn)
    pages_dir = defn / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)   # pages are fully generated; stale page folders must not survive
    order = []
    builders = (page1, page2, page3, page4) + ((page5, page6) if with_deneb else ())
    for builder in builders:
        pid, display, visuals, interactions = builder()
        pdir = pages_dir / pid
        if pdir.exists():
            shutil.rmtree(pdir)
        page = {"$schema": PAGE, "name": pid, "displayName": display, "displayOption": "FitToPage",
                "height": 720, "width": 1280}
        if interactions:
            page["visualInteractions"] = interactions
        write_json(pdir / "page.json", page)
        for v in visuals:
            write_json(pdir / "visuals" / v["name"] / "visual.json", v)
        order.append(pid)
    write_json(pages_dir / "pages.json", {"$schema": PAGES, "pageOrder": order, "activePageName": order[0]})
    rj = defn / "report.json"
    rep = json.loads(rj.read_text(encoding="utf-8-sig"))
    if with_deneb:
        rep["publicCustomVisuals"] = [DENEB]
    else:
        rep.pop("publicCustomVisuals", None)
    write_json(rj, rep)
    print("wrote pages:", order)


if __name__ == "__main__":
    main(sys.argv[1], "--deneb" in sys.argv)
