#!/usr/bin/env python3
"""Draw one architecture diagram per cloud from workload.json.

Usage: python diagrams.py workload.json --out diagrams/
Writes aws.png, gcp.png, azure.png and aws.drawio, gcp.drawio, azure.drawio.
Layout: columns by tier (users, edge, web, app, data, analytics, ops); flows drawn as arrows.
Each box shows the cloud service, the SKU and the component label. No vendor logos are used.
"""
import argparse, json, os, html
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

TIERS = ["users", "edge", "web", "app", "data", "analytics", "ops"]
TIER_TITLES = {"users": "Users", "edge": "Edge and network", "web": "Web", "app": "Application",
               "data": "Data", "analytics": "Analytics", "ops": "Operations"}
CLOUD = {"aws": ("AWS", "#c2630a", "#fdf4ec"), "gcp": ("Google Cloud", "#1a63c7", "#eef4fd"), "azure": ("Microsoft Azure", "#0b7a8a", "#ebf7f8")}
BW, BH, GX, GY = 2.3, 1.35, 0.75, 0.4  # box width/height, gaps (inches in plot units)


def wrap(s, n=30):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def layout(wl):
    comps = {c["id"]: c for c in wl["components"]}
    used_users = any("users" in (f["from"], f["to"]) for f in wl.get("flows", []))
    cols = {t: [] for t in TIERS}
    if used_users:
        cols["users"].append("users")
    for c in wl["components"]:
        cols[c.get("tier", "app") if c.get("tier", "app") in TIERS else "app"].append(c["id"])
    active = [t for t in TIERS if cols[t]]
    pos = {}
    maxrows = max(len(cols[t]) for t in active)
    for xi, t in enumerate(active):
        n = len(cols[t])
        offset = (maxrows - n) * (BH + GY) / 2
        for yi, cid in enumerate(cols[t]):
            pos[cid] = (xi * (BW + GX), offset + yi * (BH + GY))
    return comps, active, pos, maxrows


def node_text(cloud, cid, comps):
    if cid == "users":
        return "Users", ""
    c = comps[cid]
    m = c.get("mapping", {}).get(cloud, {})
    svc = m.get("service", "?")
    sku = m.get("sku", "")
    return svc, f"{sku}\n{c.get('label', cid)}".strip()


def png(cloud, wl, path):
    comps, active, pos, maxrows = layout(wl)
    name, edge, fill = CLOUD[cloud]
    W = len(active) * (BW + GX) - GX; H = maxrows * (BH + GY) - GY
    fig, ax = plt.subplots(figsize=(max(7, W + 0.6), H + 1.9), dpi=200)
    ax.set_xlim(-0.3, W + 0.3); ax.set_ylim(H + 0.55, -1.45); ax.axis("off")
    ax.text(-0.3, -1.3, f"{wl.get('project', 'Project')} on {name}", fontsize=15, fontweight="bold", color="#1f2937", va="top")
    ax.text(-0.3, -0.85, f"Region {wl.get('regions', {}).get(cloud, '')}. Boxes show service, SKU and component.", fontsize=10, color="#4b5563", va="top")
    for xi, t in enumerate(active):
        ax.text(xi * (BW + GX) + BW / 2, -0.1, TIER_TITLES[t], ha="center", fontsize=11, color="#374151", fontweight="bold")
    for f in wl.get("flows", []):
        if f["from"] in pos and f["to"] in pos:
            (x1, y1), (x2, y2) = pos[f["from"]], pos[f["to"]]
            if x2 > x1:
                a, b = (x1 + BW, y1 + 0.2 + BH / 2), (x2, y2 + 0.2 + BH / 2)
            elif x2 < x1:
                a, b = (x1, y1 + 0.2 + BH / 2), (x2 + BW, y2 + 0.2 + BH / 2)
            else:
                a, b = ((x1 + BW / 2, y1 + 0.2 + BH), (x2 + BW / 2, y2 + 0.2)) if y2 > y1 else ((x1 + BW / 2, y1 + 0.2), (x2 + BW / 2, y2 + 0.2 + BH))
            ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=11, color="#6b7280", lw=1.1,
                                         connectionstyle="arc3,rad=0.0" if x2 != x1 else "arc3,rad=0.25"))
            if f.get("label"):
                ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 0.2, f["label"], fontsize=9, color="#4b5563", ha="center",
                        bbox=dict(facecolor="white", edgecolor="none", pad=0.5))
    for cid, (x, y) in pos.items():
        y += 0.2
        svc, sub = node_text(cloud, cid, comps)
        users = cid == "users"
        ax.add_patch(FancyBboxPatch((x, y), BW, BH, boxstyle="round,pad=0,rounding_size=0.08",
                                    facecolor="#f3f4f6" if users else fill, edgecolor="#9ca3af" if users else edge, lw=1.4))
        svl = wrap(svc, 22)[:2]
        ax.text(x + 0.1, y + 0.1, "\n".join(svl), fontsize=11, fontweight="bold", color="#111827", va="top")
        ax.text(x + 0.1, y + 0.2 + 0.3 * len(svl), "\n".join(sum((wrap(s, 28) for s in sub.split("\n")), [])[:3]), fontsize=9.3, color="#374151", va="top")
    plt.savefig(path, bbox_inches="tight", facecolor="white"); plt.close(fig)


