# Test matrix – six test resumes

All six resumes are team-authored with fictional names, employers and contact details.
Regenerate them with `python scripts/make_test_resumes.py` (PDF + matching `.txt`).

## Test job

Post this job on the recruiter page (or run `tests/api/smoke_test.sh`, which creates it):

| Field | Value |
| --- | --- |
| title | Cloud Engineer Intern |
| requiredSkills | python, aws, docker, linux, sql |
| minYears | 2 |
| recruiterEmail | any subscribed address |

## Expected vs actual

"Expected (formula)" is computed from each resume's source text with the section 12 formula.
`python -m unittest tests.test_scoring` checks every row against its band locally.
Fill in "Actual" from the leaderboard after the Day 2 Hr 1 run.

| # | File | Design | Purpose | Blueprint band | Skills /60 | Exp /20 | Edu /20 | Expected (formula) | Alert? | Actual | Pass? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | `R1.pdf` | all 5 skills, 3 yrs, B.Tech, text PDF | upper bound; SNS must fire | 90–100 | 60 (5/5) | 20 (3.0 yrs) | 20 | **100** | yes | 100, alert sent (console upload, 13 Oct) | ✅ |
| R2 | `R2.pdf` | all skills as aliases (Python3, Amazon Web Services, docker-compose, Ubuntu/RHEL, PL/SQL), 2 yrs, diploma | alias dictionary | 85–95 | 60 (5/5) | 20 (2.0 yrs) | 10 | **90** | yes | 90 (8 of 8 load-test runs) | ✅ |
| R3 | `R3.pdf` | same profile as R1, **image-only PDF** (no text layer) | OCR path | 85–100 | 60 (5/5) | 20 (3.0 yrs) | 20 | **100** | yes | FAILED – no text layer (Textract unavailable on Free plan) | expected on this account |
| R4 | `R4.pdf` | 2 of 5 skills (python, sql), 1 yr, no degree | mid band; no alert | 40–55 | 24 (2/5) | 10 (1.0 yr) | 10 | **44** | no | 44, no alert (browser upload + 8 load-test runs) | ✅ |
| R5 | `R5.pdf` | no required skills, 5 yrs, M.Tech | skill weight dominates | 30–40 | 0 (0/5) | 20 (5.0 yrs) | 20 | **40** | no | 40 (8 of 8 load-test runs) | ✅ |
| R6 | `R6.pdf` | 2 pages, skills only on page 2, 3 yrs, B.Tech | multi-page Textract | R1 ± 5 | 60 (5/5) | 20 (3.0 yrs) | 20 | **100** | yes | 100, 2 pages read, alert sent (13 Oct) | ✅ |

Notes:

- "Half the skills" for R4 is 2 of 5 so the formula lands inside the 40–55 band
  (3 of 5 would give 56).
- R2 has no degree keyword on purpose (a diploma is not in the section 12 degree list), which
  is what puts it at 90 rather than 100.
- Education-section dates (e.g. "B.Tech 2018 - 2022") are excluded from experience so a
  degree is not counted as work experience.
- **This account is on the AWS Free plan, where Textract is not available.** The processor falls
  back to the PDF text layer, so R3 (image-only) is expected to end as **FAILED – "no text layer
  in the PDF (scanned image)"**. That run demonstrates the failure path (T1.6); the OCR band
  above applies only on an account with Textract access.
- R3's actual score depends on OCR quality; a lower score with a readable text preview is
  a documented limitation, not a pipeline failure.

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

`python scripts/load_test.py 40 20` – 40 uploads of R1/R2/R4/R5/R6 through the real API
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
