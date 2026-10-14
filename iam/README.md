# IAM policies

Least-privilege policies from blueprint section 14, extended for the SQS buffer and the
recruiter features. Both roles also get the AWS managed policy **AWSLambdaBasicExecutionRole**
(CloudWatch Logs).

| File | Attach to | Purpose |
| --- | --- | --- |
| `lambda-trust-policy.json` | both roles (trust relationship) | lets Lambda assume the role; the console adds this automatically when "Lambda" is chosen as the use case |
| `role-api-policy.json` | `role-api` (inline policy `resumerank-api`) | Jobs: PutItem/GetItem/Scan/UpdateItem (job list, close / reopen); Candidates + ScoreIndex: PutItem/GetItem/Query/UpdateItem (decisions, notes, superseding duplicates); S3 PutObject/GetObject on `resumes/*` (signing upload and view-resume URLs); SNS Publish on `resumerank-alerts` (emailing the shortlist) |
| `role-processor-policy.json` | `role-processor` (inline policy `resumerank-processor`) | SQS receive/delete on `resumerank-queue`; S3 GetObject on `resumes/*`; Textract async text detection; Comprehend key phrases + entities; DynamoDB GetItem/UpdateItem; SNS Publish on the one topic; PutMetricData limited to the `ResumeRank` namespace |
| `sqs-queue-policy.json` | `resumerank-queue` (Access policy) | lets **only** the resumes bucket in this account send event notifications to the queue |

Before pasting into the console JSON editor replace:

- `<ACCOUNT_ID>` – 12-digit account id (top-right account menu)
- `<SUFFIX>` – the bucket suffix chosen in Day 1 Hr 1

`"Resource": "*"` appears only for Textract, Comprehend and CloudWatch PutMetricData, which
do not support resource-level permissions for these actions. The metric permission is still
narrowed by the `cloudwatch:namespace` condition key.

Textract reads the PDF from S3 with the **caller's** permissions, which is why
`role-processor` needs `s3:GetObject` even though the Lambda never downloads the file.

The dead-letter queue `resumerank-dlq` needs no permissions of its own: SQS moves messages
into it through the main queue's redrive policy.
