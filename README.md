# ResumeRank – Serverless AI Resume Screening on AWS

A candidate uploads a PDF resume through a static web page. The upload triggers a Lambda function
that reads the PDF with **Amazon Textract**, extracts key phrases and entities with **Amazon
Comprehend**, scores the candidate 0–100 against the job's requirements, stores the result in
**DynamoDB** and emails the recruiter through **SNS** when the score is 75 or more. A ranked
leaderboard is served through **API Gateway**. Everything runs inside the AWS Free Tier.

> Course project. The score orders resumes for human review; it does not measure ability and
> must never be used to reject a candidate automatically. All test resumes are fictional.

## Architecture

```
Browser ──GET──> S3 website bucket (upload.html, recruiter.html)
   │
   ├─ POST /jobs, POST /upload-url, GET /candidates ─> API Gateway (HTTP API) ─> api_handler ─> DynamoDB Jobs / Candidates
   │                                                                              └─ returns pre-signed PUT URL (300 s, PDF, ≤ 5 MB)
   └─ PUT resume.pdf (pre-signed) ─> S3 resumes bucket (private)
                                        └─ ObjectCreated:Put (resumes/ *.pdf) ─> process_resume
                                               ├─ Textract StartDocumentTextDetection / GetDocumentTextDetection
                                               ├─ Comprehend DetectKeyPhrases / DetectEntities (5,000-byte chunks)
                                               ├─ scoring.py (skills 60 · experience 20 · education 20)
                                               ├─ DynamoDB UpdateItem → SCORED | FAILED
                                               ├─ CloudWatch metric ResumeRank/CandidateScore
                                               └─ SNS publish when score ≥ 75 ─> recruiter email
```

The interfaces between the two halves of the system (S3 key format, table schemas, API
contract, CORS) are fixed in [INTERFACES.md](INTERFACES.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `lambda/process_resume/` | S3-triggered processor: `lambda_function.py`, `scoring.py`, `skills.json` (153 skills with aliases), `requirements.txt` (pypdf, bundled into the zip) |
| `lambda/api_handler/` | HTTP API handler for the three routes |
| `frontend/` | `upload.html`, `recruiter.html`, `styles.css`, `config.example.js` |
| `iam/` | trust policy and least-privilege inline policies for `role-api` and `role-processor` |
| `tests/` | unit tests, six test resumes, Lambda console test events, curl smoke test, Postman collection |
| `scripts/` | `package_lambda.py` (zips a function), `make_test_resumes.py` |
| `docs/` | blueprint, `test_matrix.md`, `cloudwatch-dashboard.json` |

## Local development

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (Git Bash: source .venv/Scripts/activate)
pip install -r requirements-dev.txt

python -m unittest discover -s tests -v    # scoring + both handlers, AWS faked
python -m pyflakes lambda scripts tests
python scripts/make_test_resumes.py        # regenerate tests/resumes/R1..R6
python scripts/package_lambda.py           # dist/process_resume.zip, dist/api_handler.zip
```

Configuration is never committed. Copy `.env.example` → `.env` (resource names only, used by
the smoke test) and `frontend/config.example.js` → `frontend/config.js` (API URL). Both copies
are gitignored.

## Deployment (AWS Console, region ap-south-1)

1. **Guard-rails** – AWS Budgets **zero-spend budget** (`resumerank-zero-spend`, emails both members once spend passes USD 0.01) and Free Tier usage alerts. A CloudWatch billing alarm (us-east-1) can be added once the Billing metric appears.
2. **S3** – `resumerank-site-<suffix>` and `resumerank-resumes-<suffix>`, Block Public Access on
   both; lifecycle rule on the resumes bucket expiring `resumes/` after 7 days.
3. **DynamoDB** (on-demand) – `Jobs` (PK `jobId`), `Candidates` (PK `jobId`, SK `candidateId`)
   with GSI `ScoreIndex` (PK `jobId`, SK `score` Number, projection ALL).
4. **SNS** – standard topic `resumerank-alerts`, email subscriptions confirmed.
5. **IAM** – roles `role-api` and `role-processor` (use case Lambda), each with
   `AWSLambdaBasicExecutionRole` plus the inline policy from `iam/` (replace `<ACCOUNT_ID>` and
   `<SUFFIX>`).
6. **Lambda `process_resume`** – Python 3.12, 256 MB, 120 s, role `role-processor`; upload
   `dist/process_resume.zip`; environment `JOBS_TABLE`, `CANDIDATES_TABLE`, `SNS_TOPIC_ARN`,
   `SCORE_THRESHOLD=75`; Configuration → Asynchronous invocation → retry attempts **0**;
   S3 trigger on the resumes bucket, event `PUT`, prefix `resumes/`, suffix `.pdf`.
7. **Lambda `api_handler`** – Python 3.12, 256 MB, 10 s, role `role-api`; upload
   `dist/api_handler.zip`; environment `JOBS_TABLE`, `CANDIDATES_TABLE`, `SCORE_INDEX`,
   `RESUMES_BUCKET`.
8. **API Gateway** – HTTP API `resumerank-api` with routes `POST /jobs`, `POST /upload-url`,
   `GET /candidates`, all integrated with `api_handler`; stage `$default` with auto-deploy;
   CORS as in INTERFACES.md §4.
9. **Website** – put the invoke URL in `frontend/config.js`; upload `upload.html`,
   `recruiter.html`, `styles.css`, `config.js` to the site bucket; enable static website
   hosting; allow public read on the site bucket only; set the resumes bucket CORS
   (INTERFACES.md §4).
10. **Dashboard** – CloudWatch → Dashboards → create `ResumeRank` → Actions → View/edit source →
    paste `docs/cloudwatch-dashboard.json`.

Verify with `bash tests/api/smoke_test.sh`, then the six resumes in
[docs/test_matrix.md](docs/test_matrix.md).

## Scoring

```
skill_score = matched / required × 60
exp_score   = min(years / max(min_years, 1), 1) × 20     (min_years = 0: 20 if any work/project dates)
edu_score   = 20 if b.tech / b.e. / bachelor / m.tech / mca / bsc / msc / phd found, else 10
score       = round(skill_score + exp_score + edu_score)
```

Skills are matched in two passes (aliases over the OCR text, then over Comprehend key phrases).
Experience is the larger of explicit "N years" mentions and summed date ranges outside the
education section (Comprehend DATE entities + text), merged for overlaps and capped at 15.
Component scores are stored with every candidate so each number can be explained.

## Limitations

- No authentication: anyone with the URLs can post a job or view a leaderboard (Cognito is
  future work). Candidate emails are therefore not returned by the API.
- **Textract on the AWS Free plan:** Free-plan accounts get `SubscriptionRequiredException` from
  Textract. The processor then falls back to the PDF's embedded text layer (pypdf, bundled in the
  zip): text PDFs score normally, scanned image PDFs are marked FAILED with the reason. On a paid
  account Textract is used automatically, with no code change. Comprehend is blocked the same way;
  the processor then skips it and matches skills on the extracted text alone.
- English PDF resumes only; unusual layouts or poor scans can OCR imperfectly – the text preview
  on the leaderboard shows what was read.
- SNS emails every confirmed subscriber of the topic, not just the job's `recruiterEmail`.
- The score is a transparent heuristic, not a model of candidate quality, and can encode bias
  (for example against career gaps).

## Tear-down (after the viva)

S3 trigger → both Lambdas → API Gateway → empty and delete both buckets → both DynamoDB tables →
SNS topics → CloudWatch dashboard and alarm → both IAM roles. Confirm the Billing console shows a
zero forecast.
