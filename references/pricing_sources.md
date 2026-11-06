# Pricing sources

Use only official vendor sources. Prefer the API; fall back to the pricing page. Record the exact URL used. Pages move: if a URL returns 404, search the vendor's own site for "<service> pricing" and use the official page found.

## APIs

| Cloud | API | Auth | Endpoint |
|---|---|---|---|
| Azure | Azure Retail Prices API | None | `https://prices.azure.com/api/retail/prices?$filter=...` (OData filter on serviceName, armRegionName, skuName, priceType, meterName) |
| AWS | Price List Query API (GetProducts) | AWS credentials (SigV4) | boto3 `pricing` client, endpoint region `us-east-1` |
| AWS | Price List Bulk API (offer files) | Plain download per docs | `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<serviceCode>/current/<region>/index.json` (EC2 files are very large; use GetProducts or the page instead) |
| Google Cloud | Cloud Billing Catalog API | API key (`GOOGLE_PRICING_API_KEY`) | `https://cloudbilling.googleapis.com/v1/services?key=...` then `/v1/services/<id>/skus?key=...` |

Documentation
- Azure: https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices
- AWS: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api-fetching-price-list-files-manually.html and https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html
- Google Cloud: https://docs.cloud.google.com/billing/v1/how-tos/catalog-api

Network note: these hosts may be blocked by the session's network allowlist. `fetch_prices.py probe` reports this. An admin can allow `prices.azure.com`, `pricing.us-east-1.amazonaws.com`, `api.pricing.us-east-1.amazonaws.com` and `cloudbilling.googleapis.com`. Until then, call the same APIs from the user's browser with `assets/browser_pricing.js` (Claude in Chrome), which is not limited by the session allowlist. Tested 2026-11-05: Azure Retail Prices and AWS bulk CSV work this way with no login.

## Pricing pages (rendered in the browser, or WebFetch as a last resort)

WebFetch can only open URLs that appeared in a search result, so run WebSearch restricted to the vendor domain first (for example `allowed_domains: ["aws.amazon.com"]`, query `"S3 pricing"`) and fetch the official link it returns. Most of these pages fill prices with JavaScript, so WebFetch often sees empty tables; the rendered page in the browser (`pageGrep` in assets/browser_pricing.js) works better.

| Category | AWS | Google Cloud | Azure |
|---|---|---|---|
| VMs | https://aws.amazon.com/ec2/pricing/on-demand/ | https://cloud.google.com/products/compute/pricing/general-purpose (also /compute-optimized, /memory-optimized) | https://azure.microsoft.com/pricing/details/virtual-machines/linux/ |
| Block storage | https://aws.amazon.com/ebs/pricing/ | https://cloud.google.com/compute/disks-image-pricing | https://azure.microsoft.com/pricing/details/managed-disks/ |
| Object storage | https://aws.amazon.com/s3/pricing/ | https://cloud.google.com/storage/pricing | https://azure.microsoft.com/pricing/details/storage/blobs/ |
| Relational DB | https://aws.amazon.com/rds/pricing/ | https://cloud.google.com/sql/pricing | https://azure.microsoft.com/pricing/details/postgresql/flexible-server/ |
| NoSQL | https://aws.amazon.com/dynamodb/pricing/ | https://cloud.google.com/firestore/pricing ; https://cloud.google.com/bigtable/pricing | https://azure.microsoft.com/pricing/details/cosmos-db/ |
| Serverless containers | https://aws.amazon.com/fargate/pricing/ | https://cloud.google.com/run/pricing | https://azure.microsoft.com/pricing/details/container-apps/ |
| Kubernetes | https://aws.amazon.com/eks/pricing/ | https://cloud.google.com/kubernetes-engine/pricing | https://azure.microsoft.com/pricing/details/kubernetes-service/ |
| Functions | https://aws.amazon.com/lambda/pricing/ | https://cloud.google.com/run/pricing | https://azure.microsoft.com/pricing/details/functions/ |
| Load balancer | https://aws.amazon.com/elasticloadbalancing/pricing/ | https://cloud.google.com/vpc/network-pricing | https://azure.microsoft.com/pricing/details/load-balancer/ |
| CDN | https://aws.amazon.com/cloudfront/pricing/ | https://cloud.google.com/cdn/pricing | https://azure.microsoft.com/pricing/details/frontdoor/ |
| NAT | https://aws.amazon.com/vpc/pricing/ | https://cloud.google.com/nat/pricing | https://azure.microsoft.com/pricing/details/azure-nat-gateway/ |
| Data transfer out | https://aws.amazon.com/ec2/pricing/on-demand/ (Data Transfer section) | https://cloud.google.com/vpc/network-pricing | https://azure.microsoft.com/pricing/details/bandwidth/ |
| Queue / streaming | https://aws.amazon.com/sqs/pricing/ ; https://aws.amazon.com/kinesis/data-streams/pricing/ | https://cloud.google.com/pubsub/pricing | https://azure.microsoft.com/pricing/details/service-bus/ ; https://azure.microsoft.com/pricing/details/event-hubs/ |
| ETL / Spark | https://aws.amazon.com/glue/pricing/ ; https://aws.amazon.com/emr/pricing/ | https://cloud.google.com/dataflow/pricing ; https://cloud.google.com/products/managed-service-for-apache-spark/pricing | https://azure.microsoft.com/pricing/details/databricks/ ; https://azure.microsoft.com/pricing/details/data-factory/ |
| Stream processing | https://aws.amazon.com/managed-service-apache-flink/pricing/ | https://cloud.google.com/dataflow/pricing | https://azure.microsoft.com/pricing/details/stream-analytics/ |
| Warehouse / lake query | https://aws.amazon.com/redshift/pricing/ ; https://aws.amazon.com/athena/pricing/ | https://cloud.google.com/bigquery/pricing | https://azure.microsoft.com/pricing/details/synapse-analytics/ |
| Monitoring / logs | https://aws.amazon.com/cloudwatch/pricing/ | https://cloud.google.com/stackdriver/pricing | https://azure.microsoft.com/pricing/details/monitor/ |
| Generative AI | https://aws.amazon.com/bedrock/pricing/ | https://cloud.google.com/vertex-ai/generative-ai/pricing | https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/ |
| Secrets | https://aws.amazon.com/secrets-manager/pricing/ | https://cloud.google.com/secret-manager/pricing | https://azure.microsoft.com/pricing/details/key-vault/ |
| BI | https://aws.amazon.com/quicksight/pricing/ | https://cloud.google.com/looker/pricing | https://www.microsoft.com/power-platform/products/power-bi/pricing |

Reading pages
- Ask WebFetch for the exact price, unit, region and pricing option (on demand vs commitment) for one SKU at a time.
- Some pages load prices with scripts and return no numbers. If so, try the API, the vendor's documentation page for that service, or mark the line `unpriced` and tell the user. Never estimate.
- Tiered prices (for example first 50 TB per month): price the tier the quantity falls in and say so in `note`; if the quantity spans tiers, add one line per tier.
