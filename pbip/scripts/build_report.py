#!/usr/bin/env python3
"""Generate the two PBIR report pages for finance-powerbi (native visuals only).

Usage:  python3 build_report.py <path to finance-powerbi.Report/definition>

Writes pages/budgetVsActual and pages/costCenterAttribution, rewrites pages.json,
and removes the old blank 'financeOverview' page. Field names match the TMDL model
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
GOOD = "#2E7D32"       # green, favourable variance (cost under plan / prior year)
BAD = "#C62828"        # red, unfavourable variance
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
    is_pct = "Pct" in measure
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


# ---------- Page 1: Budget vs Actual ----------
def page1():
    V = []
    V.append(textbox("pageTitle", 16, 2, 1000, 46, 100,
                     "Budget vs Actual - City of Vancouver capital spending (CAD)", "18pt", True))
    V.append(textbox("pageSubtitle", 16, 42, 1248, 30, 110,
                     "Actual black, Prior Year grey, Plan light. Green = under prior year, red = over. "
                     "The fiscal-year filter drives the Prior Year view; Plan is FY2026 only.",
                     "10pt", False, "#605E5C"))

    V.append(slicer("slicerFiscalYear", 16, 72, 200, 58, 200, col(PER_T, "label"), "Fiscal year", False, "FY2025"))
    V.append(slicer("slicerBusinessUnit", 228, 72, 330, 58, 210, col(BU_T, "business_unit_name"),
                    "Business unit", True))

    cw, gap, x0, y0, ch = 198, 12, 16, 138, 78
    cards = [
        ("cardActual", "Actual", "Actual (selected FY)"),
        ("cardPriorYear", "Prior Year", "Prior Year (FY before)"),
        ("cardVarPY", "Variance Abs (AC vs PY)", "Variance vs Prior Year"),
        ("cardVarPyPct", "Variance Pct (AC vs PY)", "Variance vs Prior Year %"),
        ("cardPlan", "Plan", "Plan (FY2026 budget)"),
        ("cardVarPL", "Variance Abs (AC vs PL)", "Actual FY23-25 vs Plan FY26"),
    ]
    for i, (n, m, t) in enumerate(cards):
        V.append(card(n, x0 + i * (cw + gap), y0, cw, ch, 300 + i, m, t))

    # clustered column: Actual / Prior Year / Plan by fiscal year
    colq = {
        "queryState": {
            "Category": {"projections": [proj(col(PER_T, "label"), True)]},
            "Y": {"projections": [proj(mea("Actual")), proj(mea("Prior Year")), proj(mea("Plan"))]},
        },
        **sort_def(col(PER_T, "label"), "Ascending"),
    }
    objs = {
        "dataPoint": [series_fill(BLACK, f"{FACT}.Actual"), series_fill(GREY, f"{FACT}.Prior Year"),
                      series_fill(LIGHT, f"{FACT}.Plan")],
        "labels": [{"properties": data_labels()}],
        **axes_clean("10D"), **legend(True),
    }
    V.append(visual("chartActualVsBudgetByYear", 16, 226, 470, 400, 400, "clusteredColumnChart", colq, objs,
                    container_objects("Actual vs Prior Year vs Plan by fiscal year (CAD M)")))

    def bu_bar(name, x, measure, title, z, colored=True):
        q = {
            "queryState": {
                "Category": {"projections": [proj(col(BU_T, "business_unit_name"), True)]},
                "Y": {"projections": [proj(mea(measure))]},
            },
            **sort_def(mea(measure), "Descending"),
        }
        md = f"{FACT}.{measure}"
        if colored:
            dp = [{"properties": {"fill": {"solid": {"color": variance_fill(measure, md)}}},
                   "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]
        else:
            dp = [{"properties": {"defaultColor": {"solid": {"color": s(NEUTRAL)}}}}]
        o = {
            "dataPoint": dp,
            "labels": [{"properties": data_labels("8D")}],
            **axes_clean("8D"), **legend(False),
        }
        return visual(name, x, 226, 385, 400, z, "clusteredBarChart", q, o, container_objects(title))

    V.append(bu_bar("chartVarianceByBuPlan", 498, "Variance Abs (AC vs PL)",
                    "Actual FY23-25 minus Plan FY26 by business unit (CAD M)", 410,
                    colored=False))
    V.append(bu_bar("chartVarianceByBuPY", 895, "Variance Abs (AC vs PY)",
                    "Change vs Prior Year by business unit (CAD M)", 420))

    V.append(textbox(
        "footnote", 16, 634, 1248, 78, 500,
        "Source: City of Vancouver open data (Open Government Licence). Actual is the approved budget for elapsed "
        "years FY2023-25, because the city publishes no spending ledger. Plan exists for FY2026 only and includes an "
        "annual budget line that Actual does not have, so Actual vs Plan compares 3 years with 1 year and is shown in "
        "neutral grey. The Prior Year view is the like-for-like comparison.",
        "9pt", False, "#605E5C"))

    interactions = [
        {"source": "slicerFiscalYear", "target": t, "type": "NoFilter"}
        for t in ("chartActualVsBudgetByYear", "chartVarianceByBuPlan", "cardPlan", "cardVarPL")
    ]
    return "budgetVsActual", "Budget vs Actual", V, interactions


# ---------- Page 2: Cost-center attribution ----------
def topn_filter():
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
                                                                             "Property": "Actual"}}}],
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
    V.append(textbox("pageTitle", 16, 2, 1000, 46, 100,
                     "Cost-center attribution - where the capital spend sits (CAD)", "18pt", True))
    V.append(textbox("pageSubtitle", 16, 42, 1248, 30, 110,
                     "Business unit > service category (cost center group) > service category detail. "
                     "Expand rows with the + icons. Actual black, Plan light.",
                     "10pt", False, "#605E5C"))
    V.append(slicer("slicerBusinessUnit", 16, 72, 330, 58, 200, col(BU_T, "business_unit_name"),
                    "Business unit", True))

    mq = {
        "queryState": {
            "Rows": {"projections": [proj(col(BU_T, "business_unit_name"), True, "Business unit / cost center"),
                                     proj(col(CC_T, "service_category_2"), True),
                                     proj(col(CC_T, "service_category_3"), True)]},
            "Values": {"projections": [proj(mea("Actual")), proj(mea("Plan")),
                                       proj(mea("Variance Abs (AC vs PL)"), None, "Actual minus Plan"),
                                       proj(mea("Variance Pct (AC vs PL)"), None, "Actual vs Plan %")]},
        },
    }
    mobj = {
        "columnHeaders": [{"properties": {"fontSize": lit("10D"), "bold": lit("true")}}],
        "rowHeaders": [{"properties": {"fontSize": lit("10D")}}],
        "grid": [{"properties": {"gridVertical": lit("false")}}],
    }
    V.append(visual("matrixBuCostCenter", 16, 138, 760, 506, 300, "pivotTable", mq, mobj,
                    container_objects("Business unit and cost center: Actual FY23-25, Plan FY26, variance (CAD)")))

    tq = {
        "queryState": {
            "Category": {"projections": [proj(col(CC_T, "service_category_2"), True)]},
            "Y": {"projections": [proj(mea("Actual")), proj(mea("Plan"))]},
        },
        **sort_def(mea("Actual"), "Descending"),
    }
    tobj = {
        "dataPoint": [series_fill(BLACK, f"{FACT}.Actual"), series_fill(LIGHT, f"{FACT}.Plan")],
        "labels": [{"properties": data_labels("8D")}],
        **axes_clean("9D"), **legend(True),
    }
    V.append(visual("chartTop10ServiceCategory", 792, 138, 472, 506, 400, "clusteredBarChart", tq, tobj,
                    container_objects("Top 10 service categories by Actual (CAD M)"), filters=[topn_filter()]))

    V.append(textbox(
        "footnote", 16, 650, 1248, 62, 500,
        "Cost center = a service category within a business unit (120 cost centers, 13 business units). Actual covers "
        "FY2023-25 (3 years) and Plan covers FY2026 (1 year), so the variance columns are not like-for-like and carry "
        "no red or green. The top 10 groups cost centers by service category across business units.",
        "9pt", False, "#605E5C"))
    return "costCenterAttribution", "Cost-center attribution", V, []


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main(defn):
    defn = Path(defn)
    pages_dir = defn / "pages"
    old = pages_dir / "financeOverview"
    if old.exists():
        shutil.rmtree(old)
    order = []
    for builder in (page1, page2):
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
    print("wrote pages:", order)


if __name__ == "__main__":
    main(sys.argv[1])
