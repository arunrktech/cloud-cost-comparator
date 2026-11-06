#!/usr/bin/env python3
"""One page pros and cons infographic comparing AWS, Google Cloud and Azure for this project.

Usage: python infographic.py report.json costs.json --out infographic.png

Reads report.json["pros_cons"]:
  {"aws": {"pros": [{"text": "...", "evidence": "..."}], "cons": [...], "best_for": "..."}, "gcp": {...}, "azure": {...}}
Each point is a short plain-language phrase (max ~70 characters) and must carry `evidence`
(a table, figure or source in the report). The script refuses points without evidence.
Costs come from costs.json so the headline numbers always match the report.
Identity is never color alone: every column has the cloud name, every point a check or cross symbol.
"""
import argparse, json, sys, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

CL = ["aws", "gcp", "azure"]
NAME = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Microsoft Azure"}
EDGE = {"aws": "#c2630a", "gcp": "#1a63c7", "azure": "#0b7a8a"}
FILL = {"aws": "#fdf4ec", "gcp": "#eef4fd", "azure": "#ebf7f8"}
INK, MUTE, GOOD, BAD = "#111827", "#4b5563", "#1f7a3d", "#b42318"


def load_json(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"ERROR: {what} file not found: {path}")
    except IsADirectoryError:
        sys.exit(f"ERROR: {what} path is a folder, expected a JSON file: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: {what} file is not valid JSON ({path}, line {e.lineno}): {e.msg}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("report"); ap.add_argument("costs"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    R = load_json(a.report, "report"); C = load_json(a.costs, "costs"); pc = R.get("pros_cons", {})
    if "like_for_like" not in C.get("variance", {}).get("ondemand", {}):
        sys.exit(f"ERROR: costs file {a.costs} is from an older cost_model.py; re-run cost_model.py")
    errs = [f"{c} {k}: '{p.get('text')}' has no evidence" for c in CL for k in ("pros", "cons") for p in pc.get(c, {}).get(k, []) if not p.get("evidence")]
    errs += [f"{c}: needs at least 2 pros and 2 cons" for c in CL if len(pc.get(c, {}).get("pros", [])) < 2 or len(pc.get(c, {}).get("cons", [])) < 2]
    if errs:
        print("INFOGRAPHIC INPUT INVALID:\n  " + "\n  ".join(errs)); sys.exit(1)
    V = C["variance"]; od = V["ondemand"]["totals"]; cm = V["commit"]["totals"]; cheap = V["ondemand"]["cheapest"]
    esc = lambda t: str(t).replace("$", r"\$")  # matplotlib treats $...$ as math
    WR, LH, PG = 38, 0.3, 0.2  # wrap width, line height, gap after a point

    def col_height(d):
        h = 0.95 + 0.42
        h += sum(LH * len(textwrap.wrap(p["text"], WR)) + PG for p in d["pros"])
        h += 0.15 + 0.42
        h += sum(LH * len(textwrap.wrap(p["text"], WR)) + PG for p in d["cons"])
        if d.get("best_for"):
            h += 0.25 + 0.42 + LH * min(2, len(textwrap.wrap(d["best_for"], 42))) + 0.2
        return h + 0.25

    top = 3.75; colw = 3.95; gap = 0.25
    hcol = max(col_height(pc[c]) for c in CL)
    H = top + hcol + 0.9
    fig = plt.figure(figsize=(13, H), dpi=200); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 13); ax.set_ylim(H, 0); ax.axis("off")
    ax.text(0.5, 0.55, esc(R.get("infographic_title") or f"{R.get('title', 'Project')}: which cloud fits?"), fontsize=20, fontweight="bold", color=INK, va="top")
    sub = f"Monthly cost at list price (USD): on demand, with the 1 year commitment price in brackets. Prices retrieved {C.get('retrieved', '')}."
    if not cheap:
        lf = V["ondemand"]["like_for_like"]
        sub = ("INCOMPLETE: some items could not be priced, so these totals are partial and no cloud is ranked. "
               + (f"Like for like on {len(lf['components'])} components: {NAME[lf['cheapest']]} lowest." if lf.get("cheapest") else "No component is priced on every cloud."))
    ax.text(0.5, 1.15, esc(sub), fontsize=10.5, color=MUTE if cheap else BAD, va="top", fontweight="normal" if cheap else "bold")
    mx = max(od.values()) or 1
    for i, c in enumerate(CL):
        y = 1.75 + i * 0.62
        ax.text(0.5, y + 0.22, NAME[c], fontsize=12, fontweight="bold", color=INK, va="center")
        w = 6.6 * od[c] / mx
        partial = not cheap and c in V["ondemand"].get("incomplete_clouds", [])
        ax.add_patch(FancyBboxPatch((3.0, y), w, 0.44, boxstyle="round,pad=0,rounding_size=0.06",
                                    facecolor="white" if partial else EDGE[c], edgecolor=EDGE[c], lw=1.5, hatch="////" if partial else None))
        if cheap:
            tag = "   lowest" if c == cheap else f"   +{V['ondemand']['vs_cheapest'][c]['pct']}%"
        else:
            tag = "   incomplete: has unpriced items" if c in V["ondemand"].get("incomplete_clouds", []) else ""
        lab = f"${od[c]:,.0f} a month  (${cm[c]:,.0f} committed)" + tag
        ax.text(3.0 + w + 0.12, y + 0.22, esc(lab), fontsize=11, color=INK, va="center", fontweight="bold" if c == cheap else "normal")
    for i, c in enumerate(CL):
        x = 0.45 + i * (colw + gap); d = pc[c]
        ax.add_patch(FancyBboxPatch((x, top), colw, hcol, boxstyle="round,pad=0,rounding_size=0.12", facecolor=FILL[c], edgecolor=EDGE[c], lw=2))
        ax.add_patch(FancyBboxPatch((x, top), colw, 0.6, boxstyle="round,pad=0,rounding_size=0.12", facecolor=EDGE[c], edgecolor=EDGE[c]))
        ax.text(x + colw / 2, top + 0.3, NAME[c], fontsize=15, fontweight="bold", color="white", ha="center", va="center")
        y = top + 0.95
        for title, key, sym, colr in (("Positives", "pros", "\u2714", GOOD), ("Negatives", "cons", "\u2716", BAD)):
            ax.text(x + 0.25, y, title, fontsize=11.5, fontweight="bold", color=colr, va="top"); y += 0.42
            for p in d[key]:
                lines = textwrap.wrap(p["text"], WR)
                ax.text(x + 0.25, y, sym, fontsize=12, color=colr, va="top", fontweight="bold")
                ax.text(x + 0.62, y + 0.02, esc("\n".join(lines)), fontsize=10.5, color=INK, va="top", linespacing=1.25)
                y += LH * len(lines) + PG
            y += 0.15
        if d.get("best_for"):
            y += 0.1
            bl = textwrap.wrap(d["best_for"], 42)[:2]
            bh = 0.42 + LH * len(bl) + 0.1
            ax.add_patch(FancyBboxPatch((x + 0.2, y), colw - 0.4, bh, boxstyle="round,pad=0,rounding_size=0.08", facecolor="white", edgecolor=EDGE[c], lw=1.2))
            ax.text(x + 0.35, y + 0.12, "Best fit if:", fontsize=10, fontweight="bold", color=EDGE[c], va="top")
            ax.text(x + 0.35, y + 0.42, esc("\n".join(bl)), fontsize=9.8, color=INK, va="top", linespacing=1.25)
    ax.text(0.45, H - 0.55, "Every point is backed by a table, figure or source in the full report. List prices only; taxes, support and negotiated discounts excluded.",
            fontsize=9, color=MUTE, va="top")
    fig.savefig(a.out, facecolor="white"); print("Wrote", a.out)


if __name__ == "__main__":
    main()
