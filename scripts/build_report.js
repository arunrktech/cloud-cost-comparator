#!/usr/bin/env node
// Build the comparison report (.docx).
// Usage: node build_report.js report.json costs.json workload.json diagrams_dir out.docx
// Requires the "docx" npm package (preinstalled in most Claude workspaces; else `npm install docx`).
const fs = require("fs");
const path = require("path");
const D = require("docx");
const { Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, BorderStyle, Footer, PageNumber } = D;

const [, , REPORT, COSTS, WORKLOAD, DIAG, OUT] = process.argv;
if (!OUT) { console.error("usage: node build_report.js report.json costs.json workload.json diagrams_dir out.docx"); process.exit(1); }
const R = JSON.parse(fs.readFileSync(REPORT, "utf8"));
const C = JSON.parse(fs.readFileSync(COSTS, "utf8"));
const W = JSON.parse(fs.readFileSync(WORKLOAD, "utf8"));
const CL = ["aws", "gcp", "azure"];
const NAME = { aws: "AWS", gcp: "Google Cloud", azure: "Azure" };
const FONT = "Calibri";
const usd = (v, d = 2) => (v == null ? "n/a" : "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
const unitp = (v) => (v == null ? "n/a" : "$" + (v < 0.01 ? Number(v).toPrecision(3) : Number(v).toLocaleString("en-US", { maximumFractionDigits: 4 })));
const pct = (v) => (v == null ? "" : (v === 0 ? "cheapest" : `+${v}%`));

const P = (t, o = {}) => new Paragraph({ children: [new TextRun({ text: t, ...(o.run || {}) })], spacing: { after: 140, line: 276 }, ...(o.para || {}) });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const Cap = (t) => new Paragraph({ children: [new TextRun({ text: t, bold: true, size: 20 })], spacing: { before: 120, after: 80 }, keepNext: true });
const FigCap = (t) => new Paragraph({ children: [new TextRun({ text: t, italics: true, size: 20 })], alignment: AlignmentType.CENTER, spacing: { after: 220 } });
const paras = (arr) => (arr || []).map((t) => P(t));
const b = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: b, bottom: b, left: b, right: b };
let tableNo = 0, figNo = 0;

function Tbl(caption, header, rows, widths, opts = {}) {
  const total = widths.reduce((a, x) => a + x, 0);
  const size = opts.size || 18;
  const cell = (t, i, head, shade) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { fill: "1F3864", type: ShadingType.CLEAR, color: "auto" } : shade ? { fill: shade, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ alignment: (!head && opts.right && opts.right.includes(i)) ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: String(t ?? ""), size, bold: head || (opts.boldLast && rows.length && t === rows[rows.length - 1][i] && false), color: head ? "FFFFFF" : undefined })] })] });
  tableNo += 1;
  return [Cap(`Table ${tableNo}. ${caption}`), new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: header.map((t, i) => cell(t, i, true)) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((t, i) => cell(t, i, false, opts.shadeRow && opts.shadeRow(r, ri))) }))] }),
    new Paragraph({ spacing: { after: 100 }, children: [] })];
}

function pngSize(file) {
  const buf = fs.readFileSync(file);
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20), buf };
}
function Img(file, caption) {
  const { w, h, buf } = pngSize(file);
  const width = 624, height = Math.round(624 * h / w);
  figNo += 1;
  return [new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120 },
    children: [new ImageRun({ type: "png", data: buf, transformation: { width, height }, altText: { title: caption, description: caption, name: path.basename(file) } })] }),
    FigCap(`Figure ${figNo}. ${caption}`)];
}

const body = [];
const V = C.variance;
// Title
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 100 }, children: [new TextRun({ text: R.title, bold: true, size: 36 })] }));
if (R.subtitle) body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: R.subtitle, size: 24 })] }));
body.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: [R.author, R.date].filter(Boolean).join(" | "), size: 20, color: "555555" })] }));

