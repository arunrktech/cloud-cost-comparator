#!/usr/bin/env python3
"""Compute monthly costs per cloud, per component, and the variance between clouds.

Usage: python cost_model.py prices.json --out costs.json [--workload workload.json]

Validation (exit code 1 on failure, nothing written):
  * every priced line has unit_price, quantity, source in {api, page}, an https url on an
    official vendor host (see OFFICIAL_HOSTS) and a retrieved date
  * unpriced lines must have source 'unpriced' and a note
  * every component in workload.json (if given) has at least one line on every cloud, or an unpriced line

Fair comparison rule:
  A component is "comparable" only if it is fully priced on all three clouds (no unpriced line and
  at least one priced line on each). If any component is not comparable, no overall cheapest cloud
  is declared. Instead the result carries a like for like comparison over the comparable components,
  and the totals are flagged as incomplete.
"""
import argparse, json, sys
from urllib.parse import urlparse

CLOUDS = ["aws", "gcp", "azure"]
NAMES = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Azure"}

# Exact hostnames accepted as official pricing sources. Exact match only, so look alike hosts
# (notgoogle.com.evil.example), other products on the same parent domain (docs.google.com Sheets,
# www.amazon.com retail) and user content hosts (*.s3.amazonaws.com buckets) are rejected.
OFFICIAL_HOSTS = {
    # AWS
    "aws.amazon.com", "docs.aws.amazon.com", "calculator.aws",
    "pricing.us-east-1.amazonaws.com", "api.pricing.us-east-1.amazonaws.com",
    "api.pricing.eu-central-1.amazonaws.com", "api.pricing.ap-south-1.amazonaws.com",
    # Google Cloud
    "cloud.google.com", "docs.cloud.google.com", "cloudbilling.googleapis.com",
    # Microsoft Azure
    "azure.microsoft.com", "learn.microsoft.com", "prices.azure.com", "www.microsoft.com",
}


def official_url(u):
    """Return None if u is an https URL on an official host, else a reason string."""
    try:
        p = urlparse(str(u).strip())
    except ValueError:
        return "not a valid URL"
    if p.scheme != "https":
        return "must start with https://"
    host = (p.hostname or "").lower().rstrip(".")
    if p.username or p.password:
        return "must not contain credentials"
    if host not in OFFICIAL_HOSTS:
        return f"host '{host or '?'}' is not an official vendor pricing host"
    return None


def load_json(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"ERROR: {what} file not found: {path}")
    except IsADirectoryError:
        sys.exit(f"ERROR: {what} path is a folder, expected a JSON file: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: {what} file is not valid JSON ({path}, line {e.lineno}, column {e.colno}): {e.msg}")


def validate(prices, workload):
    errs = []
    if not isinstance(prices, dict) or not isinstance(prices.get("clouds"), dict):
        return ["prices.json must be an object with a 'clouds' object holding aws, gcp and azure lists"]
    for c in CLOUDS:
        for i, l in enumerate(prices["clouds"].get(c, [])):
            tag = f"{c}[{i}] {l.get('component')}/{l.get('item')}"
            if l.get("source") == "unpriced":
                if not l.get("note"):
                    errs.append(f"{tag}: unpriced line needs a note explaining why")
                if not l.get("component"):
                    errs.append(f"{tag}: missing component")
                continue
            for f in ("component", "item", "unit", "unit_price", "quantity", "url", "retrieved"):
                if l.get(f) in (None, ""):
                    errs.append(f"{tag}: missing {f}")
            if l.get("source") not in ("api", "page"):
                errs.append(f"{tag}: source must be api, page or unpriced")
            for f in ("unit_price", "quantity", "commit_unit_price"):
                v = l.get(f)
                if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0):
                    errs.append(f"{tag}: {f} must be a non negative number")
            if l.get("url"):
                why = official_url(l["url"])
                if why:
                    errs.append(f"{tag}: url {why}: {l['url']}")
    if workload:
        ids = [x["id"] for x in workload.get("components", [])]
        for c in CLOUDS:
            have = {l.get("component") for l in prices["clouds"].get(c, [])}
            for cid in ids:
                if cid not in have:
                    errs.append(f"{c}: component '{cid}' has no price line (add one or an unpriced line)")
    return errs


