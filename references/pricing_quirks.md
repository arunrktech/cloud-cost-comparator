# Pricing quirks (verified 2026-11-05)

These traps produce wrong totals if missed. Check each one before writing prices.json.

| Quirk | What to do |
|---|---|
| **Azure reservation prices are per term, not per hour.** The Retail Prices API returns `type: Reservation` rows with `unitOfMeasure: "1 Hour"` but `retailPrice` is the total for the term (D2s v5 East US: 519 for 1 Year). | Hourly equivalent = retailPrice / (8760 x years). Put the formula in `note`. |
| **AWS reserved rows come in pairs.** Partial and All Upfront options have an hourly row plus an `Upfront Fee` row. | For the commitment scenario use 1 year, standard, **No Upfront** hourly rows unless the user asks otherwise. Say which option in `commit_label`. |
| **Free allowances on egress.** AWS gives 100 GB per month of data transfer out free across all services and Regions; Azure's first 100 GB per month (tier minimum 0) is priced at 0. | Price only the billable GB (quantity = GB minus allowance) and state the allowance in `note`. Free tiers for other services stay excluded unless the user asks. |
| **Tiered prices.** Storage and egress drop per GB as volume grows (AWS S3 Standard: first 50 TB at one rate, next 450 TB lower). | Add one line per tier the quantity spans. |
| **GiB versus GB.** Google Cloud lists many prices per GiB (and storage per GiB hour); AWS and Azure use GB. | Convert to one unit (1 GiB = 1.073741824 GB) or keep the vendor unit and state it. Storage per GiB hour x 730 = per GiB month. |
| **Google Cloud pages default to Iowa (us-central1).** | Switch the page's region selector before reading, or use the Catalog API with a region filter. Never label an Iowa price as us-east1. |
| **Network tier.** Google Cloud internet egress differs between Premium and Standard tier. Azure egress differs between routing preference Microsoft network and Internet. | Default to Google Premium tier and Azure Microsoft network routing (the defaults) and state it. |
| **Request units differ.** S3 prices per 1,000 PUT and per 10,000 GET (bulk file gives per request); Azure per 10,000 operations; Google per 1,000 Class A/B operations. | Convert quantity to the same unit as the unit price. |
| **Windows and licensed images cost more.** VM API rows include Windows, SQL Server and Spot variants. | Filter for Linux, shared tenancy, no preinstalled software, and exclude Spot / Low Priority unless the user asks. |
| **JavaScript rendered pages.** Vendor pricing pages often fill tables with scripts, so WebFetch sees `$-` placeholders. | Use the APIs or the rendered page in the browser. If neither works, mark the line `unpriced`. |
| **Rate limits.** Azure Retail Prices API returns HTTP 429 when called quickly. | Wait and retry (the browser helper backs off automatically); keep filters narrow. |
