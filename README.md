# ResumeRank – Serverless AI Resume Screening on AWS

A recruiter posts a job (skills can be extracted automatically from the job description), candidates
upload PDF resumes, and every resume is read, scored 0–100 against the job's requirements and ranked
on a live dashboard within seconds. Uploads are buffered in **SQS** and processed by an auto-scaling
**Lambda** that extracts the text (**Amazon Textract** OCR where the account allows it, otherwise the
PDF text layer), analyses it (**Amazon Comprehend** where available), stores the result in
**DynamoDB** and emails the recruiter through **SNS** when the score reaches the job's alert threshold
(75 by default). Everything runs inside the AWS Free Tier with no server to manage.

> Course project. The score orders resumes for human review; it does not measure ability and
> must never be used to reject a candidate automatically. All test resumes are fictional.

## Features

| For | Feature |
| --- | --- |
| Everyone | **Home page** with live counts, open positions, how-it-works and architecture; **dark mode** on every page |
| Candidates | **Apply** to any open job (job list + drag-and-drop PDF upload through a 5-minute pre-signed URL); phone-friendly layout |
| Candidates | **Track application**: live status, score ring, weighted breakdown, bonus, matched / missing skills and advice |
| Candidates | **Re-upload a text-based PDF** when an application FAILED – same reference, rescored automatically |
| Recruiters | **Access-key protected dashboard** opening on **all-jobs insights** (top 10 skill gaps across every job) |
| Recruiters | **Post a job**: skill extraction from the description, **preferred skills** (+2 each, max +10), **score weights** (must total 100), **deadline**, **per-job alert threshold** |
| Recruiters | **Close / reopen** a job; closed or expired jobs disappear from the public site and refuse uploads |
| Recruiters | Ranked, auto-refreshing **leaderboard**: stat cards, score-distribution and skill-gap charts, **full-text search** over the resumes, filters, **CSV export** |
| Recruiters | **Blind screening** ("hide names until shortlisted") and **compare two candidates** side by side |
| Recruiters | **Candidate drawer**: weighted breakdown, extracted text, **view the resume PDF**, **shortlist / reject**, private **notes** |
| Recruiters | **Email shortlist** to the alert subscribers; **QR code** of the apply link; **bulk upload** of many PDFs |
| Recruiters | **Duplicate applications**: the same email applying again replaces the earlier application (SUPERSEDED) |
| Operations | **SQS buffer + dead-letter queue**, Lambda concurrency cap, API Gateway throttling, CloudWatch dashboard, load-test script |

## Architecture

```
Browser ── S3 static website (index, recruiter, upload, status)
   │
   ├─ HTTPS ─> API Gateway HTTP API  (throttle 20 req/s, burst 50)
   │             └─> Lambda api_handler ──> DynamoDB  Jobs · Candidates (+ GSI ScoreIndex)
   │                    └─ pre-signed PUT (upload) / GET (view) URLs for the private bucket
   │
   └─ PUT resume.pdf ─> S3 resumes bucket (private, 7-day lifecycle)
                          └─ ObjectCreated:Put ─> SQS resumerank-queue ──(3 failed receives)──> SQS resumerank-dlq
                                                     └─> Lambda process_resume  (scales out, max 5 concurrent)
                                                           ├─ Textract OCR  · or PDF text layer (pypdf) on the Free plan
                                                           ├─ Comprehend key phrases / entities (when available)
                                                           ├─ scoring.py  per-job weights (default 60/20/20) + preferred-skill bonus
                                                           ├─ DynamoDB UpdateItem → SCORED | FAILED (never over SUPERSEDED)
                                                           ├─ CloudWatch metric ResumeRank/CandidateScore
                                                           └─ SNS email when score ≥ the job's alert threshold
```

The contract between the components (S3 key format, table schemas, API routes, CORS) is in
[INTERFACES.md](INTERFACES.md).

## Scalability – load balancing and auto scaling

| Concern | How ResumeRank handles it |
| --- | --- |
| **Load balancing** | API Gateway is a managed, multi-AZ front door: every request is spread across infrastructure AWS operates. There is no EC2 instance, so no ALB is needed. |
| **Auto scaling (compute)** | Lambda runs one copy per in-flight message and adds copies as the SQS queue fills, up to the event-source **maximum concurrency of 5** (raise it for production), then scales back to zero. |
| **Auto scaling (database)** | DynamoDB on-demand capacity adjusts reads/writes automatically. |
| **Burst absorption** | SQS holds a spike of uploads (queue-based load levelling) so the processor never sees more than it can handle. |
| **Overload protection** | API Gateway throttling (rate 20/s, burst 50) answers excess requests with HTTP 429; the browser and load test retry. |
| **Fault tolerance** | Only transient failures are retried (partial batch responses); after 3 receives a message moves to the dead-letter queue instead of being lost or looping. |
| **Evidence** | `python scripts/load_test.py 40 20` fires 40 uploads 20 at a time; the CloudWatch dashboard shows concurrent executions rising, queue depth spiking and draining, and API 4xx (throttled) counts. |