def compute(prices, workload=None):
    order = [x["id"] for x in workload["components"]] if workload else []
    labels = {x["id"]: x.get("label", x["id"]) for x in (workload or {}).get("components", [])}
    lines, unpriced, sources = [], [], {}
    comp = {}  # comp[id][cloud] = {"ondemand": x, "commit": y}
    unpriced_on = {}  # component -> set of clouds with an unpriced line
    for c in CLOUDS:
        for l in prices["clouds"].get(c, []):
            cid = l["component"]
            if cid not in order:
                order.append(cid)
            if l.get("source") == "unpriced":
                unpriced.append({"cloud": c, **l}); unpriced_on.setdefault(cid, set()).add(c); continue
            od = round(l["unit_price"] * l["quantity"], 4)
            cu = l.get("commit_unit_price")
            cm = round((cu if cu is not None else l["unit_price"]) * l["quantity"], 4)
            lines.append({"cloud": c, "component": cid, "item": l["item"], "unit": l["unit"], "unit_price": l["unit_price"],
                          "quantity": l["quantity"], "monthly_ondemand": od, "commit_unit_price": cu, "monthly_commit": cm,
                          "commit_label": l.get("commit_label", ""), "source": l["source"], "url": l["url"],
                          "retrieved": l["retrieved"], "note": l.get("note", "")})
            comp.setdefault(cid, {}).setdefault(c, {"ondemand": 0.0, "commit": 0.0})
            comp[cid][c]["ondemand"] += od; comp[cid][c]["commit"] += cm
            sources.setdefault(l["url"], {"cloud": c, "url": l["url"], "retrieved": l["retrieved"], "source": l["source"], "items": []})["items"].append(l["item"])

    # A component is comparable only when every cloud has priced lines and no cloud has an unpriced line.
    missing_on = {cid: {c for c in CLOUDS if c not in comp.get(cid, {})} for cid in order}
    gaps = {cid: sorted(unpriced_on.get(cid, set()) | missing_on[cid]) for cid in order}
    comparable = [cid for cid in order if not gaps[cid]]
    excluded = [cid for cid in order if gaps[cid]]
    complete = not excluded

    def sums(ids, scn):
        return {c: round(sum(comp.get(cid, {}).get(c, {}).get(scn, 0.0) for cid in ids), 2) for c in CLOUDS}

    def ranking(vals):
        cheapest = min(vals, key=vals.get)
        base = vals[cheapest]
        return cheapest, {c: {"usd": round(vals[c] - base, 2), "pct": round((vals[c] - base) / base * 100, 1) if base else None} for c in CLOUDS}

    def variance(scn):
        totals = sums(order, scn)
        out = {"scenario": scn, "complete": complete, "totals": totals, "annual": {c: round(totals[c] * 12, 2) for c in CLOUDS},
               "cheapest": None, "vs_cheapest": None,
               "incomplete_clouds": sorted({c for cid in excluded for c in gaps[cid]}, key=CLOUDS.index)}
        like = {"components": comparable, "excluded_components": excluded, "totals": None, "cheapest": None, "vs_cheapest": None}
        if comparable:
            lt = sums(comparable, scn)
            lc, lv = ranking(lt)
            like.update({"totals": lt, "cheapest": lc, "vs_cheapest": lv})
        out["like_for_like"] = like
        if complete:  # only a fully priced comparison may name an overall cheapest cloud
            out["cheapest"], out["vs_cheapest"] = ranking(totals)
        return out

    comp_rows = []
    for cid in order:
        row = {"component": cid, "label": labels.get(cid, cid), "comparable": not gaps[cid], "gaps_on": gaps[cid]}
        for scn in ("ondemand", "commit"):
            v = {c: round(comp.get(cid, {}).get(c, {}).get(scn, 0.0), 2) for c in CLOUDS}
            row[scn] = v
            if gaps[cid]:
                row[scn + "_cheapest"] = None; row[scn + "_spread_usd"] = None
            else:
                row[scn + "_cheapest"] = min(v, key=v.get)
                row[scn + "_spread_usd"] = round(max(v.values()) - min(v.values()), 2)
        comp_rows.append(row)
    ranked = [r for r in comp_rows if r["comparable"]]
    sum_spread = sum(r["ondemand_spread_usd"] for r in ranked)
    drivers = sorted(ranked, key=lambda r: -r["ondemand_spread_usd"])[:3]
    warnings = []
    if not complete:
        detail = "; ".join(labels.get(cid, cid) + " on " + ", ".join(NAMES[c] for c in gaps[cid]) for cid in excluded)
        warnings.append(
            "No overall cheapest cloud declared: %d component(s) are not priced on every cloud (%s). "
            "Totals are incomplete; the like for like comparison covers %d of %d components."
            % (len(excluded), detail, len(comparable), len(order)))
    return {"currency": prices.get("currency", "USD"), "retrieved": prices.get("retrieved"), "complete": complete, "warnings": warnings,
            "variance": {"ondemand": variance("ondemand"), "commit": variance("commit")},
            "components": comp_rows,
            "top_variance_drivers": [{"component": d["component"], "label": d["label"], "spread_usd": d["ondemand_spread_usd"],
                                      "share_of_component_spread_pct": round(d["ondemand_spread_usd"] / sum_spread * 100, 1) if sum_spread else None} for d in drivers],
            "lines": lines, "unpriced": unpriced, "sources": list(sources.values()),
            "source_mix": {s: sum(1 for l in lines if l["source"] == s) for s in ("api", "page")}}


def main():
    ap = argparse.ArgumentParser(description="Compute costs and variance from prices.json")
    ap.add_argument("prices"); ap.add_argument("--out", required=True); ap.add_argument("--workload")
    a = ap.parse_args()
    prices = load_json(a.prices, "prices")
    workload = load_json(a.workload, "workload") if a.workload else None
    errs = validate(prices, workload)
    if errs:
        print("VALIDATION FAILED:\n  " + "\n  ".join(errs)); sys.exit(1)
    res = compute(prices, workload)
    try:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
    except OSError as e:
        sys.exit(f"ERROR: cannot write output file {a.out}: {e.strerror}")
    for scn, label in (("ondemand", "Monthly on demand"), ("commit", "Monthly commitment")):
        v = res["variance"][scn]
        head = ", ".join(f"{NAMES[c]} ${v['totals'][c]:,.2f}" for c in CLOUDS)
        if v["cheapest"]:
            print(f"{label}: {head} | cheapest: {NAMES[v['cheapest']]}")
        else:
            lf = v["like_for_like"]
            tail = f" | like for like cheapest ({len(lf['components'])} components): {NAMES[lf['cheapest']]}" if lf["cheapest"] else " | no components priced on every cloud"
            print(f"{label} (INCOMPLETE): {head}{tail}")
    for w in res["warnings"]:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
