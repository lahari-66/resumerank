# 1. Introduction

## 1.1 The problem

Resume screening is the first filter in hiring: reading each applicant's resume and deciding
whether it meets the minimum requirements of the job well enough to justify an interview. A single
campus opening can attract 200–500 resumes. Three properties of the placement-cell setting shape
this project:

- **Volume is bursty.** Nothing happens for months, then hundreds of resumes arrive in a week. A
  system that costs money while idle is wasteful; one that cannot scale during the burst is useless.
- **There is no IT team.** Nobody will patch a server, renew a certificate or restart a crashed
  process.
- **The budget is zero.** The tool must run on a free cloud account.

## 1.2 How screening is done today

| Approach | How it works | Why it fails here |
| --- | --- | --- |
| Manual review | Recruiters open and skim every PDF | Slow, inconsistent between reviewers, no record of reasons |
| Keyword search in a folder | Search PDFs for required words | Misses synonyms ("JS" vs "JavaScript"), cannot rank, no explanation |
| Commercial ATS | Hosted platform with parsing and ranking | Subscription cost, onboarding effort, data leaves the institution |
| Script on a virtual machine | A parser polling a folder on EC2 | Bills 24 × 7, needs maintenance, failures go unnoticed |

## 1.3 Problem statement

Small teams with no budget and no operations staff have no tool that reads any resume, scores it
objectively, explains the score, ranks all applicants and alerts the recruiter immediately – and
that costs nothing while idle.

## 1.4 Objectives

| # | Objective | Where it is met |
| --- | --- | --- |
| O1 | Build an event-driven serverless pipeline: S3 upload → queue → Lambda → text extraction → DynamoDB → SNS, with no server provisioned | §3 |
| O2 | Apply managed AI services (Textract OCR, Comprehend NLP) without training a model, with a graceful fallback | §7 |
| O3 | Design a NoSQL data model in which "all candidates of a job, sorted by score" is one query | §3.3 |
| O4 | Expose a REST API through API Gateway with correct CORS and throttling | §3, §8, §9 |
| O5 | Secure uploads: private bucket, pre-signed URLs, least-privilege IAM, recruiter access key | §8 |
| O6 | Alert the recruiter by email when a candidate scores 75 or more | §3.1, §11 |
| O7 | Make the system observable: logs, a custom metric and a dashboard | §9, §11 |
| O8 | Demonstrate load balancing, auto scaling and fault tolerance | §9, §11 |
| O9 | Give recruiters and candidates a usable interface: dashboard, analytics, decisions, application tracking | §5 |
| O10 | Prove it: six test resumes with predicted scores, a load test, a repository and this report – at Rs. 0 | §10–§12 |

## 1.5 Scope

**In scope:** single- and multi-page PDF resumes in English; multiple jobs; a public job board,
application form and status page; a key-protected recruiter dashboard with analytics, bulk upload,
resume viewing and shortlist / reject decisions; email alerts; scaling controls; CloudWatch
observability; six team-authored test resumes.

**Out of scope:** individual user accounts (Cognito), formats other than PDF, interview
scheduling, any claim that the score predicts job performance, and production hardening (WAF,
custom domain, CI/CD). Each is listed as future work in §13.

## 1.6 Team and division of work

| Member | Role | Responsibilities |
| --- | --- | --- |
| M. Lahari | Backend and AI lead | processing Lambda, text extraction and Comprehend integration, skill dictionary and scoring, DynamoDB writes, SNS alerts, custom metric, queue consumer; technical report sections |
| S. Mounika Reddy | API, frontend and operations lead | IAM roles and policies, API Lambda and API Gateway, all web pages, test resumes, load test, CloudWatch dashboard, architecture diagram, README and report assembly |

The two halves meet at three interfaces agreed in the first hour and recorded in `INTERFACES.md`:
the S3 key convention `resumes/{jobId}/{candidateId}.pdf`, the DynamoDB schemas and the API
contract.
