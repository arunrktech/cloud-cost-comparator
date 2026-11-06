#!/usr/bin/env python3
"""Fetch list prices from the official AWS, Azure and Google Cloud pricing APIs.

Subcommands
  probe                         Check which pricing APIs are reachable from this session.
  azure  --filter "<OData>"     Azure Retail Prices API (no auth). Example filter:
                                "serviceName eq 'Virtual Machines' and armRegionName eq 'eastus' and armSkuName eq 'Standard_D2s_v5' and priceType eq 'Consumption'"
  aws    --service AmazonEC2 --region us-east-1 [--filter Field=Value ...]
                                Uses boto3 GetProducts when AWS credentials exist; otherwise streams the public
                                bulk offer CSV for the region and keeps rows whose columns match --filter exactly
                                (bulk column names, e.g. "Instance Type=m7i.large" "Operating System=Linux").
  gcp    --service "Compute Engine" [--match "N2 Instance Core"] [--region us-east1]
                                Cloud Billing Catalog API; needs env GOOGLE_PRICING_API_KEY.

All subcommands print JSON: {"source": "api", "url": ..., "retrieved": ..., "items": [...]}.
Each item has sku, description, region, unit, unit_price, currency and raw fields useful for checking.
Exit code 2 means the API is unreachable or not configured: fall back to the official pricing page.
"""
import argparse, datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

TODAY = datetime.date.today().isoformat()
TIMEOUT = 30
AZURE = "https://prices.azure.com/api/retail/prices"
AWS_BULK = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws"
GCP = "https://cloudbilling.googleapis.com/v1"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cloud-cost-comparator/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def out(payload, code=0):
    print(json.dumps(payload, indent=1))
    sys.exit(code)


def fail(api, err):
    out({"api": api, "reachable": False, "error": str(err),
         "next": "Call the same API from the browser with assets/browser_pricing.js (Claude in Chrome); else read the rendered official pricing page; else mark the line unpriced"}, 2)


# ---------- probe ----------
def probe(_):
    checks = {
        "azure_retail_prices": AZURE + "?$top=1",
        "aws_bulk_offer_index": AWS_BULK + "/index.json",
        "gcp_billing_catalog": GCP + "/services?pageSize=1" + (f"&key={os.environ['GOOGLE_PRICING_API_KEY']}" if os.environ.get("GOOGLE_PRICING_API_KEY") else ""),
    }
    res = {}
    for name, url in checks.items():
        try:
            req = urllib.request.Request(url, method="GET", headers={"User-Agent": "cloud-cost-comparator/1.0", "Range": "bytes=0-1023"})
            with urllib.request.urlopen(req, timeout=15) as r:
                res[name] = {"reachable": True, "status": r.status}
        except urllib.error.HTTPError as e:
            note = "reachable but needs GOOGLE_PRICING_API_KEY" if name.startswith("gcp") and e.code in (400, 401, 403) else ""
            res[name] = {"reachable": e.code < 500 and bool(note), "status": e.code, "note": note or str(e)}
        except Exception as e:  # blocked by proxy, DNS, timeout
            res[name] = {"reachable": False, "error": str(e)}
    try:
        import boto3  # noqa: F401
        import botocore.session
        creds = botocore.session.get_session().get_credentials()
        res["aws_get_products"] = {"boto3": True, "credentials": bool(creds)}
    except Exception:
        res["aws_get_products"] = {"boto3": False, "credentials": False}
    out({"retrieved": TODAY, "apis": res,
         "advice": "Unreachable APIs: fall back to pricing pages via WebFetch (references/pricing_sources.md)."})


# ---------- azure ----------
def azure(a):
    url = AZURE + "?" + urllib.parse.urlencode({"$filter": a.filter, "currencyCode": a.currency})
    items, next_url, pages = [], url, 0
    try:
        while next_url and pages < a.max_pages:
            data = json.loads(get(next_url))
            for i in data.get("Items", []):
                items.append({"sku": i.get("armSkuName") or i.get("skuName"), "description": f"{i.get('productName')} | {i.get('skuName')} | {i.get('meterName')}",
                              "region": i.get("armRegionName"), "unit": i.get("unitOfMeasure"), "unit_price": i.get("retailPrice"),
                              "currency": i.get("currencyCode"), "price_type": i.get("type"), "reservation_term": i.get("reservationTerm"),
                              "tier_min_units": i.get("tierMinimumUnits"), "effective": i.get("effectiveStartDate")})
            next_url, pages = data.get("NextPageLink"), pages + 1
    except Exception as e:
        fail("azure", e)
    out({"source": "api", "api": "Azure Retail Prices", "url": url, "retrieved": TODAY, "items": items})


