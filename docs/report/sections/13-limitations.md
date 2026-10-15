# 13. Limitations, Ethics and Future Scope

## 13.1 Limitations

- **Scanned resumes on the Free plan.** Without Textract, image-only PDFs cannot be read; they are
  marked FAILED with a clear reason. On an account with Textract access they are OCR'd normally.
- **Heuristic scoring.** The score measures stated fit to a job description, not ability. Skills
  described in unusual words, or missing from the 184-skill dictionary, can be missed.
- **Experience estimation** relies on explicit statements and date ranges in work sections;
  resumes that give neither are scored as having no experience. Work listed under an unusual heading
  is counted only if the heading is recognised.
- **Shared recruiter key.** One secret protects all recruiter functions; there are no individual
  accounts or per-recruiter job ownership.
- **SNS fan-out.** Alerts and emailed shortlists go to every confirmed subscriber of the topic, not
  only to the recruiter who posted the job.
- **Duplicate detection by email.** A candidate who applies again with a different email address
  is treated as a new applicant. The check reads the job's candidates with a filter, which is fine
  at tens to hundreds per job; a dedicated index would be needed at larger scale.
- **Recruiter-set weights.** Per-job weights and preferred skills make the score more flexible but
  also easier to tune in a biased direction; the weights used are stored and shown with every score
  so they remain visible.
- **English PDF resumes only**, maximum 5 MB.
- **Prototype scale controls.** Processor concurrency is deliberately capped at 5 to stay within
  free limits; production would raise it.

## 13.2 Ethics and fairness

Automated screening can encode bias – for example by penalising career gaps, non-standard
education paths or simply different vocabulary. ResumeRank is designed to **order a pile for human
review, never to decide**:

- the interface states on every page that the score is not a hiring decision;
- the score is fully explained (three components, matched and missing skills, extracted text);
- only a recruiter can shortlist or reject, and nothing is rejected automatically;
- **blind screening** hides names and emails until a candidate is shortlisted, so the first pass
  is made on skills and experience alone;
- a candidate whose resume could not be read can **re-upload** it instead of silently dropping out;
- candidates can see their own result and which required skills were not recognised, with advice on
  making them explicit – making the process more transparent for applicants than manual screening;
- test resumes are fictional; real resumes are deleted after 7 days.

A production deployment should add a periodic review of score distributions across groups and let
candidates request a manual review.

## 13.3 Future scope

| Area | Improvement |
| --- | --- |
| Identity | Amazon Cognito sign-in for recruiters and candidates; per-recruiter jobs |
| Orchestration | AWS Step Functions for the pipeline stages, with per-stage retries |
| Scoring | Semantic matching with embeddings or a Bedrock model, alongside the transparent rule; learned skill similarity instead of a fixed alias list |
| Notifications | Per-job email routing with SNS filter policies or Amazon SES; candidate notifications when shortlisted or closed |
| Security | AWS WAF on the API, customer-managed KMS keys, audit log of recruiter decisions |
| Data | A `(jobId, email)` index for duplicate detection at scale; audit trail of re-uploads and decisions |
| Operations | Infrastructure as code (AWS SAM or CDK) and a CI/CD pipeline running the unit tests on every push |
| OCR | Textract on a paid account, or an open-source OCR container image on Lambda as an alternative |
