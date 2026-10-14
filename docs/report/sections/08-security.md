# 8. Security Design

| Control | Implementation |
| --- | --- |
| **Private resume storage** | The resumes bucket keeps Block Public Access ON and has no public bucket policy; an anonymous request returns 403. Resumes are expired by an S3 lifecycle rule after 7 days. |
| **Pre-signed upload URLs** | `api_handler` signs a PUT for one exact key, valid 300 s. `Content-Type: application/pdf` and the declared `Content-Length` are part of the signature, so S3 itself rejects another file type or a different size. Measured: a size mismatch and a wrong type both returned **403 SignatureDoesNotMatch**. |
| **Input validation** | The API rejects non-PDF content types, files over 5 MB, malformed JSON, invalid emails, unknown IDs and over-long fields with 400 / 404. |
| **Pre-signed view URLs** | Recruiters open a resume through a 5-minute signed GET URL; the bucket never becomes public. |
| **Recruiter access key** | Recruiter routes (`POST /jobs`, `GET /candidates`, `POST /decision`, `GET /resume-url`) require the header `x-recruiter-key`, compared in constant time with a secret held only in the Lambda environment. Without it the API answers **401**. Candidate-facing routes return no other candidate's data and never the recruiter's decision. |
| **Least-privilege IAM** | Each Lambda has its own role listing only the actions and resource ARNs it uses (below). Wildcard resources appear only where AWS offers no resource-level permission (Textract, Comprehend, PutMetricData – the last narrowed by a namespace condition). |
| **Queue policy** | The SQS access policy allows `sqs:SendMessage` only from the resumes bucket in this account (`aws:SourceArn` + `aws:SourceAccount`). |
| **CORS** | API Gateway and the resumes bucket allow only the website's origin, the needed methods and the headers `content-type` and `x-recruiter-key`. |
| **No secrets in code or Git** | Bucket names, the API URL and the recruiter key live in Lambda environment variables or gitignored files (`.env`, `config.js`); no AWS keys are used anywhere. |
| **Safe rendering** | The pages insert every API value with `textContent`, never `innerHTML`, so a malicious name in a resume form cannot inject script. |

## 8.1 IAM roles

| Role | Allowed actions (resources) |
| --- | --- |
| `role-api` | DynamoDB `PutItem`, `GetItem`, `Scan` (Jobs); `PutItem`, `GetItem`, `Query`, `UpdateItem` (Candidates and ScoreIndex); S3 `PutObject`, `GetObject` (`resumes/*` – needed to sign upload and view URLs); CloudWatch Logs via `AWSLambdaBasicExecutionRole`. |
| `role-processor` | SQS `ReceiveMessage`, `DeleteMessage`, `GetQueueAttributes` (the queue); S3 `GetObject` (`resumes/*`); Textract text detection; Comprehend key phrases and entities; DynamoDB `GetItem`, `UpdateItem` (both tables); SNS `Publish` (the one topic); CloudWatch `PutMetricData` (namespace `ResumeRank` only); Logs. |

The policy JSON is versioned in the repository under `iam/`.

## 8.2 What a production system would add

Individual recruiter accounts with Amazon Cognito instead of a shared key, AWS WAF in front of the
API, encryption with a customer-managed KMS key, and an audit trail of decisions. These are listed
as future work (§13).