# ---------- aws ----------
def aws(a):
    filters = [f.split("=", 1) for f in (a.filter or [])]
    try:
        import boto3, botocore.session
        if botocore.session.get_session().get_credentials():
            c = boto3.client("pricing", region_name="us-east-1")
            fl = [{"Type": "TERM_MATCH", "Field": k, "Value": v} for k, v in filters]
            if a.region:
                fl.append({"Type": "TERM_MATCH", "Field": "regionCode", "Value": a.region})
            items = []
            for page in c.get_paginator("get_products").paginate(ServiceCode=a.service, Filters=fl, PaginationConfig={"MaxItems": a.max_items}):
                for p in page["PriceList"]:
                    items.extend(_aws_flatten(json.loads(p)))
            out({"source": "api", "api": "AWS Price List Query (GetProducts)", "url": "https://api.pricing.us-east-1.amazonaws.com", "retrieved": TODAY, "items": items})
    except SystemExit:
        raise
    except Exception:
        pass  # fall through to bulk
    # Bulk offer file as CSV, streamed line by line (EC2 is ~480 MB; only matching rows are kept).
    import csv, io
    url = f"{AWS_BULK}/{a.service}/current/{a.region}/index.csv"
    want = dict(filters)
    items, header, published = [], None, None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cloud-cost-comparator/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            for raw in io.TextIOWrapper(r, encoding="utf-8", newline=""):
                if header is None:
                    if raw.startswith('"SKU"'):
                        header = next(csv.reader([raw]))
                    elif "Publication Date" in raw:
                        published = next(csv.reader([raw]))[1]
                    continue
                if want and not all(v in raw for v in want.values()):
                    continue
                row = dict(zip(header, next(csv.reader([raw]))))
                if all(row.get(k) == v for k, v in want.items()):
                    items.append({"sku": row.get("SKU"), "description": row.get("PriceDescription"), "region": row.get("Region Code") or a.region,
                                  "unit": row.get("Unit"), "unit_price": float(row.get("PricePerUnit") or "nan"), "currency": row.get("Currency"),
                                  "term": row.get("TermType"), "lease": row.get("LeaseContractLength"), "purchase_option": row.get("PurchaseOption"),
                                  "offering_class": row.get("OfferingClass"), "begin_range": row.get("StartingRange"), "end_range": row.get("EndingRange"),
                                  "usage_type": row.get("usageType")})
                    if len(items) >= a.max_items:
                        break
    except Exception as e:
        fail("aws", e)
    out({"source": "api", "api": "AWS Price List Bulk (offer file, CSV)", "url": url, "published": published, "retrieved": TODAY, "items": items})


def _aws_flatten(p):
    prod = p.get("product", {}); attrs = prod.get("attributes", {}); rows = []
    for term_type, by_sku in p.get("terms", {}).items():
        offers = by_sku.values() if isinstance(by_sku, dict) else []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            for o in (offer.values() if "priceDimensions" not in offer else [offer]):
                if not isinstance(o, dict) or "priceDimensions" not in o:
                    continue
                ta = o.get("termAttributes", {})
                for d in o["priceDimensions"].values():
                    rows.append({"sku": prod.get("sku"), "description": d.get("description"), "region": attrs.get("regionCode"),
                                 "unit": d.get("unit"), "unit_price": float(d.get("pricePerUnit", {}).get("USD", "nan")), "currency": "USD",
                                 "term": term_type, "lease": ta.get("LeaseContractLength"), "purchase_option": ta.get("PurchaseOption"),
                                 "begin_range": d.get("beginRange"), "instance_type": attrs.get("instanceType"),
                                 "attributes": {k: attrs[k] for k in ("operatingSystem", "tenancy", "preInstalledSw", "capacitystatus", "storageClass", "volumeApiName", "usagetype") if k in attrs}})
    return rows


# ---------- gcp ----------
def gcp(a):
    key = os.environ.get("GOOGLE_PRICING_API_KEY")
    if not key:
        fail("gcp", "GOOGLE_PRICING_API_KEY not set")
    try:
        services = json.loads(get(f"{GCP}/services?pageSize=5000&key={key}"))["services"]
        svc = next((s for s in services if s["displayName"].lower() == a.service.lower()), None)
        if not svc:
            fail("gcp", f"service '{a.service}' not found; names include e.g. Compute Engine, Cloud Storage, BigQuery")
        items, token = [], ""
        while True:
            u = f"{GCP}/{svc['name']}/skus?pageSize=5000&currencyCode={a.currency}&key={key}" + (f"&pageToken={token}" if token else "")
            data = json.loads(get(u))
            for s in data.get("skus", []):
                if a.match and a.match.lower() not in s["description"].lower():
                    continue
                if a.region and a.region not in s.get("serviceRegions", []):
                    continue
                for pi in s.get("pricingInfo", []):
                    pe = pi["pricingExpression"]
                    for tr in pe.get("tieredRates", []):
                        up = tr["unitPrice"]
                        items.append({"sku": s["skuId"], "description": s["description"], "region": ",".join(s.get("serviceRegions", [])),
                                      "unit": pe.get("usageUnitDescription"), "unit_price": int(up.get("units", 0)) + up.get("nanos", 0) / 1e9,
                                      "currency": up.get("currencyCode"), "tier_start": tr.get("startUsageAmount"),
                                      "usage_type": s.get("category", {}).get("usageType")})
            token = data.get("nextPageToken")
            if not token:
                break
    except SystemExit:
        raise
    except Exception as e:
        fail("gcp", e)
    out({"source": "api", "api": "Cloud Billing Catalog", "url": f"{GCP}/{svc['name']}/skus", "retrieved": TODAY, "items": items[: a.max_items]})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("probe").set_defaults(fn=probe)
    p = sp.add_parser("azure"); p.add_argument("--filter", required=True); p.add_argument("--currency", default="USD"); p.add_argument("--max-pages", type=int, default=5); p.set_defaults(fn=azure)
    p = sp.add_parser("aws"); p.add_argument("--service", required=True); p.add_argument("--region", default="us-east-1"); p.add_argument("--filter", action="append"); p.add_argument("--max-items", type=int, default=200); p.set_defaults(fn=aws)
    p = sp.add_parser("gcp"); p.add_argument("--service", required=True); p.add_argument("--match"); p.add_argument("--region"); p.add_argument("--currency", default="USD"); p.add_argument("--max-items", type=int, default=200); p.set_defaults(fn=gcp)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