// 1 Executive summary
body.push(H1("1. Executive Summary"), ...paras(R.executive_summary));
const cheapOD = V.ondemand.cheapest, cheapCM = V.commit.cheapest;
body.push(...Tbl("Monthly cost by cloud (USD list prices)", ["Cloud", "On demand / month", "On demand / year", "vs cheapest", "With commitments / month", "vs cheapest"],
  CL.map((c) => [NAME[c], usd(V.ondemand.totals[c]), usd(V.ondemand.annual[c], 0), V.ondemand.vs_cheapest[c].usd === 0 ? "cheapest" : `${usd(V.ondemand.vs_cheapest[c].usd)} (${pct(V.ondemand.vs_cheapest[c].pct)})`,
    usd(V.commit.totals[c]), V.commit.vs_cheapest[c].usd === 0 ? "cheapest" : `${usd(V.commit.vs_cheapest[c].usd)} (${pct(V.commit.vs_cheapest[c].pct)})`]),
  [1300, 1600, 1600, 1700, 1560, 1600], { right: [1, 2, 4], shadeRow: (r) => (r[0] === NAME[cheapOD] ? "E8F3EA" : null) }));
if (C.top_variance_drivers && C.top_variance_drivers.length) {
  body.push(P("Largest contributors to the difference between clouds (on demand): " + C.top_variance_drivers.map((d) => `${d.label} (${usd(d.spread_usd)} spread, ${d.share_of_component_spread_pct}% of all component level differences)`).join("; ") + "."));
}
body.push(P(`Prices are USD list prices retrieved ${C.retrieved || ""} from official vendor APIs and pricing pages (${C.source_mix.api} API lines, ${C.source_mix.page} page lines). Taxes, support plans, negotiated discounts and free tiers are excluded.`, { run: { italics: true, size: 20 } }));

// Pros and cons infographic (optional file next to the diagrams)
const info = path.join(DIAG, "infographic.png");
if (fs.existsSync(info)) {
  body.push(H2("At a glance"));
  body.push(...Img(info, "Positives and negatives of each cloud for this project"));
}
if (R.pros_cons) {
  const pcRows = [];
  for (const c of CL) for (const k of ["pros", "cons"]) for (const p of ((R.pros_cons[c] || {})[k] || [])) pcRows.push([NAME[c], k === "pros" ? "Positive" : "Negative", p.text, p.evidence]);
  body.push(...Tbl("Positives and negatives with supporting evidence", ["Cloud", "Type", "Point", "Evidence"], pcRows, [1300, 1100, 3480, 3480],
    { shadeRow: (r) => (r[1] === "Negative" ? "FCEDEC" : "EAF5EC") }));
}

// 2 Scope and requirements
body.push(H1("2. Scope and Inputs"), ...paras(R.scope));
body.push(P("Inputs reviewed: " + (W.inputs || []).join("; ") + "."));
if (R.requirements && R.requirements.length) body.push(...Tbl("Requirements extracted from the inputs", ["ID", "Requirement", "Source"], R.requirements, [900, 5560, 2900]));

// 3 Assumptions
body.push(H1("3. Assumptions"));
body.push(P("Every sizing value is labelled stated (from the inputs or the client) or default (planning default used because the inputs were silent). Defaults should be confirmed before the estimate is used for budgeting."));
const arows = [];
for (const c of W.components) {
  for (const [k, v] of Object.entries(c.sizing || {})) arows.push([c.label || c.id, k.replace(/_/g, " "), String(v), (c.sizing_basis || {})[k] || "stated"]);
}
for (const a of W.assumptions || []) arows.push(["General", a.item, a.value, a.basis + (a.impact === "high" ? " (high impact)" : "")]);
body.push(...Tbl("Sizing and assumptions", ["Component", "Item", "Value", "Basis"], arows, [2600, 2200, 2700, 1860],
  { shadeRow: (r) => (String(r[3]).startsWith("default") ? "FFF6E0" : null) }));
body.push(P(`Regions: AWS ${W.regions.aws}, Google Cloud ${W.regions.gcp}, Azure ${W.regions.azure}. Hours per month: ${W.hours_per_month || 730}.`));

// 4 Service mapping
body.push(H1("4. Service Mapping"));
body.push(...Tbl("Equivalent services and SKUs", ["Component", "AWS", "Google Cloud", "Azure"],
  W.components.map((c) => [c.label || c.id, ...CL.map((k) => { const m = (c.mapping || {})[k] || {}; return `${m.service || ""}${m.sku ? ", " + m.sku : ""}`; })]),
  [2100, 2420, 2420, 2420]));
const reasons = W.components.filter((c) => CL.some((k) => ((c.mapping || {})[k] || {}).reason));
if (reasons.length) body.push(...Tbl("Mapping rationale", ["Component", "Why these SKUs are equivalent"],
  reasons.map((c) => [c.label || c.id, CL.map((k) => `${NAME[k]}: ${((c.mapping || {})[k] || {}).reason || ""}`).join(" | ")]), [2100, 7260]));

