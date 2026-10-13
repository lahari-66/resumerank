# IAM policies

Least-privilege policies from blueprint section 14. Both roles also get the AWS managed
policy **AWSLambdaBasicExecutionRole** (CloudWatch Logs).

| File | Attach to | Purpose |
| --- | --- | --- |
| `lambda-trust-policy.json` | both roles (trust relationship) | lets Lambda assume the role; the console adds this automatically when "Lambda" is chosen as the use case |
| `role-api-policy.json` | `role-api` (inline policy `resumerank-api`) | DynamoDB PutItem/GetItem/Query on Jobs, Candidates and ScoreIndex; S3 PutObject on `resumes/*` (needed to sign the upload URL) |
| `role-processor-policy.json` | `role-processor` (inline policy `resumerank-processor`) | S3 GetObject on `resumes/*`, Textract async text detection, Comprehend key phrases + entities, DynamoDB GetItem/UpdateItem, SNS Publish on the one topic, PutMetricData limited to the `ResumeRank` namespace |

Before pasting into the console JSON editor replace:

- `<ACCOUNT_ID>` – 12-digit account id (top-right account menu)
- `<SUFFIX>` – the bucket suffix chosen in Day 1 Hr 1

`"Resource": "*"` appears only for Textract, Comprehend and CloudWatch PutMetricData, which
do not support resource-level permissions for these actions. The metric permission is still
narrowed by the `cloudwatch:namespace` condition key.

Textract reads the PDF from S3 with the **caller's** permissions, which is why
`role-processor` needs `s3:GetObject` even though the Lambda never downloads the file.
