# Abstract

College placement cells and small companies receive hundreds of resumes for every opening and
screen them by hand – slowly, inconsistently and without a record of why a candidate was passed
over. Commercial applicant-tracking systems solve this for large firms but cost money, need
servers or subscriptions and send applicant data outside the institution.

**ResumeRank** is a fully serverless, event-driven resume screening system built on Amazon Web
Services in two days by a team of two, at a cloud cost of Rs. 0. A recruiter posts a job – the
required skills can be extracted automatically from the job description – and shares an
application link. Candidates upload a PDF through a static web page; the file goes straight into a
private S3 bucket through a short-lived pre-signed URL. The upload event is buffered in an SQS
queue and processed by an automatically scaling AWS Lambda function that extracts the text
(Amazon Textract OCR where the account permits, otherwise the PDF text layer), analyses it (Amazon
Comprehend where available), and scores the candidate 0–100 with a transparent formula: skills 60,
experience 20, education 20. Results are stored in DynamoDB, ranked through a global secondary
index, shown on a live recruiter dashboard with charts, filters, CSV export and shortlist / reject
actions, and an SNS email alerts the recruiter to every candidate scoring 75 or more. Candidates
can track their own application and see which required skills were not recognised.

The system is secured with least-privilege IAM roles, a private bucket, pre-signed upload and view
URLs and a recruiter access key; it is observed through CloudWatch logs, a custom metric and a
dashboard; and it scales through API Gateway, SQS and Lambda with throttling and a dead-letter
queue. All six team-authored test resumes behaved exactly as predicted, and a load test scored a
burst of 40 resumes in 9.4 seconds. The report also documents an honest limitation: on the AWS Free
plan Textract and Comprehend are unavailable, and the system degrades gracefully to text-layer
extraction rather than failing.

**Keywords:** serverless computing, event-driven architecture, AWS Lambda, Amazon SQS, DynamoDB,
resume screening, auto scaling, cloud security.
