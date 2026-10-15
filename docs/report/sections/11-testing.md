# 11. Testing and Results

## 11.1 Test resumes

Eight fictional resumes were generated to look like real student and early-career CVs: a header
with degree and contact row, Education with CGPA, Technical Skills grouped by category, Experience,
Projects with a GitHub link and measurable bullets, Achievements and Positions of Responsibility,
and Certifications – one to two pages each. Their structure was modelled on real CVs, but every
name, employer, university, email, phone number and project is invented. The test job was
*Cloud Engineer Intern* with required skills python, aws, docker, linux, sql and a minimum of
2 years. Expected scores were computed from the formula before deployment, and a unit test checks
that the text layer of every PDF scores exactly like its source text.

| # | Profile | Purpose | Expected | Actual (deployed) |
| --- | --- | --- | --- | --- |
| R1 | cloud engineer, all 5 skills, 3 years, B.Tech | upper bound; alert must fire | 100 | 100, email received |
| R2 | developer, skills only as aliases (Python3, Amazon Web Services, docker-compose, Ubuntu/RHEL, PL/SQL), 2 years, diploma | alias dictionary | 90 | 90 |
| R3 | like R1, image-only scanned PDF | OCR path | 100 with OCR | FAILED – "no text layer… OCR needs Textract" (expected on the Free plan, §7); re-uploaded as a text PDF it was rescored to 100 under the same reference |
| R4 | data analyst, 2 of 5 skills, 1 year, Class XII only | mid band, no alert | 44 | 44, no email |
| R5 | applied ML engineer working in R / MATLAB, none of the 5 skills, 5 years, M.Tech | skill weight dominates | 40 | 40 |
| R6 | cloud engineer, two pages, skills only on page 2 | multi-page extraction | 100 | 100, 2 pages read |
| R7 | fresher web developer (Next.js, TypeScript, Express, MongoDB), AWS only in a project bullet, dated projects and a club role | fresher; club role is not work | 32 (52 for a 0-year job) | to be filled from the final run |
| R8 | software engineer, "AWS (Lambda, API Gateway, DynamoDB, S3, Cognito)", 12-month internship, hackathon wins | skills in brackets; internship years | 78 | 78 (no alert under the 95 threshold of the Tier 2 check) |

In the load test the earlier versions of R1, R2, R4, R5 and R6 were each processed eight times; every run produced the
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
| Close a job | `POST /jobs/status`, then upload | upload refused, job hidden publicly | 400 "applications for this job are closed"; hidden; still listed for the recruiter |
| Apply twice with one email | two uploads, different letter case | first SUPERSEDED, second ranked | first SUPERSEDED and unranked, second SCORED #1 |
| Notes and shortlist email | `POST /decision` with a note, `POST /shortlist/send` | note stored, one email | note returned; SNS email received |
| Per-job alert threshold | threshold 95 | 78 silent, 100 alerts | as expected |
| Re-upload a failed resume | scanned PDF, then `POST /reupload-url` twice | 200 for the same key, then 409, rescored | as expected; rescored to 100 |
| Weights and bonus | weights 40/40/20, preferred Terraform | components 40/40/20, +2, capped | 40/40/20, +2, total 100 |
| Blind screening, compare, insights, QR, phone, dark mode | Chrome against the live API | all behave as designed | 19 / 19 browser checks pass; QR decodes to the apply link |
| Unit tests | `python -m unittest` | all pass | 94 / 94 pass |

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

[[figure: screenshots/cloudwatch-dashboard.png | Figure 16 – CloudWatch dashboard during the load test: Lambda concurrency, SQS queue depth and API requests]]

[[figure: screenshots/sns-email.png | Figure 17 – SNS alert email for a candidate scoring 100]]

[[figure: screenshots/sqs-monitoring.png | Figure 18 – SQS queue monitoring: messages sent by S3 and deleted by Lambda]]

## 11.4 Issues found and fixed during testing

| Issue | Cause | Fix |
| --- | --- | --- |
| Textract and Comprehend calls rejected | AWS Free plan (`SubscriptionRequiredException`) | automatic fallback to the PDF text layer and dictionary matching (§7) |
| `POST /jobs` returned 404 | route created with method GET in API Gateway | corrected the route method |
| New routes returned 404 | routes created without an attached integration | attached the `api_handler` integration |
| Website showed the old pages | not all files uploaded and index document unchanged | uploaded all seven files, set `index.html` as index document |
| A student's club role counted as 1.8 years of work | every date range outside Education was treated as work | experience now counts only work sections; activities give the fresher credit (§6.2) |
| Real CVs used skills the dictionary did not know | dictionary built for the original test set | 31 skills and many aliases added; tests lock in bracketed skills and false-positive guards |
| A late resume could overwrite a newer application | processor wrote SCORED unconditionally | conditional write that never overwrites SUPERSEDED, and no alert for it |
| Resume PDFs could be corrupted on Windows checkouts | Git treated PDFs as text | `.gitattributes` marks PDFs and images as binary |