## API

| Route | Access | Purpose |
| --- | --- | --- |
| `GET /jobs` | public / recruiter | open jobs (recruiter key: every job), or one job with `?jobId=` |
| `POST /upload-url` | public | PENDING candidate + pre-signed PUT; supersedes the same email's earlier application |
| `POST /reupload-url` | public | new pre-signed PUT to the same key for a FAILED candidate |
| `GET /status` | public | a candidate's own result |
| `POST /skills/extract` | public | skills found in a job description |
| `POST /jobs` | recruiter | create a job (deadline, alert threshold, preferred skills, weights) |
| `POST /jobs/status` | recruiter | close or reopen a job |
| `GET /candidates` | recruiter | ranked leaderboard with full text |
| `POST /decision` | recruiter | shortlist / reject / clear, optional note |
| `POST /shortlist/send` | recruiter | email the shortlist through SNS |
| `GET /resume-url` | recruiter | 5-minute pre-signed GET to view a PDF |

Request and response examples are in [INTERFACES.md](INTERFACES.md) §3.

## Repository layout

| Path | Contents |
| --- | --- |
| `lambda/process_resume/` | SQS/S3-triggered processor: `lambda_function.py`, `scoring.py`, `skills.json` (184 skills with aliases), `requirements.txt` (pypdf, bundled into the zip) |
| `lambda/api_handler/` | HTTP API handler for the eleven routes (the package script also bundles `scoring.py` + `skills.json` for skill extraction) |
| `frontend/` | `index.html`, `recruiter.html`, `upload.html`, `status.html`, `app.js`, `styles.css`, `qrcode.js` (MIT, inlined), `config.example.js` |
| `iam/` | trust policy, least-privilege inline policies for both roles, SQS queue access policy |
| `tests/` | 94 unit tests, eight realistic test resumes (R1–R8, PDF + text), Lambda console test events, curl smoke test, Postman collection |
| `scripts/` | `package_lambda.py`, `make_test_resumes.py`, `load_test.py`, `draw_architecture.py`, `build_report.py` |
| `docs/` | blueprint, `test_matrix.md`, `cloudwatch-dashboard.json`, architecture diagram, report sources |

## Local development

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (Git Bash: source .venv/Scripts/activate)
pip install -r requirements-dev.txt

