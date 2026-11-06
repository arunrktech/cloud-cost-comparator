#!/usr/bin/env python3
"""Compute monthly costs per cloud, per component, and the variance between clouds.

Usage: python cost_model.py prices.json --out costs.json [--workload workload.json]

Validation (exit code 1 on failure, nothing written):
  * every priced line has unit_price, quantity, source in {api, page}, url and retrieved date
  * unpriced lines must have source 'unpriced' and a note
  * every component in workload.json (if given) has at least one line on every cloud, or an unpriced line
"""
import argparse, json, sys

CLOUDS = ["aws", "gcp", "azure"]
NAMES = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Azure"}


def validate(prices, workload):
    errs = []
    for c in CLOUDS:
        for i, l in enumerate(prices["clouds"].get(c, [])):
            tag = f"{c}[{i}] {l.get('component')}/{l.get('item')}"
            if l.get("source") == "unpriced":
                if not l.get("note"):
                    errs.append(f"{tag}: unpriced line needs a note explaining why")
                continue
            for f in ("component", "item", "unit", "unit_price", "quantity", "url", "retrieved"):
                if l.get(f) in (None, ""):
                    errs.append(f"{tag}: missing {f}")
            if l.get("source") not in ("api", "page"):
                errs.append(f"{tag}: source must be api, page or unpriced")
            for f in ("unit_price", "quantity", "commit_unit_price"):
                v = l.get(f)
                if v is not None and (not isinstance(v, (int, float)) or v < 0):
                    errs.append(f"{tag}: {f} must be a non negative number")
            u = str(l.get("url", ""))
            if u and not any(d in u for d in ("amazon.com", "amazonaws.com", "google.com", "googleapis.com", "microsoft.com", "azure.com")):
                errs.append(f"{tag}: url is not an official vendor domain: {u}")
    if workload:
        ids = [x["id"] for x in workload.get("components", [])]
        for c in CLOUDS:
            have = {l.get("component") for l in prices["clouds"].get(c, [])}
            for cid in ids:
                if cid not in have:
                    errs.append(f"{c}: component '{cid}' has no price line (add one or an unpriced line)")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prices"); ap.add_argument("--out", required=True); ap.add_argument("--workload")
    a = ap.parse_args()
    prices = json.load(open(a.prices))
    workload = json.load(open(a.workload)) if a.workload else None
    errs = validate(prices, workload)
    if errs:
        print("VALIDATION FAILED:\n  " + "\n  ".join(errs)); sys.exit(1)

    order = [x["id"] for x in workload["components"]] if workload else []
    labels = {x["id"]: x.get("label", x["id"]) for x in (workload or {}).get("components", [])}
    lines, unpriced, sources = [], [], {}
    comp = {}  # comp[id][cloud] = {"ondemand":x,"commit":y}
    totals = {c: {"ondemand": 0.0, "commit": 0.0} for c in CLOUDS}
    for c in CLOUDS:
        for l in prices["clouds"].get(c, []):
            cid = l["component"]
            if cid not in order:
                order.append(cid)
            if l.get("source") == "unpriced":
                unpriced.append({"cloud": c, **l}); continue
            od = round(l["unit_price"] * l["quantity"], 4)
            cu = l.get("commit_unit_price")
            cm = round((cu if cu is not None else l["unit_price"]) * l["quantity"], 4)
            lines.append({"cloud": c, "component": cid, "item": l["item"], "unit": l["unit"], "unit_price": l["unit_price"],
                          "quantity": l["quantity"], "monthly_ondemand": od, "commit_unit_price": cu, "monthly_commit": cm,
                          "commit_label": l.get("commit_label", ""), "source": l["source"], "url": l["url"],
                          "retrieved": l["retrieved"], "note": l.get("note", "")})
            comp.setdefault(cid, {}).setdefault(c, {"ondemand": 0.0, "commit": 0.0})
            comp[cid][c]["ondemand"] += od; comp[cid][c]["commit"] += cm
            totals[c]["ondemand"] += od; totals[c]["commit"] += cm
            sources.setdefault(l["url"], {"cloud": c, "url": l["url"], "retrieved": l["retrieved"], "source": l["source"], "items": []})["items"].append(l["item"])

    def variance(scn):
        vals = {c: round(totals[c][scn], 2) for c in CLOUDS}
        cheapest = min(vals, key=vals.get)
        base = vals[cheapest]
        return {"scenario": scn, "cheapest": cheapest, "totals": vals,
                "vs_cheapest": {c: {"usd": round(vals[c] - base, 2), "pct": round((vals[c] - base) / base * 100, 1) if base else None} for c in CLOUDS},
                "annual": {c: round(vals[c] * 12, 2) for c in CLOUDS}}

    comp_rows = []
    for cid in order:
        row = {"component": cid, "label": labels.get(cid, cid)}
        for scn in ("ondemand", "commit"):
            v = {c: round(comp.get(cid, {}).get(c, {}).get(scn, 0.0), 2) for c in CLOUDS}
            lo = min(v, key=v.get)
            row[scn] = v; row[scn + "_cheapest"] = lo
            row[scn + "_spread_usd"] = round(max(v.values()) - min(v.values()), 2)
        comp_rows.append(row)
    sum_spread = sum(r["ondemand_spread_usd"] for r in comp_rows)
    drivers = sorted(comp_rows, key=lambda r: -r["ondemand_spread_usd"])[:3]
    res = {"currency": prices.get("currency", "USD"), "retrieved": prices.get("retrieved"),
           "variance": {"ondemand": variance("ondemand"), "commit": variance("commit")},
           "components": comp_rows,
           "top_variance_drivers": [{"component": d["component"], "label": d["label"], "spread_usd": d["ondemand_spread_usd"],
                                     "share_of_component_spread_pct": round(d["ondemand_spread_usd"] / sum_spread * 100, 1) if sum_spread else None} for d in drivers],
           "lines": lines, "unpriced": unpriced, "sources": list(sources.values()),
           "source_mix": {s: sum(1 for l in lines if l["source"] == s) for s in ("api", "page")}}
    json.dump(res, open(a.out, "w"), indent=1)
    v = res["variance"]["ondemand"]
    print("Monthly on demand:", ", ".join(f"{NAMES[c]} ${v['totals'][c]:,.2f}" for c in CLOUDS), "| cheapest:", NAMES[v["cheapest"]])
    vc = res["variance"]["commit"]
    print("Monthly commitment:", ", ".join(f"{NAMES[c]} ${vc['totals'][c]:,.2f}" for c in CLOUDS), "| cheapest:", NAMES[vc["cheapest"]])
    if unpriced:
        print(f"WARNING: {len(unpriced)} unpriced line(s) excluded from totals; list them in the report.")


if __name__ == "__main__":
    main()
