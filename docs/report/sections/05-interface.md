# 5. User Interface and Features

The interface is four static pages (HTML, CSS and vanilla JavaScript, no framework or build step)
served from the S3 website bucket. Charts use Chart.js from a CDN. All pages share one stylesheet,
one helper script and a navigation bar.

| Page | For | Features |
| --- | --- | --- |
| **Home** (`index.html`) | everyone | live counts of jobs and processed resumes, open positions with *Apply* buttons, how-it-works steps, architecture and scaling overview |
| **Apply** (`upload.html`) | candidates | choose a position (or arrive through a shared link), job details and required skills, drag-and-drop PDF upload, validation (PDF, ≤ 5 MB), a tracking link after upload |
| **Track application** (`status.html`) | candidates | status that refreshes automatically while processing, a score ring, component breakdown, skills found and not found, and advice on making missing skills explicit; failure reasons in plain language |
| **Recruiter dashboard** (`recruiter.html`) | recruiters | access-key sign-in; list of all jobs; posting a job with **automatic skill extraction** from the description; stat cards; **score-distribution** and **skill-gap** charts; a ranked leaderboard refreshing every 5 s with search, status filters and **CSV export**; **bulk upload** of many PDFs; a candidate panel with score breakdown, extracted text, **View resume PDF** and **Shortlist / Reject** |

[[figure: screenshots/home.png | Figure 2 – Home page with live statistics and open positions]]

[[figure: screenshots/recruiter-dashboard.png | Figure 3 – Recruiter dashboard: stat cards, score distribution, skill gaps and the ranked leaderboard]]

[[figure: screenshots/candidate-drawer.png | Figure 4 – Candidate panel with breakdown, extracted text, resume viewer and decision buttons]]

[[figure: screenshots/status.png | Figure 5 – Candidate's application status with score ring and skill feedback]]

## 5.1 API used by the pages

| Route | Access | Used by |
| --- | --- | --- |
| `GET /jobs` | public | home page, apply page, dashboard job list |
| `POST /upload-url` | public | apply page, bulk upload |
| `GET /status` | public | status page |
| `POST /skills/extract` | public | new-job form |
| `POST /jobs` | recruiter | new-job form |
| `GET /candidates` | recruiter | leaderboard, charts, CSV |
| `POST /decision` | recruiter | shortlist / reject |
| `GET /resume-url` | recruiter | resume viewer |

Values received from the API are always inserted as text, never as HTML, so user-supplied names
cannot inject markup. The API URL is kept in a small `config.js` that is not committed to Git.
