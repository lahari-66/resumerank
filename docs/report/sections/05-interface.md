# 5. User Interface and Features

The interface is four static pages (HTML, CSS and vanilla JavaScript, no framework or build step)
served from the S3 website bucket. Charts use Chart.js from a CDN; the QR-code library is a small
MIT-licensed file served with the site, so it works without any external dependency. All pages share
one stylesheet, one helper script and a navigation bar with a **light / dark theme switch**, and the
candidate pages switch to a single-column, large-touch-target layout below 600 px.

| Page | For | Features |
| --- | --- | --- |
| **Home** (`index.html`) | everyone | live counts of jobs and processed resumes, open positions with *Apply* buttons, how-it-works steps, architecture and scaling overview |
| **Apply** (`upload.html`) | candidates | choose an open position (or arrive through a shared link or QR code), job details, deadline and required skills, drag-and-drop PDF upload, validation (PDF, ≤ 5 MB), a tracking link after upload; a closed or expired job explains why it cannot be applied to |
| **Track application** (`status.html`) | candidates | status that refreshes automatically while processing, a score ring, the breakdown using the job's own weights plus any preferred-skill bonus, skills found and not found, and advice; failure reasons in plain language with a **Re-upload a text-based PDF** button; a clear message when a newer application replaced this one |
| **Recruiter dashboard** (`recruiter.html`) | recruiters | access-key sign-in; **all-jobs insights** landing view; job list with closed jobs greyed; posting a job with **automatic skill extraction**, **preferred skills**, **score weights**, **deadline** and **alert threshold**; close / reopen; stat cards; **score-distribution** and **skill-gap** charts; a ranked leaderboard refreshing every 5 s with **full-text search**, filters and **CSV export**; **blind screening** and **compare two candidates**; **bulk upload**; **email shortlist**; a **QR code** of the apply link; a candidate panel with weighted breakdown, extracted text, **View resume PDF**, **Shortlist / Reject** and a private **note** |

[[figure: screenshots/home.png | Figure 2 – Home page with live statistics and open positions]]

[[figure: screenshots/home-how-it-works.png | Figure 3 – Home page: the six-step "How it works" explanation]]

[[figure: screenshots/apply.png | Figure 4 – Apply page: position picker, required skills and drag-and-drop PDF upload]]

[[figure: screenshots/status.png | Figure 5 – Candidate's application status with score ring and skill feedback]]

[[figure: screenshots/recruiter-login.png | Figure 6 – Recruiter sign-in with the access key]]

[[figure: screenshots/new-job.png | Figure 7 – Posting a job: seven required skills extracted automatically from the description]]

[[figure: screenshots/recruiter-dashboard.png | Figure 8 – Recruiter dashboard: job list, stat cards, score distribution and skill-gap charts]]

[[figure: screenshots/leaderboard.png | Figure 9 – Ranked leaderboard filtered to scores above the alert threshold and searched for a word inside the resumes ("northwind")]]

[[figure: screenshots/candidate-drawer.png | Figure 10 – Candidate panel with weighted breakdown and bonus, extracted text, resume viewer, decision buttons and private note]]

## 5.1 Recruiter workflow features

| Feature | What it does | Why it matters |
| --- | --- | --- |
| All-jobs insights | Landing view that adds up the missing skills of every scored candidate across all jobs and charts the top 10 | Shows which skills to train or advertise for, beyond a single job |
| Blind screening | "Hide names until shortlisted" replaces names and emails with *Candidate #rank* in the table, panel, compare view and CSV; search skips hidden names | Reduces name-based bias in the first pass; reveals identity only after a positive decision |
| Compare | Tick two rows to see score, components, years, matched and missing skills side by side, the better value highlighted | Faster, fairer choice between close candidates |
| Job settings | Deadline, alert threshold (50–100), preferred skills (+2 each, max +10), score weights (total 100) | Different roles value experience and education differently |
| Close / reopen | One click; the job disappears from the public site and the API refuses new uploads | Ends a hiring round without deleting data |
| Duplicates | The same email applying again replaces the earlier application, which stays visible under a filter | The leaderboard counts each person once |
| Notes and shortlist email | Private 500-character note per candidate; one click emails the ranked shortlist with notes to the alert subscribers | Hands the result to the hiring panel |
| Re-upload | A FAILED candidate (for example a scanned PDF) uploads a text-based PDF to the same reference and is rescored | Recovers applicants instead of losing them |

[[figure: screenshots/insights.png | Figure 11 – All-jobs insights: top skill gaps across every job]]

[[figure: screenshots/job-form.png | Figure 12 – Posting a job with preferred skills, score weights, deadline and alert threshold]]

[[figure: screenshots/compare.png | Figure 13 – Comparing two candidates, with blind screening switched on]]

[[figure: screenshots/qr-dark.png | Figure 14 – Job header in dark mode: status, close / email-shortlist buttons and the QR code of the apply link]]

[[figure: screenshots/phone-status.png | Figure 15 – Track-application page on a phone: weighted breakdown and bonus]]

## 5.2 API used by the pages

| Route | Access | Used by |
| --- | --- | --- |
| `GET /jobs` | public / recruiter | home page and apply page (open jobs), dashboard job list (all jobs) |
| `POST /upload-url` | public | apply page, bulk upload |
| `POST /reupload-url` | public | status page re-upload |
| `GET /status` | public | status page |
| `POST /skills/extract` | public | new-job form |
| `POST /jobs` | recruiter | new-job form |
| `POST /jobs/status` | recruiter | close / reopen |
| `GET /candidates` | recruiter | leaderboard, charts, insights, compare, CSV, search |
| `POST /decision` | recruiter | shortlist / reject, notes |
| `POST /shortlist/send` | recruiter | email shortlist |
| `GET /resume-url` | recruiter | resume viewer |

Values received from the API are always inserted as text, never as HTML, so user-supplied names
cannot inject markup. The API URL is kept in a small `config.js` that is not committed to Git.
