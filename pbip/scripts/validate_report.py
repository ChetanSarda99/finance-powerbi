#!/usr/bin/env python3
"""Offline validator for the finance-powerbi PBIR report.

Usage: validate_report.py <pbip dir (contains finance-powerbi.Report)> <schema clone root>
  schema clone root = a checkout of github.com/microsoft/json-schemas containing fabric/item/report

Checks: JSON parses; every file validates against the exact published schema version it
declares ($ref chain resolved locally); every Column/Measure reference exists in the TMDL
with the right kind; queryRef/nativeQueryRef consistency; pages.json matches folders;
visual names unique; interactions point at real visuals; visuals inside the page bounds;
embedded Conditional expressions validate against the semanticQuery schema.
Needs: pip install jsonschema referencing
"""
import json
import re
import sys
from pathlib import Path

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

BASE = "https://developer.microsoft.com/json-schemas/"
fails = []


def fail(msg):
    fails.append(msg)
    print("FAIL:", msg)


def parse_tmdl(model_dir):
    cols, meas = {}, {}
    for f in (model_dir / "tables").glob("*.tmdl"):
        text = f.read_text(encoding="utf-8")
        t = re.match(r"table\s+(.+)", text).group(1).strip().strip("'")
        cols[t] = set(re.findall(r"^\tcolumn\s+('?)(.+?)\1\s*$", text, re.M) and
                      [m[1] for m in re.findall(r"^\tcolumn\s+('?)(.+?)\1\s*$", text, re.M)])
        meas[t] = {m[1] for m in re.findall(r"^\tmeasure\s+('?)(.+?)\1\s*=", text, re.M)}
    return cols, meas


def make_registry(root):
    def retrieve(uri):
        if not uri.startswith(BASE):
            raise KeyError(uri)
        rel = uri[len(BASE):].replace("schema.embedded.json", "schema-embedded.json")
        p = root / rel
        return Resource.from_contents(json.loads(p.read_text(encoding="utf-8")), default_specification=DRAFT7)
    return Registry(retrieve=retrieve)


def validate(doc, schema_url, reg, label):
    rel = schema_url[len(BASE):]
    schema = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    v = jsonschema.Draft7Validator(schema, registry=reg)
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    for e in errs[:8]:
        fail(f"{label}: schema {'/'.join(map(str, e.path))}: {e.message[:200]}")
    return not errs


def walk(node, fn, path=()):
    fn(node, path)
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, fn, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, fn, path + (i,))


