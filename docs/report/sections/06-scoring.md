# 6. Scoring Methodology

The score is deliberately a **transparent weighted rule**, not a trained model: every number on
the leaderboard can be explained in one sentence, and the components, the weights used and any
bonus are stored with each candidate so a recruiter can see exactly why a score is what it is.

```
skill_score = (|matched required skills| / |required skills|) × W_skills          default 60
exp_score   = min(years_found / max(min_years, 1), 1.0) × W_experience           default 20
              (fresher roles, min_years = 0: full marks if dated work, projects or activities are found)
edu_score   = W_education if a degree keyword is found, otherwise W_education / 2 default 20 / 10
              (b.tech, b.e., bachelor, m.tech, mca, bsc, msc, phd)
bonus       = 2 per preferred skill found, at most 10
score       = min(100, round(skill_score + exp_score + edu_score + bonus))
```

With the default weights and no preferred skills this is exactly the blueprint formula. A recruiter
can change the weights per job (three whole numbers that must add up to 100 – for example 40/40/20
for a role where experience matters as much as skills) and list **preferred skills** that are nice
to have but not required. Preferred skills only ever add points; they never reduce a score.

## 6.1 Skill matching

A dictionary of **184 canonical skills with aliases** (`skills.json`) is bundled with the
function – for example `"javascript": ["js", "java script", "ecmascript", "es6"]`,
`"aws": ["amazon web services", "amazon aws"]`, `"kubernetes": ["k8s", "eks", "aks", "gke"]`.
Matching runs in two passes:

1. an alias search over the lower-cased extracted text, with word boundaries so that "awsome"
   does not match `aws` and "prosql" does not match `sql`;
2. a search over Comprehend key phrases, which catches skills split across lines or embedded in
   phrases ("deployed on Amazon Web Services").

Skills written inside brackets are found too – "AWS (Lambda, API Gateway, DynamoDB, S3, Cognito)"
yields aws, lambda, api gateway, dynamodb, s3 and cognito. The dictionary was extended after running
real student CVs through the scorer: modern web stacks (Next.js, TypeScript, Express, Supabase,
Vercel, JWT, Zod, Vitest), ML tooling (PyTorch, scikit-learn, OpenCV, LoRA, PySpark, MLlib, Streamlit)
and cloud services (Cognito, Amplify, API Gateway) are all recognised, while "PostgreSQL" is not
mistaken for the separate skill "SQL" and "next steps" is not mistaken for Next.js.

Ambiguous everyday words (`go`, `r`, `c`, `rest`, `spring`, `excel`, `swift`) are only matched
through an explicit alias such as "golang" or "rest api". The job's required skills are first
mapped to their canonical names, so a recruiter who types "JS" gets the same result as one who
types "javascript". A required skill that is not in the dictionary is matched on its own name.
The union of both passes intersected with the required skills gives `matchedSkills`; the
difference gives `missingSkills`.

The same dictionary powers the **job-description skill extraction** on the recruiter page: the
API runs the alias search over the pasted description and returns the skills it found, ordered by
first mention.

## 6.2 Experience estimation

Two signals are combined and the larger is taken:

- **explicit statements** – the pattern `(\d+)\+?\s*(years?|yrs?)`, e.g. "3 years of experience";
- **date ranges** – "2021 – 2023", "Jun 2022 – Present", "03/2020 to 05/2022", found in the text
  and in Comprehend DATE entities (including two adjacent entities joined by a dash). Ranges are
  converted to months and **merged where they overlap**, so two concurrent roles are not counted
  twice.

Only **work sections** count. The resume is split by its headings: dates under Experience,
Internships or Employment (and in the summary or before any heading) count as work; dates under
**Education** never count, otherwise a four-year degree would become four years of experience; and
dates under **Projects, Achievements, Positions of Responsibility, Hackathons or Certifications** are
not work years either. This was found by testing a real student CV, where a club role "Head – Coding
Club (Jan 2025 – Present)" had been counted as 1.8 years of work. Those dated activities still count
as evidence of practical work for a **fresher role** (minimum 0 years), which then receives the full
experience marks. The result is capped at 15 years.

## 6.3 Worked example (test resume R4)

Job: python, aws, docker, linux, sql; minimum 2 years. Resume R4 lists Python and SQL, one job
"Jan 2025 – Jan 2026" and only a Higher Secondary certificate.

| Component | Calculation | Points |
| --- | --- | --- |
| Skills | 2 of 5 matched → 2/5 × 60 | 24 |
| Experience | 1.0 year / 2 required → 0.5 × 20 | 10 |
| Education | no degree keyword | 10 |
| **Total** | | **44** |

The deployed system returned exactly 44 for this resume in every run (§11). With weights 40/40/20
the same resume would score 2/5 × 40 + 0.5 × 40 + 10 = 46, and if the job listed Pandas as a
preferred skill it would gain 2 more points.

## 6.4 Honest limits of the score

The score ranks resumes by **stated** fit to a job description; it does not measure ability. A
candidate who writes "Amazon Web Services" scores the same as one who writes "AWS" only because the
dictionary says so, and a real skill that is described in unusual words can be missed. These are
stated limitations, and they are the reason the system shows the breakdown, the matched and missing
skills and the extracted text, and leaves every decision to a human (§13).