def drawio(cloud, wl, path):
    comps, active, pos, _ = layout(wl)
    name, edge, fill = CLOUD[cloud]
    S = 90  # pixels per unit
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    cells.append(f'<mxCell id="title" value="{html.escape(wl.get("project", "Project") + " on " + name)}" style="text;fontSize=18;fontStyle=1;align=left;" vertex="1" parent="1"><mxGeometry x="0" y="-70" width="700" height="30" as="geometry"/></mxCell>')
    for xi, t in enumerate(active):
        cells.append(f'<mxCell id="tier_{t}" value="{TIER_TITLES[t]}" style="text;fontStyle=1;align=center;" vertex="1" parent="1"><mxGeometry x="{xi*(BW+GX)*S}" y="-30" width="{BW*S}" height="24" as="geometry"/></mxCell>')
    for cid, (x, y) in pos.items():
        svc, sub = node_text(cloud, cid, comps)
        val = html.escape(f"<b>{html.escape(svc)}</b><br>{html.escape(sub).replace(chr(10), '<br>')}")
        st = ("rounded=1;whiteSpace=wrap;html=1;align=left;spacingLeft=8;fontSize=11;"
              + ("fillColor=#f3f4f6;strokeColor=#9ca3af;" if cid == "users" else f"fillColor={fill};strokeColor={edge};strokeWidth=2;"))
        cells.append(f'<mxCell id="n_{cid}" value="{val}" style="{st}" vertex="1" parent="1"><mxGeometry x="{x*S:.0f}" y="{y*S:.0f}" width="{BW*S:.0f}" height="{BH*S:.0f}" as="geometry"/></mxCell>')
    for i, f in enumerate(wl.get("flows", [])):
        if f["from"] in pos and f["to"] in pos:
            cells.append(f'<mxCell id="e{i}" value="{html.escape(f.get("label", ""))}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;strokeColor=#6b7280;fontSize=10;" edge="1" parent="1" source="n_{f["from"]}" target="n_{f["to"]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    xml = ('<mxfile host="cloud-cost-comparator"><diagram name="' + html.escape(name) + '"><mxGraphModel grid="1" gridSize="10" page="0"><root>'
           + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")
    open(path, "w", encoding="utf-8").write(xml)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("workload"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    wl = json.load(open(a.workload)); os.makedirs(a.out, exist_ok=True)
    missing = [(c["id"], k) for c in wl["components"] for k in CLOUD if k not in c.get("mapping", {})]
    if missing:
        raise SystemExit(f"Missing mapping for: {missing}")
    for k in CLOUD:
        png(k, wl, os.path.join(a.out, f"{k}.png")); drawio(k, wl, os.path.join(a.out, f"{k}.drawio"))
    print("Wrote", ", ".join(f"{k}.png/{k}.drawio" for k in CLOUD), "to", a.out)


if __name__ == "__main__":
    main()
