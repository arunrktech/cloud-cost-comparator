# report.json outline

`build_report.js` builds the tables (assumptions, service mapping, line items, totals, variance, sources) from `workload.json` and `costs.json`. `report.json` supplies the narrative and metadata only.

```json
{
  "title": "Order Analytics Platform: AWS vs Google Cloud vs Azure",
  "subtitle": "Architecture and cost comparison",
  "author": "Prepared by ...",
  "date": "November 5, 2026",
  "executive_summary": ["paragraph", "paragraph"],
  "scope": ["What the inputs said, what is in and out of scope"],
  "requirements": [["FR1", "Requirement text", "Source"]],
  "architecture": {
    "aws": ["How the design works on AWS, one or two paragraphs"],
    "gcp": ["..."],
    "azure": ["..."]
  },
  "variance_discussion": ["Why the totals differ: name the components and assumptions that drive the gap"],
  "infographic_title": "Order Analytics Platform: which cloud fits?",
  "pros_cons": {
    "aws": {
      "pros": [{"text": "Lowest storage price per GB in this design", "evidence": "Table: AWS line items, S3 Standard $0.023/GB"}],
      "cons": [{"text": "Highest internet egress cost at 200 GB a month", "evidence": "Table: cost by component, data transfer row"}],
      "best_for": "Your team already runs on AWS and data stays mostly inside the cloud"
    },
    "gcp": {"pros": [], "cons": [], "best_for": ""},
    "azure": {"pros": [], "cons": [], "best_for": ""}
  },
  "risks": ["Risk or exclusion and its likely cost direction"],
  "next_steps": ["How to tighten the estimate: e.g. confirm egress volume, run vendor calculator, request committed pricing"]
}
```

Report sections built in this order
1. Title block
2. Executive summary: a generated verdict sentence from costs.json (not written by Claude), then the narrative, plus a totals table (on demand and commitment per cloud, cheapest marked, variance vs cheapest), then the infographic and a pros and cons table with evidence
3. Scope and inputs (narrative) plus requirements table
4. Assumptions table (every sizing value with stated or default basis, high impact flagged)
5. Service mapping table (component by cloud with SKU and reason)
6. Architecture per cloud: diagram plus narrative
7. Cost breakdown per cloud: line items with unit price, quantity, monthly cost, source type
8. Cost variance: per component table and narrative
9. Risks, exclusions and next steps
10. Price sources: every URL with retrieval date
