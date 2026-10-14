# 6. Scoring Methodology

The score is deliberately a **transparent weighted rule**, not a trained model: every number on
the leaderboard can be explained in one sentence, and the three components are stored with each
candidate so a recruiter can see exactly why a score is what it is.

```
skill_score = (|matched skills| / |required skills|) × 60
exp_score   = min(years_found / max(min_years, 1), 1.0) × 20
              (fresher roles, min_years = 0: 20 if any work / internship / project dates are found)
edu_score   = 20 if a degree keyword is found, otherwise 10
              (b.tech, b.e., bachelor, m.tech, mca, bsc, msc, phd)
score       = round(skill_score + exp_score + edu_score)          range 0 – 100
```

## 6.1 Skill matching

A dictionary of **153 canonical skills with aliases** (`skills.json`) is bundled with the
function – for example `"javascript": ["js", "java script", "ecmascript", "es6"]`,
`"aws": ["amazon web services", "amazon aws"]`, `"kubernetes": ["k8s", "eks", "aks", "gke"]`.
Matching runs in two passes:

1. an alias search over the lower-cased extracted text, with word boundaries so that "awsome"
   does not match `aws` and "prosql" does not match `sql`;
2. a search over Comprehend key phrases, which catches skills split across lines or embedded in
   phrases ("deployed on Amazon Web Services").

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

Dates inside the **Education** section are ignored – otherwise a four-year degree would count as
four years of work experience. The result is capped at 15 years.

## 6.3 Worked example (test resume R4)

Job: python, aws, docker, linux, sql; minimum 2 years. Resume R4 lists Python and SQL, one job
"Jan 2025 – Jan 2026" and only a Higher Secondary certificate.

| Component | Calculation | Points |
| --- | --- | --- |
| Skills | 2 of 5 matched → 2/5 × 60 | 24 |
| Experience | 1.0 year / 2 required → 0.5 × 20 | 10 |
| Education | no degree keyword | 10 |
| **Total** | | **44** |

The deployed system returned exactly 44 for this resume in every run (§11).

## 6.4 Honest limits of the score

The score ranks resumes by **stated** fit to a job description; it does not measure ability. A
candidate who writes "Amazon Web Services" scores the same as one who writes "AWS" only because the
dictionary says so, and a real skill that is described in unusual words can be missed. These are
stated limitations, and they are the reason the system shows the breakdown, the matched and missing
skills and the extracted text, and leaves every decision to a human (§13).
