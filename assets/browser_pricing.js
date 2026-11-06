// Browser pricing helpers for Claude in Chrome (paste into javascript_tool).
// Use when the shell cannot reach the pricing APIs (network allowlist) but the user's Chrome can.
// Each helper must run on a tab whose page is on the SAME origin as the URL it fetches:
//   azurePrices  -> first navigate the tab to https://prices.azure.com/api/retail/prices?$top=1
//   awsBulk      -> first navigate the tab to https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/region_index.json
//   gcpCatalog   -> first navigate the tab to https://cloudbilling.googleapis.com/v1/services?key=<KEY>&pageSize=1
//   pageGrep     -> run on a rendered official pricing page (wait for it to load)
// Verified working on 2026-11-05 for Azure Retail Prices and AWS bulk CSV (EC2 file of ~480 MB streams in about 8 s).

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- Azure Retail Prices API (no auth). Retries on HTTP 429. ----------
// Example filter: "serviceName eq 'Virtual Machines' and armRegionName eq 'eastus' and armSkuName eq 'Standard_D2s_v5' and priceType eq 'Consumption'"
// QUIRK: priceType 'Reservation' rows return the TOTAL price for the whole term (e.g. 519 for 1 Year) even though
// unitOfMeasure says '1 Hour'. Hourly equivalent = retailPrice / (8760 * years).
async function azurePrices(filter, maxPages = 5) {
  let url = "https://prices.azure.com/api/retail/prices?$filter=" + encodeURIComponent(filter);
  const items = [];
  for (let p = 0; url && p < maxPages; p++) {
    let d;
    for (let a = 0; a < 6; a++) {
      const r = await fetch(url);
      if (r.status === 429) { await sleep(5000 * (a + 1)); continue; }
      d = await r.json(); break;
    }
    if (!d) throw new Error("Azure API rate limited; wait a minute and retry");
    items.push(...d.Items); url = d.NextPageLink; await sleep(800);
  }
  return { source: "api", url: "https://prices.azure.com/api/retail/prices", filter,
    items: items.map((i) => ({ product: i.productName, sku: i.skuName, meter: i.meterName, price: i.retailPrice, unit: i.unitOfMeasure,
      type: i.type, term: i.reservationTerm || "", tierMin: i.tierMinimumUnits, region: i.armRegionName, effective: i.effectiveStartDate })) };
}

// ---------- AWS Price List bulk offer file (CSV, streamed, no auth) ----------
// match: exact column values, e.g. {"Instance Type":"m7i.large","Operating System":"Linux","Tenancy":"Shared","Pre Installed S/W":"NA","CapacityStatus":"Used"}
// Useful columns: TermType, PricePerUnit, Unit, LeaseContractLength, PurchaseOption, OfferingClass, PriceDescription,
// StartingRange, EndingRange, usageType, Volume Type, From Location, To Location.
// QUIRK: Reserved rows come in pairs (hourly rate + 'Upfront Fee'); for No Upfront use the hourly row only.
// Common service codes: AmazonEC2, AmazonRDS, AmazonS3, AWSDataTransfer, AWSELB, AmazonDynamoDB, AWSLambda, AmazonCloudFront, AmazonVPC.
function csvLine(l) { const o = []; let cur = "", q = false;
  for (let i = 0; i < l.length; i++) { const ch = l[i];
    if (q) { if (ch === '"') { if (l[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch; }
    else { if (ch === '"') q = true; else if (ch === ",") { o.push(cur); cur = ""; } else cur += ch; } }
  o.push(cur); return o; }
async function awsBulk(service, region, match, keep, limit = 100) {
  const url = `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/${service}/current/${region}/index.csv`;
  const r = await fetch(url); if (!r.ok) return { url, error: r.status };
  const rd = r.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "", H = null, published = null; const rows = []; const vals = Object.values(match);
  keep = keep || ["TermType", "PricePerUnit", "Unit", "LeaseContractLength", "PurchaseOption", "OfferingClass", "PriceDescription", "StartingRange", "EndingRange", "usageType"];
  while (true) { const { value, done } = await rd.read(); if (done) break; buf += value; let i;
    while ((i = buf.indexOf("\n")) >= 0) { const line = buf.slice(0, i).replace(/\r$/, ""); buf = buf.slice(i + 1);
      if (!H) { if (line.startsWith('"SKU"')) H = csvLine(line); else if (line.includes("Publication Date")) published = csvLine(line)[1]; continue; }
      if (!vals.every((v) => line.includes(v))) continue;
      const c = csvLine(line); const o = {}; H.forEach((h, j) => (o[h] = c[j]));
      if (Object.entries(match).every(([k, v]) => o[k] === v)) { rows.push(Object.fromEntries(keep.map((k) => [k, o[k]]))); if (rows.length >= limit) return { source: "api", url, published, rows }; } } }
  return { source: "api", url, published, rows };
}

// ---------- Google Cloud Billing Catalog API (needs a free API key) ----------
// service: display name, e.g. "Compute Engine", "Cloud Storage", "BigQuery". match: substring of SKU description.
async function gcpCatalog(key, service, match, region) {
  const base = "https://cloudbilling.googleapis.com/v1";
  const svcs = (await fetch(`${base}/services?pageSize=5000&key=${key}`).then((r) => r.json())).services;
  const s = svcs.find((x) => x.displayName.toLowerCase() === service.toLowerCase()); if (!s) return { error: "service not found" };
  const out = []; let tok = "";
  do { const d = await fetch(`${base}/${s.name}/skus?pageSize=5000&key=${key}${tok ? "&pageToken=" + tok : ""}`).then((r) => r.json());
    for (const k of d.skus || []) {
      if (match && !k.description.toLowerCase().includes(match.toLowerCase())) continue;
      if (region && !(k.serviceRegions || []).includes(region)) continue;
      for (const pi of k.pricingInfo || []) for (const tr of pi.pricingExpression.tieredRates || [])
        out.push({ sku: k.skuId, description: k.description, regions: k.serviceRegions, unit: pi.pricingExpression.usageUnitDescription,
          price: Number(tr.unitPrice.units || 0) + (tr.unitPrice.nanos || 0) / 1e9, tierStart: tr.startUsageAmount, usageType: k.category && k.category.usageType });
    }
    tok = d.nextPageToken; } while (tok);
  return { source: "api", url: `${base}/${s.name}/skus`, items: out };
}

// ---------- Rendered pricing page search (any official pricing page) ----------
// Waits for scripts to fill the tables, then returns text around each keyword. Check which region the page shows
// (Google Cloud pages default to Iowa us-central1; use the page's region selector to change it before reading).
async function pageGrep(keys, span = 400, waitMs = 2500) {
  await sleep(waitMs); const t = document.body.innerText; const res = {};
  for (const k of keys) { const hits = []; let i = -1; while ((i = t.indexOf(k, i + 1)) >= 0 && hits.length < 3) hits.push(t.slice(Math.max(0, i - 80), i + span)); res[k] = hits; }
  return { source: "page", url: location.href, res };
}
