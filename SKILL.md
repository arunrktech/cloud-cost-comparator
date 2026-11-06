---
name: cloud-cost-comparator
description: Compare AWS, Google Cloud and Azure for a project from an HLD, requirements doc or discovery notes; produce a Word report with cost estimates, variance, per cloud architecture diagrams and a pros/cons infographic.
---

# Cloud Cost Comparator

Turns project input (HLD, requirements document, discovery session notes, or a plain description) into a Word report that shows, for AWS, Google Cloud and Azure:

1. the equivalent architecture on each cloud, with a diagram (PNG in the report plus an editable draw.io file),
2. a priced bill of materials per cloud,
3. the cost variance between clouds (total and per component), on demand and with commitments,
4. a one page infographic of each cloud's positives and negatives for this project, in plain language,
5. every assumption and every price source, so a reader can check each number.

## Non negotiable rules

- **Never invent a price.** Every unit price comes from an official vendor pricing API or an official vendor pricing page (aws.amazon.com, amazonaws.com, cloud.google.com, googleapis.com, azure.microsoft.com, azure.com, learn.microsoft.com). Record `source` (`api` or `page`), the URL and the retrieval date on every price line. `cost_model.py` accepts only https URLs whose hostname exactly matches its official host list (for example aws.amazon.com, pricing.us-east-1.amazonaws.com, cloud.google.com, prices.azure.com, azure.microsoft.com, learn.microsoft.com); Google Sheets, look alike domains and storage buckets are rejected. If no official number can be read, mark the line `unpriced` and say so in the report. Never fill a price from memory, a third party site, or an estimate.
- **Never label a price with the wrong region.** If the only price available is for another region (Google pages default to Iowa), either switch the region or change `regions` in workload.json and say so.
- **Never invent sizing.** Sizing comes from the input, the user's answers, or `references/sizing_defaults.md`, labelled `stated` or `default`.
- **Pros and cons are evidence based.** Each point must point to evidence in the report (a cost table row, a variance driver, a mapping note, an unpriced item, or a cited vendor page). No generic marketing claims.
- **Like for like.** Compare equivalent capability (vCPU and memory class, redundancy, region tier). If no equivalent exists, say so.
- **List prices only.** USD, before tax, no negotiated discounts, no support plans, free tiers excluded except the egress allowances in `references/pricing_quirks.md`.
- **Arithmetic is done by `scripts/cost_model.py`, never in prose.**
- **No cheapest cloud on incomplete data.** If `costs.json` has `complete: false` (any component unpriced or missing on any cloud), do not call any cloud cheapest overall in the summary, narrative or pros and cons. Say which items are unpriced, quote the like for like comparison (`variance.<scenario>.like_for_like`) and recommend pricing the gaps first. The report and infographic show this warning automatically.

## Defaults (use unless the user says otherwise)

| Setting | Default |
|---|---|
| Currency | USD list price |
| Regions | AWS us-east-1, Google Cloud us-east1, Azure eastus |
| Hours per month | 730 |
| Scenarios | On demand, plus 1 year commitment (AWS Reserved standard no upfront, Google committed use, Azure 1 year reservation) where a published price exists |
| Report | Word .docx |
| Diagrams | PNG in report plus one .drawio per cloud |
| Infographic | PNG in report plus standalone file |

## Workflow

Create a task list with these steps. Work in `work/<project-slug>/`.

### 1. Read the input
Read every document (docx via pandoc, pdf via pdftotext, md or txt directly). Write `workload.json` per `references/workload_schema.md`: components, sizing, tiers, flows, and a `source` quote for each component.

### 2. Close sizing gaps
List missing sizing values that change cost materially (compute size and count, hours, storage GB, egress GB, request volumes, DB size and HA, LLM tokens, BI users). Ask **at most 5 questions** in one message (AskUserQuestion when available), most expensive unknowns first. Fill the rest from `references/sizing_defaults.md`, labelled `default`. If the user is not present, use defaults and say so.

### 3. Map services
Pick the service and SKU per cloud with `references/service_map.md`. Record `mapping.<cloud>` with `service`, `sku` and `reason`.

