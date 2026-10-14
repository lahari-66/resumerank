# 4. AWS Services: Role and Justification

All resources are in **ap-south-1 (Mumbai)**, chosen for the lowest latency from India and because
every service used is available there.

| Service | Role in ResumeRank | Why this service | Free allowance |
| --- | --- | --- | --- |
| **Amazon S3** | Hosts the static website; stores resumes privately; emits the upload event | Durable storage with native event notifications, website hosting and pre-signed URLs | 5 GB, 20,000 GET, 2,000 PUT / month |
| **Amazon API Gateway** (HTTP API) | Eight REST routes with CORS and throttling | Managed, load-balanced front door for Lambda; HTTP API is cheaper and simpler than REST API | 1 million calls / month |
| **AWS Lambda** | `api_handler` (API) and `process_resume` (pipeline) | No server; scales out automatically and to zero; native S3, SQS and API Gateway integration | 1 million requests, 400,000 GB-s / month |
| **Amazon SQS** | Buffer between upload events and processing; dead-letter queue | Absorbs bursts, enables controlled scaling, retries and failure isolation | 1 million requests / month |
| **Amazon DynamoDB** | Jobs and Candidates tables; ScoreIndex for the leaderboard | Serverless NoSQL with single-digit-millisecond reads; a composite key and GSI give sorted per-job queries | 25 GB storage |
| **Amazon Textract** | OCR of PDF resumes (where the account allows) | Reads multi-page and scanned PDFs directly from S3 | 1,000 pages / month (first 3 months) |
| **Amazon Comprehend** | Key phrases and entities (where the account allows) | Pre-trained NLP – no model to train or host | 50,000 units / month (12 months) |
| **Amazon SNS** | Email alert for high-scoring candidates | One-line publish; email subscriptions need no mail server | 1,000 emails / month |
| **Amazon CloudWatch** | Logs, custom score metric, scaling dashboard | Automatic for Lambda; the project's observability evidence | 10 metrics, 3 dashboards, 5 GB logs |
| **AWS IAM** | One execution role per Lambda with least-privilege policies | Mandatory for Lambda; the security learning outcome | free |
| **AWS Budgets** | Zero-spend budget emailing both members | Guarantees the Rs. 0 claim is monitored | 2 budgets free |

**Services deliberately not used:** EC2, Elastic Load Balancing, NAT gateways and RDS – each bills
continuously and is the most common source of unexpected charges on student accounts. Their roles
(compute, load balancing, scaling, database) are covered by Lambda, API Gateway, SQS and DynamoDB.

## 4.1 Lambda configuration

| Function | Runtime | Memory | Timeout | Trigger | Role |
| --- | --- | --- | --- | --- | --- |
| `api_handler` | Python 3.12 | 256 MB | 10 s | API Gateway (8 routes) | `role-api` |
| `process_resume` | Python 3.12 | 256 MB | 120 s | SQS `resumerank-queue` (batch 1, max concurrency 5) | `role-processor` |

`boto3` ships with the Lambda runtime; the only bundled dependency is `pypdf` (pure Python) in the
processor's zip.
