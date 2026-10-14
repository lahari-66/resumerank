# 9. Scalability: Load Balancing and Auto Scaling

Resume screening is bursty: nothing happens for months, then hundreds of resumes arrive in one
placement week. A traditional design would put EC2 instances behind an Elastic Load Balancer in an
Auto Scaling group – and pay for at least one instance and the load balancer around the clock.
ResumeRank gets the same properties from managed services that cost nothing while idle.

| Concern | Traditional answer | ResumeRank |
| --- | --- | --- |
| **Load balancing** | Application Load Balancer in front of EC2 instances | **API Gateway** is a managed, multi-AZ front door: every request is distributed across infrastructure AWS operates. There are no instances to balance between. |
| **Auto scaling of compute** | Auto Scaling group adds / removes instances on CPU alarms | **Lambda** runs one copy of `process_resume` per in-flight queue message and adds copies within seconds as the queue grows, up to a configured maximum, then scales to zero. |
| **Database scaling** | Resize an RDS instance | **DynamoDB on-demand** adjusts read/write capacity automatically. |
| **Burst absorption** | Over-provision | **SQS** stores the spike (queue-based load levelling); the processor drains it at its own pace. |
| **Overload protection** | Rate limiting in the application | **API Gateway throttling**: rate 20 requests/s, burst 50; excess requests get HTTP 429 and are retried by the client. |
| **Fault tolerance** | Health checks restart instances | Partial batch responses retry only transient failures; after 3 receives a message moves to the **dead-letter queue** instead of looping or being lost. |

## 9.1 Controls configured

- SQS trigger on `process_resume`: batch size 1, **maximum concurrency 5**, report batch item
  failures. The cap keeps a burst inside free-tier limits and protects downstream services; it is
  a single setting to raise for production.
- Queue visibility timeout 12 minutes (longer than the 2-minute function timeout), redrive to
  `resumerank-dlq` after 3 receives, 14-day retention on the DLQ.
- API Gateway default route throttling on the `$default` stage: rate 20, burst 50.

## 9.2 Retry semantics

The processor distinguishes two kinds of failure:

| Failure | Example | Handling |
| --- | --- | --- |
| Permanent | unknown job, unreadable or scanned PDF | candidate marked `FAILED` with a reason; message deleted (retrying would fail again) |
| Transient | DynamoDB throttled or unavailable; malformed message | returned in `batchItemFailures`; SQS redelivers it; after 3 attempts it is parked in the DLQ |

Only the failed messages of a batch are retried, and because the result is written with
`UpdateItem`, a retried message never creates a duplicate candidate.

## 9.3 Evidence

A load-test script (`scripts/load_test.py`) uses the public API exactly as a browser does –
pre-signed URL, then PUT to S3. With 40 uploads, 20 in parallel, against the deployed system:

| Measure | Result |
| --- | --- |
| Upload burst | 40 uploads in 2.7 s (14.6 uploads/s) |
| Queue drain | pending 36 → 15 → 0 at t + 3 s, 6 s and 9.4 s |
| Whole burst scored | **9.4 s**, with at most 5 processor copies running |
| Per resume, upload → scored | median 4 s, p95 5 s, max 6 s |
| Correctness under load | every copy of each test resume got exactly its expected score |

The CloudWatch dashboard (Figure 6) shows the corresponding rise in concurrent executions, the
queue depth spiking and draining, and the API request count.
