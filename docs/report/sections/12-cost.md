# 12. Cost Analysis

Nothing in ResumeRank runs continuously: there is no EC2 instance, NAT gateway, load balancer or
database server – the services most likely to produce an unexpected bill on a student account.
Every component is billed per request or per stored byte, and the project's usage is a small
fraction of the free allowances.

| Resource | Usage for the whole project (approx.) | Free allowance | Share used |
| --- | --- | --- | --- |
| Lambda requests | ~600 invocations | 1,000,000 / month | < 0.1 % |
| Lambda compute | ~600 × 3 s × 0.25 GB ≈ 450 GB-s | 400,000 GB-s / month | 0.1 % |
| API Gateway (HTTP API) | ~3,000 calls (5-second leaderboard refresh) | 1,000,000 / month | 0.3 % |
| SQS requests | ~500 (send, receive, delete) | 1,000,000 / month | < 0.1 % |
| DynamoDB | < 1 MB stored, a few thousand on-demand requests | 25 GB + free request capacity | < 0.1 % |
| S3 | < 10 MB stored, ~1,000 requests | 5 GB, 20,000 GET, 2,000 PUT | ~50 % of PUTs at most |
| SNS email | ~60 alerts | 1,000 / month | 6 % |
| CloudWatch | 1 custom metric, 1 dashboard, logs < 50 MB | 10 metrics, 3 dashboards, 5 GB logs | within |
| Textract / Comprehend | not available on the account's Free plan | – | 0 |

**Total expected bill: Rs. 0.**

## 12.1 Guard-rails

- An **AWS Budgets zero-spend budget** (`resumerank-zero-spend`) emails both members as soon as
  actual spend exceeds USD 0.01. (A CloudWatch billing alarm at USD 1 was planned; billing metrics
  take hours to appear on a new account, so the budget was used instead – it is stricter.)
- Free Tier usage alerts are enabled in Billing preferences.
- Lambda concurrency is capped at 5 for the processor and the API is throttled, so a runaway client
  cannot generate unbounded usage.
- Resumes are deleted after 7 days by an S3 lifecycle rule.
- A documented tear-down order removes every resource after the evaluation.

## 12.2 At production scale

For a placement cell processing 5,000 resumes a month, Lambda, API Gateway, SQS, DynamoDB and S3
would still sit inside or close to the always-free allowances. The only material cost would be
Textract (about USD 1.50 per 1,000 pages) on a paid account – roughly USD 15 a month for 5,000
two-page resumes – compared with a continuously running EC2 instance plus load balancer, which
would cost more than that before processing a single resume.
