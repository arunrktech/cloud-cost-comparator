# Sizing defaults

Planning defaults for when the input and the user leave a value open. They are deliberately modest and must be labelled `default` in the assumptions table. They are not recommendations.

| Item | Default |
|---|---|
| Hours running per month | 730 (always on) for production; 176 (8 h x 22 days) for dev/test if the input says non production |
| Web or app VM | 2 instances, 2 vCPU, 8 GB memory, Linux, general purpose |
| Container service | 2 tasks or pods, 1 vCPU, 2 GB each, always on |
| Functions | 1,000,000 invocations per month, 512 MB, 200 ms average |
| Relational database | 2 vCPU, 8 GB, 100 GB SSD storage, high availability (standby in second zone), 7 day backups |
| NoSQL database | 25 GB stored, 5,000,000 reads and 1,000,000 writes per month, on demand capacity |
| Object storage | 500 GB standard class, 100,000 writes and 1,000,000 reads per month |
| Block storage per VM | 50 GB SSD |
| Data transfer out to internet | 200 GB per month |
| Load balancer | 1, always on, low traffic |
| CDN | 500 GB per month delivered, North America |
| NAT | 1 gateway, 100 GB processed per month |
| Logs ingested | 20 GB per month |
| Query on lake | 2 TB scanned per month |
| Warehouse | Smallest serverless or provisioned unit, 8 h per day on weekdays |
| LLM usage | 10,000,000 input tokens and 2,000,000 output tokens per month |
| BI users | 10 viewers |

Rules
- If the input gives a range ("1 to 3 TB"), use the midpoint and state the range.
- If the input gives users but not traffic, ask; do not convert users to requests silently.
- When a default drives more than 20% of a cloud's total, flag it as a high impact assumption in the report.
