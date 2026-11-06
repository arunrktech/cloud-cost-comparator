# Service map (equivalent services)

Use the row for the component category, then choose the SKU that matches the sizing. Prefer managed services the input asks for; if the input names a specific product (for example "PostgreSQL"), keep the engine the same on all clouds. Notes flag where services are not exact equivalents; repeat such notes in the report.

| Category | AWS | Google Cloud | Azure | Notes |
|---|---|---|---|---|
| compute_vm | Amazon EC2 | Compute Engine | Virtual Machines | Match vCPU, memory and family (general purpose, compute, memory optimised). |
| containers_k8s | Amazon EKS (+ EC2 or Fargate nodes) | Google Kubernetes Engine | Azure Kubernetes Service | Control plane fees differ; price worker nodes as compute_vm. |
| containers_serverless | AWS Fargate (ECS) or App Runner | Cloud Run | Azure Container Apps | Billing units differ (vCPU second, GB second, requests). |
| functions | AWS Lambda | Cloud Run functions | Azure Functions | Price requests plus GB seconds. |
| relational_db | Amazon RDS / Aurora | Cloud SQL / AlloyDB | Azure Database for PostgreSQL or MySQL Flexible Server, Azure SQL Database | Keep engine identical; HA doubles instance cost on most offers. |
| nosql_document | Amazon DynamoDB | Firestore | Azure Cosmos DB | Capacity models differ (RCU/WCU, operations, RU/s); show conversion in note. |
| nosql_widecolumn | Amazon Keyspaces | Bigtable | Azure Cosmos DB for Apache Cassandra | |
| cache | Amazon ElastiCache | Memorystore | Azure Cache for Redis / Azure Managed Redis | |
| object_storage | Amazon S3 | Cloud Storage | Azure Blob Storage / Data Lake Storage Gen2 | Match class (hot, infrequent, archive) and redundancy. |
| block_storage | Amazon EBS | Persistent Disk / Hyperdisk | Managed Disks | |
| file_storage | Amazon EFS | Filestore | Azure Files | |
| load_balancer | Elastic Load Balancing (ALB/NLB) | Cloud Load Balancing | Azure Load Balancer / Application Gateway | |
| cdn | Amazon CloudFront | Cloud CDN | Azure Front Door | |
| nat | NAT Gateway | Cloud NAT | Azure NAT Gateway | Hourly plus per GB processed. |
| data_transfer_out | Data transfer out to internet | Network internet egress | Bandwidth (data transfer out) | Often the largest variance driver; always state the GB assumption. |
| dns | Amazon Route 53 | Cloud DNS | Azure DNS | |
| queue | Amazon SQS | Pub/Sub | Azure Service Bus / Queue Storage | |
| streaming | Amazon Kinesis Data Streams / Amazon MSK | Pub/Sub / Managed Service for Apache Kafka | Azure Event Hubs | |
| etl_batch | AWS Glue / Amazon EMR | Managed Service for Apache Spark (formerly Dataproc) / Dataflow | Azure Databricks / Azure Data Factory | |
| stream_processing | Amazon Managed Service for Apache Flink | Dataflow | Azure Stream Analytics | |
| warehouse | Amazon Redshift | BigQuery | Azure Synapse Analytics / Microsoft Fabric Data Warehouse | Microsoft recommends Fabric for new warehouses; note it. |
| query_on_lake | Amazon Athena | BigQuery (external tables) | Synapse serverless SQL pool | Priced per data scanned. |
| bi | Amazon QuickSight | Looker / Looker Studio | Power BI | Per user licensing; ask user counts. |
| genai_llm | Amazon Bedrock | Vertex AI | Azure OpenAI in Foundry Models | Price per input and output tokens; ask token volumes. |
| ml_platform | Amazon SageMaker AI | Vertex AI | Azure Machine Learning | |
| monitoring_logs | Amazon CloudWatch | Cloud Logging / Cloud Monitoring | Azure Monitor / Log Analytics | Price by GB ingested. |
| secrets | AWS Secrets Manager | Secret Manager | Azure Key Vault | |
| identity | Amazon Cognito | Identity Platform | Microsoft Entra External ID | Price by monthly active users. |
| api_gateway | Amazon API Gateway | API Gateway / Apigee | Azure API Management | |
| waf | AWS WAF | Cloud Armor | Azure Web Application Firewall | |
| backup | AWS Backup | Backup and DR Service | Azure Backup | |

Product names change (for example Dataproc became Managed Service for Apache Spark). If a page shows a newer name, use the newer name and mention the old one once.