// 5 Architecture per cloud
body.push(H1("5. Architecture by Cloud"));
CL.forEach((k, i) => {
  body.push(H2(`5.${i + 1} ${NAME[k]}`));
  const f = path.join(DIAG, `${k}.png`);
  if (fs.existsSync(f)) body.push(...Img(f, `${W.project} on ${NAME[k]} (editable version: ${k}.drawio)`));
  body.push(...paras((R.architecture || {})[k]));
});

// 6 Cost breakdown
body.push(H1("6. Cost Breakdown by Cloud"));
const label = Object.fromEntries(W.components.map((c) => [c.id, c.label || c.id]));
CL.forEach((k, i) => {
  body.push(H2(`6.${i + 1} ${NAME[k]}`));
  const ls = C.lines.filter((l) => l.cloud === k);
  const rows = ls.map((l) => [label[l.component] || l.component, l.item, unitp(l.unit_price), Number(l.quantity).toLocaleString("en-US"), l.unit, usd(l.monthly_ondemand), usd(l.monthly_commit), l.source]);
  rows.push(["Total", "", "", "", "", usd(V.ondemand.totals[k]), usd(V.commit.totals[k]), ""]);
  body.push(...Tbl(`${NAME[k]} monthly line items`, ["Component", "Item", "Unit price", "Quantity", "Unit", "On demand", "Commitment", "Source"],
    rows, [1300, 2160, 900, 1000, 900, 1100, 1100, 900], { size: 16, right: [2, 3, 5, 6], shadeRow: (r) => (r[0] === "Total" ? "E7ECF5" : null) }));
  const notes = ls.filter((l) => l.note).map((l) => `${l.item}: ${l.note}${l.commit_label ? ` (commitment: ${l.commit_label})` : ""}`);
  if (notes.length) body.push(P("Quantity basis: " + notes.join("; ") + ".", { run: { size: 18 } }));
});

// 7 Variance
body.push(H1("7. Cost Variance"));
body.push(...Tbl("Cost by component (monthly, on demand)", ["Component", "AWS", "Google Cloud", "Azure", "Cheapest", "Spread"],
  C.components.map((r) => [r.label, usd(r.ondemand.aws), usd(r.ondemand.gcp), usd(r.ondemand.azure), NAME[r.ondemand_cheapest], usd(r.ondemand_spread_usd)])
    .concat([["Total", usd(V.ondemand.totals.aws), usd(V.ondemand.totals.gcp), usd(V.ondemand.totals.azure), NAME[cheapOD], usd(Math.max(...CL.map((c) => V.ondemand.totals[c])) - Math.min(...CL.map((c) => V.ondemand.totals[c])))]]),
  [2160, 1440, 1440, 1440, 1440, 1440], { right: [1, 2, 3, 5], shadeRow: (r) => (r[0] === "Total" ? "E7ECF5" : null) }));
body.push(...paras(R.variance_discussion));
if (C.unpriced && C.unpriced.length) {
  body.push(...Tbl("Items that could not be priced (excluded from totals)", ["Cloud", "Component", "Item", "Reason"],
    C.unpriced.map((u) => [NAME[u.cloud], label[u.component] || u.component, u.item, u.note]), [1300, 2000, 2600, 3460]));
}

// 8 Risks and next steps
body.push(H1("8. Risks, Exclusions and Next Steps"));
body.push(H2("Risks and exclusions"), ...paras(R.risks));
body.push(H2("How to tighten this estimate"), ...paras(R.next_steps));

// 9 Sources
body.push(H1("9. Price Sources"));
body.push(...Tbl("Official sources used for every price", ["Cloud", "Source", "Type", "Retrieved"],
  C.sources.map((s) => [NAME[s.cloud], s.url, s.source, s.retrieved]), [1300, 5760, 900, 1400], { size: 16 }));

const heading = (id, name, size, color, before, after, lvl) => ({ id, name, basedOn: "Normal", next: "Normal", quickFormat: true,
  run: { font: FONT, size, bold: true, color }, paragraph: { spacing: { before, after }, keepNext: true, outlineLevel: lvl } });
const doc = new Document({
  creator: R.author || "", title: R.title,
  styles: { default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [heading("Heading1", "Heading 1", 30, "1F3864", 300, 140, 0), heading("Heading2", "Heading 2", 25, "2E5597", 200, 100, 1)] },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18 })] })] }) },
    children: body }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("Wrote", OUT); });