python -m unittest discover -s tests -v    # scoring + both handlers, AWS faked
python -m pyflakes lambda scripts tests
python scripts/make_test_resumes.py        # regenerate tests/resumes/R1..R8 (reportlab)
python scripts/package_lambda.py           # dist/process_resume.zip, dist/api_handler.zip
```

Configuration is never committed. Copy `.env.example` → `.env` (resource names, API URL and the
recruiter key, used by the smoke and load tests) and `frontend/config.example.js` →
`frontend/config.js` (API URL). Both copies are gitignored.

## Deployment (AWS Console, region ap-south-1)

1. **Guard-rails** – AWS Budgets **zero-spend budget** (`resumerank-zero-spend`, emails both members once spend passes USD 0.01) and Free Tier usage alerts. A CloudWatch billing alarm (us-east-1) can be added once the Billing metric appears.
2. **S3** – `resumerank-site-<suffix>` and `resumerank-resumes-<suffix>`, Block Public Access on
   both; lifecycle rule on the resumes bucket expiring `resumes/` after 7 days.
3. **DynamoDB** (on-demand) – `Jobs` (PK `jobId`), `Candidates` (PK `jobId`, SK `candidateId`)
   with GSI `ScoreIndex` (PK `jobId`, SK `score` Number, projection ALL).
4. **SNS** – standard topic `resumerank-alerts`, email subscriptions confirmed.
5. **SQS** – `resumerank-dlq` (14-day retention) and `resumerank-queue` (visibility timeout
   12 min, access policy `iam/sqs-queue-policy.json`, dead-letter queue `resumerank-dlq` after
   3 receives).
6. **IAM** – roles `role-api` and `role-processor` (use case Lambda), each with
   `AWSLambdaBasicExecutionRole` plus the inline policy from `iam/` (replace `<ACCOUNT_ID>` and
   `<SUFFIX>`).
7. **Lambda `process_resume`** – Python 3.12, 256 MB, 120 s, role `role-processor`; upload
   `dist/process_resume.zip`; environment `JOBS_TABLE`, `CANDIDATES_TABLE`, `SNS_TOPIC_ARN`,
   `SCORE_THRESHOLD=75` (default when a job has no `alertThreshold`); SQS trigger on `resumerank-queue` with batch size 1, maximum
   concurrency 5 and *report batch item failures*.
8. **S3 → SQS** – resumes bucket → Event notifications: `PUT`, prefix `resumes/`, suffix `.pdf`,
   destination `resumerank-queue`.
9. **Lambda `api_handler`** – Python 3.12, 256 MB, 10 s, role `role-api`; upload
   `dist/api_handler.zip`; environment `JOBS_TABLE`, `CANDIDATES_TABLE`, `SCORE_INDEX`,
   `RESUMES_BUCKET`, `RECRUITER_KEY` (a long random string, kept out of Git) and `SNS_TOPIC_ARN`
   (for emailing the shortlist). `role-api` needs `dynamodb:UpdateItem` on Jobs (close / reopen)
   and `sns:Publish` on the topic – both are in `iam/role-api-policy.json`.
10. **API Gateway** – HTTP API `resumerank-api` with the eleven routes above, all
    integrated with `api_handler`; stage `$default` with auto-deploy and throttling rate 20 /
    burst 50; CORS as in INTERFACES.md §4 (headers `content-type`, `x-recruiter-key`).
11. **Website** – put the invoke URL in `frontend/config.js`; upload `index.html`,
    `recruiter.html`, `upload.html`, `status.html`, `app.js`, `styles.css`, `qrcode.js`, `config.js` to the
    site bucket; static website hosting with index document `index.html`; public read on the
    site bucket only; resumes bucket CORS allows `PUT` from the site origin.
12. **Dashboard** – CloudWatch → Dashboards → create `ResumeRank` → Actions → View/edit source →
    paste `docs/cloudwatch-dashboard.json` (replace `<API_ID>`).

Verify with `bash tests/api/smoke_test.sh`, the eight resumes in
[docs/test_matrix.md](docs/test_matrix.md), then `python scripts/load_test.py`.

## Scoring

```
skill      = matched_required / required × W_skills                       (default 60)
experience = min(years / max(min_years, 1), 1) × W_experience             (default 20)
             min_years = 0: full marks if the resume shows dated work, projects or activities
education  = W_education if b.tech / b.e. / bachelor / m.tech / mca / bsc / msc / phd, else half  (default 20)
bonus      = 2 per preferred skill found, at most 10
score      = min(100, round(skill + experience + education + bonus))
```

With default weights and no preferred skills this is exactly the blueprint formula. Skills are
matched in two passes (aliases over the extracted text, then over Comprehend key phrases), including
skills inside brackets such as "AWS (Lambda, API Gateway)". Experience is the larger of explicit
"N years" mentions and summed date ranges, counted **only in work sections** and unlabelled text:
education dates never count, and project, hackathon and club-role dates are not work years. Ranges
are merged for overlaps and capped at 15. Every component, the weights used and the bonus are stored
with each candidate so each number can be explained.

## Limitations

- Recruiter access is a single shared key, not individual accounts (Cognito is future work);
  job listings and candidate status pages are public by design.
- **Textract on the AWS Free plan:** Free-plan accounts get `SubscriptionRequiredException` from
  Textract. The processor then falls back to the PDF's embedded text layer (pypdf, bundled in the
  zip): text PDFs score normally, scanned image PDFs are marked FAILED with the reason. On a paid
  account Textract is used automatically, with no code change. Comprehend is blocked the same way;
  the processor then skips it and matches skills on the extracted text alone.
- English PDF resumes only; unusual layouts or poor scans can OCR imperfectly – the text preview
  in the candidate drawer shows what was read.
- SNS emails every confirmed subscriber of the topic, not just the job's `recruiterEmail` – for score
  alerts and for the emailed shortlist.
- Duplicate applications are matched on the email typed into the form; a candidate using a
  different email is treated as a new applicant.
- The score is a transparent heuristic, not a model of candidate quality, and can encode bias
  (for example against career gaps).

## Tear-down (after the viva)

S3 event notification → both Lambdas (and the SQS trigger) → API Gateway → both SQS queues →
empty and delete both buckets → both DynamoDB tables → SNS topic → CloudWatch dashboard and
budget → both IAM roles. Confirm the Billing console shows a zero forecast.
