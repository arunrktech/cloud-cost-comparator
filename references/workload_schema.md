# File schemas

## workload.json

```json
{
  "project": "Order Analytics Platform",
  "inputs": ["HLD v2.docx", "Discovery notes 2026-10-12"],
  "regions": {"aws": "us-east-1", "gcp": "us-east1", "azure": "eastus"},
  "hours_per_month": 730,
  "components": [
    {
      "id": "web",
      "label": "Web tier",
      "category": "compute_vm",
      "tier": "web",
      "sizing": {"count": 2, "vcpu": 2, "memory_gb": 8, "hours": 730, "os": "linux"},
      "sizing_basis": {"count": "stated", "vcpu": "default", "memory_gb": "default", "hours": "default"},
      "source": "HLD 3.1: 'two web servers behind a load balancer'",
      "mapping": {
        "aws":   {"service": "Amazon EC2", "sku": "m7i.large", "reason": "2 vCPU / 8 GiB general purpose"},
        "gcp":   {"service": "Compute Engine", "sku": "n2-standard-2", "reason": "2 vCPU / 8 GB general purpose"},
        "azure": {"service": "Virtual Machines", "sku": "D2s v5", "reason": "2 vCPU / 8 GiB general purpose"}
      }
    }
  ],
  "flows": [
    {"from": "users", "to": "cdn", "label": "HTTPS"},
    {"from": "cdn", "to": "lb"},
    {"from": "lb", "to": "web"}
  ],
  "assumptions": [
    {"item": "Data transfer out", "value": "200 GB per month", "basis": "default", "impact": "medium"}
  ]
}
```

Field rules
- `category` is one of the keys in `service_map.md`.
- `tier` drives diagram layout: `edge`, `web`, `app`, `data`, `analytics`, `ops`. The pseudo node `users` is drawn automatically when a flow uses it.
- `sizing_basis` labels every sizing value `stated` (from input or user) or `default` (from sizing_defaults.md).
- `source` quotes the input; use `"user answer"` or `"default"` when that is the origin.

## prices.json

```json
{
  "currency": "USD",
  "retrieved": "2026-11-05",
  "clouds": {
    "aws": [
      {
        "component": "web",
        "item": "EC2 m7i.large Linux on demand",
        "unit": "hour",
        "unit_price": 0.1008,
        "quantity": 1460,
        "commit_unit_price": 0.0635,
        "commit_label": "1 year Reserved, no upfront",
        "source": "page",
        "url": "https://aws.amazon.com/ec2/pricing/on-demand/",
        "retrieved": "2026-11-05",
        "note": "2 instances x 730 hours"
      }
    ],
    "gcp": [],
    "azure": []
  }
}
```

Line rules
- One line per billable item (instance hours, GB month, requests, GB transferred). A component can have several lines.
- `quantity` is in the same unit as `unit_price` (if the price is per 1,000 requests, quantity counts thousands).
- `commit_unit_price` is optional; omit it when no published commitment price exists, and the model uses the on demand price for that line in the commitment scenario.
- `source` is `api` or `page`. `unpriced` is allowed with `unit_price: null` and a `note` explaining why; such lines are excluded from totals and listed in the report.
- Values the example shows are illustrative only. Always fetch real prices.

## costs.json (written by cost_model.py)
Totals per cloud and scenario, per component costs, variance tables, line items, unpriced list, and source list. Do not hand edit.
