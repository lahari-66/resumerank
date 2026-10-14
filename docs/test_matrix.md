# Test matrix – eight test resumes

All eight resumes are team-authored and fictional (names, employers, universities, `example.com`
emails, `+91 90000 0000x` phone numbers, placeholder GitHub links). They follow the structure of
real student and early-career CVs: header with degree and contact row, Education with CGPA,
Technical Skills grouped by category, Experience, Projects (title | stack, link, bullets with
numbers), Achievements and Positions of Responsibility, and Certifications.
Regenerate them with `python scripts/make_test_resumes.py` (PDF + matching `.txt`).

## Test job

| Field | Value |
| --- | --- |
| title | Cloud Engineer Intern |
| requiredSkills | python, aws, docker, linux, sql |
| minYears | 2 |
| recruiterEmail | any subscribed address |

## Expected vs actual

"Expected" is the section 12 formula applied to each resume's text;
`python -m unittest tests.test_scoring` asserts every value, every band and that the PDF text
layer scores the same as the `.txt` source. Fill in **Actual** from the leaderboard after uploading
all eight to one job.

| # | Profile | Design | Purpose | Band | Skills /60 | Exp /20 | Edu /20 | Expected | Alert? | Actual | Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | Ananya Rao – cloud engineer | all 5 skills explicit, 3 yrs, B.Tech, text PDF | upper bound | 90–100 | 60 (5/5) | 20 (3.0 yrs) | 20 | **100** | yes | | |
| R2 | Rohit Varma – developer | skills only as aliases (Python3, Amazon Web Services, docker-compose, Ubuntu / RHEL, PL/SQL), 2 yrs, diploma | alias dictionary | 85–95 | 60 (5/5) | 20 (2.0 yrs) | 10 | **90** | yes | | |
| R3 | Kavya Menon – cloud engineer | like R1, **image-only PDF** | OCR path | 85–100 | 60 (5/5) | 20 (3.0 yrs) | 20 | **100** with Textract; **FAILED – no text layer** on this Free-plan account | yes / no | | |
| R4 | Imran Shaik – data analyst | 2 of 5 skills (python, sql), 1 yr, Class XII only | mid band, no alert | 40–55 | 24 (2/5) | 10 (1.0 yr) | 10 | **44** | no | | |
| R5 | Sneha Kulkarni – applied ML (R / MATLAB) | none of the 5 skills, 5 yrs, M.Tech | skill weight dominates | 30–40 | 0 (0/5) | 20 (5.0 yrs) | 20 | **40** | no | | |
| R6 | Arjun Reddy – cloud engineer | 2 pages, all skills only on page 2, 3 yrs, B.Tech | multi-page extraction | R1 ± 5 | 60 (5/5) | 20 (3.0 yrs) | 20 | **100** | yes | | |
| R7 | Priya Nair – fresher web developer | Next.js / TypeScript / Express / MongoDB; AWS only inside a project bullet; no work experience, dated projects and a club role (Aug 2024 – Present) | fresher; club role is not work | 25–40 | 12 (1/5: aws) | 0 (0 yrs) | 20 | **32** (52 if minYears = 0) | no | | |
| R8 | Karthik Iyer – software engineer | "AWS (Lambda, API Gateway, DynamoDB, S3, Cognito)", Docker, pytest / GitHub Actions, 12-month internship, dated hackathon wins | skills in parentheses; internship years | 70–85 | 48 (4/5, no linux) | 10 (1.0 yr) | 20 | **78** | yes | | |

Notes:

- **Experience counts only work sections** (Experience, Internships, Employment, …) and unlabelled
  text such as the summary. Education dates never count, and dates under Projects, Achievements /
  Positions of Responsibility, Hackathons or Certifications are not work years. That is why R7's
  club role "Aug 2024 – Present" gives 0 years – but those dated activities still earn the
  **fresher credit** (full 20) when a job's minimum experience is 0.
- R2 has no degree keyword on purpose (a diploma is not in the section 12 degree list).
- R3 has no text layer. On an account with Textract it is OCR'd and scores like R1; on this AWS
  Free-plan account it ends as FAILED with a clear reason, which demonstrates the failure path.
- R5 is a genuine ML profile written around R / MATLAB, so none of the five required skills appear.
- R8 scores 78 – above the 75 alert threshold with one skill missing and one year of experience
  against a two-year minimum.

## Extra checks (cross-verification, Day 2 Hr 4)

| Check | How | Expected |
| --- | --- | --- |
| Non-PDF rejected | upload a `.png` on the upload page / smoke test | 400, nothing in S3 |
| File over 5 MB rejected | smoke test `fileSize: 6291456` | 400 |
| Size mismatch rejected by S3 | PUT a different file to a signed URL | 403 SignatureDoesNotMatch |
| Unknown job | `GET /candidates?jobId=00000000-0000-4000-8000-000000000000` | 404 |
| Failure visible | upload a corrupt / password-protected PDF | status FAILED with reason on the leaderboard |
| No duplicate scoring | re-check CloudWatch after R1: one invocation, one SNS email | async retries = 0 |
| Hand-check two scores | recompute skills/exp/edu by hand from the PDF | equals leaderboard |

## Load test (scaling evidence)

`python scripts/load_test.py 40 20` – 40 uploads of R1/R2/R4/R5/R6 (the earlier test set) through the real API
(pre-signed URL + S3 PUT), 20 in parallel, against the deployed stack (14 Oct 2026):

| Measure | Result |
| --- | --- |
| Upload burst | 40 uploads in 2.7 s (14.6 uploads/s), upload latency p50 0.97 s / p95 1.59 s |
| Queue drain | PENDING 36 → 15 → 0 at t+3 s, t+6 s, t+9.4 s |
| End-to-end | all 40 scored in 9.4 s (4.3 resumes/s) with Lambda capped at 5 concurrent |
| Per resume upload → scored | p50 4 s, p95 5 s, max 6 s |
| Correctness under load | mean score 74.8 = mean of the expected R1/R2/R4/R5/R6 scores (100, 90, 44, 40, 100) |
| Throttling | 0 × 429 at 20 parallel clients (API limit: rate 20/s, burst 50) |

Screenshot the CloudWatch dashboard (last 15 minutes) for the report: Lambda concurrent
executions, SQS queue depth and API Gateway requests.
