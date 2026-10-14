# 11. Testing and Results

## 11.1 Test resumes

Six fictional resumes were authored to exercise each part of the pipeline. The test job was
*Cloud Engineer Intern* with required skills python, aws, docker, linux, sql and a minimum of
2 years. Expected scores were computed from the formula before deployment.

| # | Design | Purpose | Expected | Actual (deployed) | Result |
| --- | --- | --- | --- | --- | --- |
| R1 | all 5 skills, 3 years, B.Tech, text PDF | upper bound; alert must fire | 100 | **100**, email received | ✅ |
| R2 | all skills written as aliases (Python3, Amazon Web Services, docker-compose, Ubuntu/RHEL, PL/SQL), 2 years, diploma | alias dictionary | 90 | **90** | ✅ |
| R3 | same profile as R1, image-only scanned PDF | OCR path | 100 with OCR | **FAILED** – "no text layer… OCR needs Textract" | ✅ expected on the Free plan (§7) |
| R4 | 2 of 5 skills, 1 year, no degree | mid band, no alert | 44 | **44**, no email | ✅ |
| R5 | no required skills, 5 years, M.Tech | skill weight dominates | 40 | **40** | ✅ |
| R6 | two pages, skills only on page 2 | multi-page extraction | 100 | **100**, 2 pages read, email received | ✅ |

In the load test each of R1, R2, R4, R5 and R6 was processed eight times; every run produced the
identical score and breakdown, confirming the pipeline is deterministic under concurrency.

## 11.2 Functional and security checks

| Check | Method | Expected | Observed |
| --- | --- | --- | --- |
| Upload a non-PDF | API with `image/png` | 400 | 400 |
| Upload over 5 MB | API with `fileSize` 6 MB | 400 | 400 |
| Upload a different file size than declared | PUT to the signed URL | rejected by S3 | 403 SignatureDoesNotMatch |
| Upload with a different content type | PUT to the signed URL | rejected by S3 | 403 |
| Anonymous read of the resumes bucket | direct S3 request | denied | 403 |
| Recruiter route without the key | `GET /candidates` | 401 | 401 |
| CORS preflight from the website | OPTIONS | origin and headers allowed | allowed: `content-type`, `x-recruiter-key` |
| Shortlist a candidate | `POST /decision` | saved and shown | `SHORTLISTED` with timestamp |
| View a resume | `GET /resume-url` | signed PDF link | HTTP 200, `application/pdf` |
| Candidate status | `GET /status` | own score, no recruiter decision | as expected |
| Skill extraction | "Intern with Python, Amazon Web Services, Docker on Ubuntu and SQL." | 5 skills | python, aws, docker, linux, sql |
| Unit tests | `python -m unittest` | all pass | 49 / 49 pass |

## 11.3 Load test

`python scripts/load_test.py 40 20` uploaded 40 resumes, 20 at a time, through the real API.

| Measure | Result |
| --- | --- |
| Upload burst | 40 uploads in 2.7 s (14.6 uploads/s); upload latency p50 0.97 s, p95 1.59 s |
| Queue drain | pending 36 → 15 → 0 at t + 3 s, 6 s, 9.4 s |
| End-to-end | all 40 scored in **9.4 s** with at most 5 processor copies |
| Per resume upload → scored | median 4 s, p95 5 s, max 6 s |
| Correctness | mean score 74.8 = mean of the expected scores of R1, R2, R4, R5, R6 |
| Throttling | no 429 responses at 20 parallel clients (limit: 20/s, burst 50) |

[[figure: screenshots/cloudwatch-dashboard.png | Figure 11 – CloudWatch dashboard during the load test: Lambda concurrency, SQS queue depth and API requests]]

[[figure: screenshots/sns-email.png | Figure 12 – SNS alert email for a candidate scoring 100]]

[[figure: screenshots/sqs-monitoring.png | Figure 13 – SQS queue monitoring: messages sent by S3 and deleted by Lambda]]

## 11.4 Issues found and fixed during testing

| Issue | Cause | Fix |
| --- | --- | --- |
| Textract and Comprehend calls rejected | AWS Free plan (`SubscriptionRequiredException`) | automatic fallback to the PDF text layer and dictionary matching (§7) |
| `POST /jobs` returned 404 | route created with method GET in API Gateway | corrected the route method |
| New routes returned 404 | routes created without an attached integration | attached the `api_handler` integration |
| Website showed the old pages | not all files uploaded and index document unchanged | uploaded all seven files, set `index.html` as index document |
