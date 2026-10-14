# 14. Conclusion

ResumeRank shows that a two-person team can build a production-shaped cloud application in two
days for Rs. 0. Every objective was met: an event-driven pipeline from upload to email with no
server; a NoSQL data model that serves a sorted leaderboard in one query; a secured REST API; a
recruiter dashboard with analytics and human decisions; candidate self-service; observability
through CloudWatch; and load balancing, auto scaling and fault tolerance demonstrated with a
measured load test – 40 resumes scored in 9.4 seconds.

The project also met a real-world constraint honestly. When the AWS Free plan blocked Textract and
Comprehend, the system was redesigned to degrade gracefully instead of failing: normal resumes
score exactly as designed, scanned ones fail with a clear explanation, and the same code uses the
AI services automatically on an account that has them.

The score is a transparent rule that orders a pile of resumes for a human recruiter. It is not a
hiring decision, and the system is built – in its interface, its data and its explanations – so
that it is never used as one.

## 14.1 Deliverables

| # | Deliverable | Status |
| --- | --- | --- |
| D1 | Working deployed system (S3, API Gateway, Lambda, SQS, DynamoDB, SNS, CloudWatch, IAM) | live in ap-south-1 |
| D2 | Live demonstration | six-minute script: post job → upload → leaderboard and email → scanned resume → dashboard |
| D3 | Code repository | GitHub, with README, `INTERFACES.md`, tests and scripts |
| D4 | Architecture and security design | Figure 1, `docs/architecture.drawio`, IAM policies in `iam/` |
| D5 | Report | this document |
| D6 | Cost evidence | zero-spend budget and Billing console screenshot (Appendix A) |

# References

1. Amazon Web Services, *AWS Lambda Developer Guide* – Using Lambda with Amazon SQS; partial batch responses.
2. Amazon Web Services, *Amazon Simple Queue Service Developer Guide* – Dead-letter queues; visibility timeout.
3. Amazon Web Services, *Amazon Textract Developer Guide* – Detecting text (asynchronous operations).
4. Amazon Web Services, *Amazon Comprehend Developer Guide* – DetectKeyPhrases and DetectEntities.
5. Amazon Web Services, *Amazon DynamoDB Developer Guide* – Global secondary indexes; on-demand capacity.
6. Amazon Web Services, *Amazon S3 User Guide* – Presigned URLs; event notifications; lifecycle rules.
7. Amazon Web Services, *Amazon API Gateway Developer Guide* – HTTP APIs: CORS and throttling.
8. Amazon Web Services, *AWS Free Tier* and *AWS Budgets* documentation.
9. Amazon Web Services, *AWS Well-Architected Framework – Serverless Applications Lens*.
10. P. Sbarski and S. Kroonenburg, *Serverless Architectures on AWS*, 2nd ed., Manning, 2022.
11. M. Raghavan, S. Barocas, J. Kleinberg and K. Levy, "Mitigating Bias in Algorithmic Hiring: Evaluating Claims and Practices," *Proc. ACM FAT\**, pp. 469–481, 2020.

# Appendix A – Console Evidence

[[figure: screenshots/s3-buckets.png | Figure A1 – S3 buckets; the resumes bucket is not public]]

[[figure: screenshots/dynamodb-tables.png | Figure A2 – DynamoDB tables and the ScoreIndex global secondary index]]

[[figure: screenshots/lambda-config.png | Figure A3 – process_resume configuration and its SQS trigger]]

[[figure: screenshots/api-routes.png | Figure A4 – API Gateway routes, CORS and throttling]]

[[figure: screenshots/iam-roles.png | Figure A5 – IAM role policies]]

[[figure: screenshots/budget.png | Figure A6 – Zero-spend budget and Rs. 0 billing]]