### 4. Get prices (use the first rung that works, per cloud)
Read `references/pricing_quirks.md` first. Then:
1. **Shell APIs.** `python scripts/fetch_prices.py probe`. For reachable APIs use `fetch_prices.py azure|aws|gcp` (see `--help`).
2. **Same APIs through the user's browser** (Claude in Chrome), which is not limited by the session's network allowlist. Load the chrome-browser skill, open a tab on the API's own origin, and run the helpers in `assets/browser_pricing.js` with javascript_tool: `azurePrices(filter)` (no auth), `awsBulk(service, region, match)` (no auth; streams the CSV offer file), `gcpCatalog(key, service, match, region)` (needs the user's free API key). Source type is `api`.
3. **Rendered official pricing page in the browser.** Open the page from `references/pricing_sources.md`, set the region on the page, and use `pageGrep([...])`. Source type is `page`.
4. **WebSearch then WebFetch.** WebFetch only opens links returned by a search, so search the vendor domain first. Many pricing pages render prices with scripts and come back empty; if so, stop.
5. **Unpriced.** Add the line with `source: "unpriced"` and a note. Tell the user which items need a manual check in the vendor calculator.

Write `prices.json` per the schema: one line per billable item, quantity computed from sizing with the calculation in `note`, tiers and free allowances applied per the quirks file, `commit_unit_price` where a commitment price exists.

### 5. Compute costs
`python scripts/cost_model.py work/<slug>/prices.json --workload work/<slug>/workload.json --out work/<slug>/costs.json`
It validates every line (source, URL on an official domain, numbers), totals each cloud, and computes variance against the cheapest cloud per component and in total for both scenarios. Fix failures; never bypass them.

### 6. Draw the architectures
`python scripts/diagrams.py work/<slug>/workload.json --out work/<slug>/diagrams` writes `aws|gcp|azure.png` and `.drawio`. Open each PNG and check it.

### 7. Write the narrative and the pros and cons
Write `report.json` per `references/report_outline.md`, including `pros_cons`: for each cloud 2 to 4 positives, 2 to 4 negatives and a `best_for` line. Write points for a non technical reader (short, no jargon, max about 70 characters), each with `evidence` that names the report table by its caption (for example "Cost by component table, internet egress" or "Azure line items note"), never by table number, because numbering is assigned at build time. Good sources of points: cost rank and variance, the biggest variance driver, commitment savings, services with no close equivalent, unpriced items, region or compliance fit, operational effort implied by the mapping (managed versus self run).

### 8. Check the narrative, then build the infographic and the report
The report opens with a verdict sentence generated from `costs.json` (cheapest cloud and gaps when complete; "no cloud is ranked" plus the like for like result when incomplete), so the headline always matches the numbers. Run the claim check first; `infographic.py` and `build_report.js` run the same check and refuse to build if it fails:
```
python scripts/narrative_check.py work/<slug>/report.json work/<slug>/costs.json
```
It blocks overall ranking claims ("cheapest overall", "lowest monthly total", "9% above Azure", "Azure is cheapest") when the comparison is incomplete, and winner claims that name the wrong cloud when it is complete. Per component claims ("cheapest storage per GB") are fine, and sentences that say "like for like" are allowed. If it fails, rewrite the flagged sentences; never edit the rules to get past it.
```
python scripts/infographic.py work/<slug>/report.json work/<slug>/costs.json --out work/<slug>/diagrams/infographic.png
node scripts/build_report.js work/<slug>/report.json work/<slug>/costs.json work/<slug>/workload.json work/<slug>/diagrams work/<slug>/<Project>_Cloud_Cost_Comparison.docx
```

### 9. Verify before delivering
- Render the docx to PDF (`soffice --headless --convert-to pdf`) and look at every page, including the infographic at full size.
- Spot check three price lines against their sources.
- Confirm report totals equal `costs.json` and every `default` appears in the assumptions table.
Deliver the .docx, `infographic.png`, the three `.drawio` files and `costs.json`. In the reply give the monthly totals per cloud, the cheapest option, the variance, the top variance driver and the two assumptions that most affect the result.

## Writing style
Plain, direct, practitioner voice. No dashes as separators. Present only what the numbers show; when a cloud is cheaper because of an assumption, name the assumption.