def main(pbip, root):
    global ROOT
    ROOT = Path(root)
    pbip = Path(pbip)
    rep = next(pbip.glob("*.Report")) / "definition"
    model = next(pbip.glob("*.SemanticModel")) / "definition"
    cols, meas = parse_tmdl(model)
    reg = make_registry(ROOT)
    print("model tables:", {t: (len(cols[t]), len(meas[t])) for t in cols})
    n_json = n_fields = 0

    files = sorted(rep.rglob("*.json"))
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception as ex:
            fail(f"{f}: JSON parse {ex}")
            continue
        n_json += 1
        sch = doc.get("$schema", "")
        if not sch.startswith(BASE):
            fail(f"{f}: missing/odd $schema")
            continue
        if not (ROOT / sch[len(BASE):]).exists():
            fail(f"{f}: schema version not published: {sch}")
            continue
        validate(doc, sch, reg, f.relative_to(rep).as_posix())

    # semantic checks
    page_dirs = sorted(p for p in (rep / "pages").iterdir() if p.is_dir())
    pages_meta = json.loads((rep / "pages" / "pages.json").read_text())
    if sorted(pages_meta["pageOrder"]) != sorted(p.name for p in page_dirs):
        fail("pages.json pageOrder != page folders")
    if pages_meta["activePageName"] not in pages_meta["pageOrder"]:
        fail("activePageName not in pageOrder")

    for pd in page_dirs:
        page = json.loads((pd / "page.json").read_text())
        if page["name"] != pd.name:
            fail(f"{pd.name}: page name != folder")
        names = []
        for vf in sorted((pd / "visuals").glob("*/visual.json")):
            v = json.loads(vf.read_text())
            names.append(v["name"])
            if v["name"] != vf.parent.name:
                fail(f"{vf}: name != folder")
            p = v["position"]
            if p["x"] + p["width"] > page["width"] or p["y"] + p["height"] > page["height"] or p["x"] < 0 or p["y"] < 0:
                fail(f"{pd.name}/{v['name']}: outside page bounds {p}")

            def chk(node, path):
                nonlocal n_fields
                if isinstance(node, dict) and ("Column" in node or "Measure" in node) and len(node) == 1:
                    kind = "Column" if "Column" in node else "Measure"
                    e = node[kind]
                    if not isinstance(e, dict) or "Expression" not in e:
                        return
                    sr = e["Expression"].get("SourceRef", {})
                    ent = sr.get("Entity")
                    if ent is None:
                        return  # alias reference (Source); resolved below via From
                    n_fields += 1
                    prop = e["Property"]
                    if ent not in cols:
                        fail(f"{pd.name}/{v['name']}: unknown table {ent}")
                    elif kind == "Column" and prop not in cols[ent]:
                        fail(f"{pd.name}/{v['name']}: {ent}[{prop}] is not a column")
                    elif kind == "Measure" and prop not in meas[ent]:
                        fail(f"{pd.name}/{v['name']}: {ent}[{prop}] is not a measure")
            walk(v, chk)

            # alias resolution: every From entity exists; alias col/measure exists
            def chk_from(node, path):
                nonlocal n_fields
                if isinstance(node, dict) and "From" in node and isinstance(node["From"], list):
                    alias = {}
                    for fr in node["From"]:
                        if "Entity" in fr:
                            alias[fr["Name"]] = fr["Entity"]
                            if fr["Entity"] not in cols:
                                fail(f"{pd.name}/{v['name']}: From entity {fr['Entity']} unknown")

                    def inner(n, p):
                        nonlocal n_fields
                        if isinstance(n, dict) and len(n) == 1 and ("Column" in n or "Measure" in n):
                            kind = "Column" if "Column" in n else "Measure"
                            e = n[kind]
                            src = e.get("Expression", {}).get("SourceRef", {}).get("Source") if isinstance(e, dict) else None
                            if src in alias:
                                n_fields += 1
                                tbl, prop = alias[src], e["Property"]
                                ok = prop in (cols[tbl] if kind == "Column" else meas[tbl])
                                if not ok:
                                    fail(f"{pd.name}/{v['name']}: alias {src}->{tbl}[{prop}] not a {kind}")
                    walk(node, inner)
            walk(v, chk_from)

            # queryRef consistency
            def chk_q(node, path):
                if isinstance(node, dict) and "queryRef" in node and "field" in node:
                    f = node["field"]
                    kind = "Column" if "Column" in f else "Measure"
                    e = f[kind]
                    exp = f"{e['Expression']['SourceRef']['Entity']}.{e['Property']}"
                    if node["queryRef"] != exp or node.get("nativeQueryRef") != e["Property"]:
                        fail(f"{pd.name}/{v['name']}: queryRef mismatch {node['queryRef']} vs {exp}")
            walk(v, chk_q)

            # selector metadata must equal a projected queryRef in the same visual
            qrefs = set()
            walk(v, lambda n, p: qrefs.add(n["queryRef"]) if isinstance(n, dict) and "queryRef" in n else None)

            def chk_sel(node, path):
                if isinstance(node, dict) and "metadata" in node and isinstance(node["metadata"], str):
                    if node["metadata"] and node["metadata"] not in qrefs:
                        fail(f"{pd.name}/{v['name']}: selector metadata {node['metadata']} not projected")
            walk(v, chk_sel)

            # Conditional expressions vs semanticQuery schema
            sq = json.loads((ROOT / "fabric/item/report/definition/semanticQuery/1.4.0/schema.json").read_text())
            def chk_cond(node, path):
                if isinstance(node, dict) and "Conditional" in node:
                    ref = {"$ref": BASE + "fabric/item/report/definition/semanticQuery/1.4.0/schema.json#/definitions/QueryExpressionContainer"}
                    errs = list(jsonschema.Draft7Validator(ref, registry=reg).iter_errors(node))
                    for e in errs[:3]:
                        fail(f"{pd.name}/{v['name']}: Conditional expr: {e.message[:160]}")
            walk(v.get("visual", {}), chk_cond)

        if len(names) != len(set(names)):
            fail(f"{pd.name}: duplicate visual names")
        for it in page.get("visualInteractions", []):
            for k in ("source", "target"):
                if it[k] not in names:
                    fail(f"{pd.name}: interaction {k} {it[k]} is not a visual")
        print(f"page {pd.name}: {len(names)} visuals")

    print(f"json files checked: {n_json}; field references checked: {n_fields}")
    print("RESULT:", "PASS" if not fails else f"{len(fails)} FAILURES")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
