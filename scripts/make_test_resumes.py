"""Generate the eight team-authored test resumes into tests/resumes/.

Every person, employer, university, email, phone number and link is fictional. The layout follows
common student / early-career CVs: a header with degree and contact row, Education with CGPA,
Technical Skills grouped by category, Experience, Projects (title | stack, a GitHub link and bullets
with numbers), Achievements and Positions of Responsibility, and Certifications.

    pip install reportlab Pillow
    python scripts/make_test_resumes.py

Writes R1..R8 as PDF plus a .txt with the same text in reading order (used by the scoring tests).
R3 is an image-only PDF (no text layer), so only OCR (Textract) can read it.

Test job: Cloud Engineer Intern – python, aws, docker, linux, sql – minimum 2 years.
"""

import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "resumes")

# ------------------------------------------------------------------ content
# A resume is a header plus a list of sections. Section items:
#   ("entry", left, right, sub)        e.g. university | years, then degree line
#   ("bullets", [..])
#   ("skills", [(category, text), ..])
#   ("project", title, stack, link, year, [bullets])
#   ("pagebreak",)


def resume(name, headline, contact, sections):
    return {"name": name, "headline": headline, "contact": contact, "sections": sections}


R1 = resume(
    "Ananya Rao", "B.Tech Computer Science & Engineering · Cloud Engineer",
    "ananya.rao@example.com | +91 90000 00001 | linkedin.com/in/ananya-rao-example | github.com/ananya-rao-example",
    [
        ("Summary", [("bullets", [
            "Cloud engineer with 3 years of experience building, deploying and running Python services on AWS.",
        ])]),
        ("Education", [
            ("entry", "Riverside Institute of Technology, Hyderabad", "2018 – 2022",
             "B.Tech in Computer Science & Engineering – CGPA: 8.4/10"),
        ]),
        ("Technical Skills", [("skills", [
            ("Languages", "Python, SQL, Bash"),
            ("Cloud & Infrastructure", "AWS (EC2, S3, Lambda, CloudWatch, IAM), Docker, Linux (Ubuntu), Terraform"),
            ("Backend & APIs", "FastAPI, REST APIs"),
            ("Databases", "MySQL, PostgreSQL, DynamoDB"),
            ("Testing & Tooling", "pytest, Git, GitHub Actions"),
        ])]),
        ("Experience", [
            ("entry", "Cloud Engineer – Northwind Software Pvt Ltd, Hyderabad", "Jul 2022 – Jun 2025", ""),
            ("bullets", [
                "Automated provisioning of 40+ EC2 and Lambda environments with Python and Terraform, cutting setup time from 2 days to 3 hours.",
                "Containerised 6 legacy services with Docker on Linux hosts and moved them behind an AWS load balancer with zero downtime.",
                "Wrote SQL reports on a 120 GB MySQL warehouse used weekly by the operations team.",
            ]),
        ]),
        ("Projects", [
            ("project", "Serverless Invoice Parser", "Python · AWS Lambda · S3 · DynamoDB",
             "github.com/ananya-rao-example/invoice-parser", "2024", [
                 "Event-driven pipeline that parses 1,000+ PDF invoices a day for under $1 a month.",
                 "Reached 98% field accuracy on a 300-invoice test set; 64 pytest tests in CI.",
             ]),
            ("project", "Container Health Dashboard", "Docker · Prometheus · Grafana",
             "github.com/ananya-rao-example/container-health", "2023", [
                 "Monitors 25 containers and alerts within 30 seconds of a failed health check.",
                 "Reduced mean time to recovery from 22 to 6 minutes on the team's staging cluster.",
             ]),
            ("project", "Log Search CLI", "Python · SQLite",
             "github.com/ananya-rao-example/log-search", "2022", [
                 "Indexes 5 million log lines and answers keyword queries in under 200 ms.",
             ]),
        ]),
        ("Achievements and Positions of Responsibility", [("bullets", [
            "Winner – Riverside Cloud Hackathon, built a cost-alerting bot (2021)",
            "Lead – Cloud Computing Club, ran 8 hands-on AWS workshops for 300+ students (2020 – 2021)",
        ])]),
        ("Certifications", [("bullets", [
            "AWS Certified Cloud Practitioner | AWS Certified Developer – Associate",
        ])]),
    ])

R2 = resume(
    "Rohit Varma", "Diploma in Computer Engineering · Software Developer",
    "rohit.varma@example.com | +91 90000 00002 | github.com/rohit-varma-example",
    [
        ("Summary", [("bullets", [
            "Developer with 2 years of industry experience on cloud-hosted back ends and data pipelines.",
        ])]),
        ("Education", [
            ("entry", "City Polytechnic, Bengaluru", "2020 – 2023", "Diploma in Computer Engineering – 82%"),
        ]),
        ("Technical Skills", [("skills", [
            ("Languages", "Python3, PL/SQL, Shell scripting"),
            ("Cloud & Infrastructure", "Amazon Web Services (EC2, RDS), docker-compose, Ubuntu / RHEL servers"),
            ("Backend & APIs", "Flask, REST services, Celery"),
            ("Testing & Tooling", "py.test, GitLab, Jira"),
        ])]),
        ("Experience", [
            ("entry", "Software Developer – Bluepeak Labs, Bengaluru", "Aug 2023 – Aug 2025", ""),
            ("bullets", [
                "Built Python3 ETL jobs that load 2 million rows a night into Oracle with PL/SQL procedures.",
                "Packaged 9 services with docker-compose and ran them on Ubuntu and RHEL servers on Amazon Web Services.",
                "Cut the nightly batch window from 4 hours to 70 minutes by parallelising the slowest stages.",
            ]),
        ]),
        ("Projects", [
            ("project", "Stock Alert Service", "Python3 · Flask · Celery",
             "github.com/rohit-varma-example/stock-alerts", "2024", [
                 "Sends price alerts to 500 subscribers with a median delay of 4 seconds.",
             ]),
            ("project", "Shift Planner", "Flask · Oracle · PL/SQL",
             "github.com/rohit-varma-example/shift-planner", "2023", [
                 "Schedules 120 warehouse staff a week and removed 6 hours of manual planning.",
             ]),
        ]),
        ("Certifications", [("bullets", [
            "Red Hat System Administration I | Oracle Database SQL Certified Associate",
        ])]),
    ])

R3 = resume(
    "Kavya Menon", "B.Tech Information Technology · Cloud Engineer",
    "kavya.menon@example.com | +91 90000 00003 | github.com/kavya-menon-example",
    [
        ("Summary", [("bullets", [
            "Cloud engineer with 3 years of experience automating AWS infrastructure.",
        ])]),
        ("Education", [
            ("entry", "Lakeside College of Engineering, Chennai", "2018 – 2022",
             "B.Tech in Information Technology – CGPA: 8.1/10"),
        ]),
        ("Technical Skills", [("skills", [
            ("Languages", "Python, SQL"),
            ("Cloud & Infrastructure", "AWS, Docker, Linux"),
            ("Testing & Tooling", "pytest, Git"),
        ])]),
        ("Experience", [
            ("entry", "Cloud Engineer – Harbourline Systems, Chennai", "Jun 2022 – May 2025", ""),
            ("bullets", [
                "Automated AWS infrastructure for 12 teams with Python and Bash.",
                "Packaged 15 applications with Docker on Linux servers.",
                "Maintained SQL schemas and nightly backups for 4 databases.",
            ]),
        ]),
        ("Certifications", [("bullets", ["AWS Certified Cloud Practitioner"])]),
    ])

R4 = resume(
    "Imran Shaik", "Junior Data Analyst",
    "imran.shaik@example.com | +91 90000 00004 | linkedin.com/in/imran-shaik-example",
    [
        ("Summary", [("bullets", [
            "Data analyst with 1 year of experience turning sales data into weekly reports.",
        ])]),
        ("Education", [
            ("entry", "Greenfield Junior College, Vijayawada", "2020 – 2022",
             "Higher Secondary Certificate (Class XII), MPC – 91%"),
        ]),
        ("Technical Skills", [("skills", [
            ("Languages", "Python, SQL"),
            ("Data & Reporting", "Pandas, Microsoft Excel, Power BI"),
            ("Soft skills", "Communication, Teamwork"),
        ])]),
        ("Experience", [
            ("entry", "Junior Data Analyst – Greenfield Retail, Vijayawada", "Jan 2025 – Jan 2026", ""),
            ("bullets", [
                "Wrote Python scripts that clean 50,000 sales rows a week.",
                "Built 14 SQL queries behind the weekly management dashboard in Power BI.",
            ]),
        ]),
        ("Projects", [
            ("project", "Retail Sales Dashboard", "Power BI · Excel",
             "github.com/imran-shaik-example/sales-dashboard", "2025", [
                 "Tracks 3 stores and 1,200 products; used every Monday by the store managers.",
             ]),
        ]),
    ])

R5 = resume(
    "Sneha Kulkarni", "M.Tech Machine Design · Applied ML Engineer",
    "sneha.kulkarni@example.com | +91 90000 00005 | github.com/sneha-kulkarni-example",
    [
        ("Summary", [("bullets", [
            "Applied machine-learning engineer with 5 years of experience in predictive maintenance for manufacturing.",
        ])]),
        ("Education", [
            ("entry", "Western University of Engineering, Pune", "2017 – 2019",
             "M.Tech in Machine Design – CGPA: 8.7/10"),
            ("entry", "Western University of Engineering, Pune", "2013 – 2017",
             "B.E. in Mechanical Engineering – CGPA: 8.2/10"),
        ]),
        ("Technical Skills", [("skills", [
            ("Languages", "R, MATLAB, Julia, C++"),
            ("Machine Learning", "Machine Learning, Deep Learning, Statistics, Computer Vision"),
            ("Data & Tools", "Tableau, Microsoft Excel, Simulink"),
            ("Engineering", "SolidWorks, ANSYS, AutoCAD"),
        ])]),
        ("Experience", [
            ("entry", "ML Engineer – Apex Motors, Pune", "Jun 2019 – May 2024", ""),
            ("bullets", [
                "Built vibration-based failure models in MATLAB that flag 87% of gearbox faults 10 days early.",
                "Cut unplanned downtime on 3 assembly lines by 23% in the first year of deployment.",
                "Trained a defect-detection model on 18,000 images of cast parts with 94% recall.",
            ]),
        ]),
        ("Projects", [
            ("project", "Bearing Fault Classifier", "MATLAB · Deep Learning Toolbox",
             "github.com/sneha-kulkarni-example/bearing-faults", "2023", [
                 "Classifies 4 fault types from 12 kHz vibration signals at 96% accuracy.",
             ]),
            ("project", "Tool-Wear Forecasting", "R · tidymodels",
             "github.com/sneha-kulkarni-example/tool-wear", "2022", [
                 "Forecasts cutting-tool wear 50 cycles ahead with a mean error of 4%.",
             ]),
        ]),
        ("Achievements and Positions of Responsibility", [("bullets", [
            "Best Paper – National Conference on Smart Manufacturing (2023)",
        ])]),
    ])

R6 = resume(
    "Arjun Reddy", "B.Tech Computer Science & Engineering · Cloud Engineer",
    "arjun.reddy@example.com | +91 90000 00006 | github.com/arjun-reddy-example",
    [
        ("Summary", [("bullets", [
            "Engineer with 3 years of experience running payment infrastructure. Technical skills are listed on page 2.",
        ])]),
        ("Education", [
            ("entry", "Eastgate Institute of Technology, Warangal", "2018 – 2022",
             "B.Tech in Computer Science & Engineering – CGPA: 8.0/10"),
        ]),
        ("Experience", [
            ("entry", "Cloud Engineer – Silverline Tech, Hyderabad", "Aug 2022 – Jul 2025", ""),
            ("bullets", [
                "Owned build pipelines and the on-call rotation for a payments team of 14 engineers.",
                "Reduced deployment time from 40 minutes to 8 minutes across 30 services.",
                "Mentored 2 interns and wrote the team's incident-review handbook.",
                "Led the migration of 3 batch jobs to an event-driven design, saving 18% in compute.",
            ]),
        ]),
        ("Achievements and Positions of Responsibility", [("bullets", [
            "Spot award for incident leadership during a 2023 payments outage (2023)",
            "Organiser – Eastgate Tech Fest, 1,500 participants (2021)",
        ])]),
        ("pagebreak", []),
        ("Technical Skills", [("skills", [
            ("Languages", "Python, SQL"),
            ("Cloud & Infrastructure", "AWS (EC2, S3, Lambda, DynamoDB), Docker, Linux"),
            ("Testing & Tooling", "pytest, Git, Jenkins"),
        ])]),
        ("Projects", [
            ("project", "Serverless File Converter", "AWS Lambda · S3 · Python",
             "github.com/arjun-reddy-example/file-converter", "2024", [
                 "Converts 2,000 documents a day; p95 latency 1.8 seconds.",
             ]),
            ("project", "Container Monitoring Dashboard", "Docker · Grafana · Linux",
             "github.com/arjun-reddy-example/container-monitor", "2024", [
                 "Tracks 40 containers and pages the on-call engineer within 1 minute of a crash.",
             ]),
        ]),
        ("Certifications", [("bullets", ["AWS Certified SysOps Administrator – Associate"])]),
    ])

R7 = resume(
    "Priya Nair", "B.Tech Computer Science & Engineering · 2023 – Expected 2027",
    "priya.nair@example.com | +91 90000 00007 | linkedin.com/in/priya-nair-example | github.com/priya-nair-example",
    [
        ("Education", [
            ("entry", "Lakeview University, Hyderabad", "2023 – Expected 2027",
             "B.Tech in Computer Science & Engineering – CGPA: 8.9/10 (Sem 6)"),
            ("entry", "Sunrise Junior College, Hyderabad", "2021 – 2023", "XII – MPC – 95.2%"),
        ]),
        ("Technical Skills", [("skills", [
            ("Frontend", "HTML, CSS, JavaScript, TypeScript, React, Next.js, Tailwind CSS"),
            ("Backend & APIs", "Node.js, Express, REST APIs, JWT Authentication, Zod"),
            ("Databases", "MongoDB, Mongoose"),
            ("Deployment", "Vercel, Netlify"),
            ("Testing & Tooling", "Vitest, Supertest, Git, GitHub"),
        ])]),
        ("Projects", [
            ("project", "Campus Bus Tracker", "Next.js · TypeScript · Express · MongoDB",
             "github.com/priya-nair-example/bus-tracker", "2026", [
                 "Live map of 18 college buses used by 1,100 students; location updates every 5 seconds over WebSockets.",
                 "Express REST API with JWT authentication and Zod validation; 92 Vitest/Supertest tests.",
                 "Stored driver documents in an AWS S3 bucket with pre-signed upload links.",
             ]),
            ("project", "Club Event Portal", "React · Node.js · MongoDB",
             "github.com/priya-nair-example/event-portal", "2025", [
                 "Handles registrations for 14 events and 2,300 sign-ups with QR-code check-in.",
                 "Cut check-in queues from 20 minutes to under 4 minutes at the annual tech fest.",
             ]),
            ("project", "Recipe Finder", "Next.js · Tailwind CSS",
             "github.com/priya-nair-example/recipe-finder", "2024", [
                 "Search over 5,000 recipes with filters; Lighthouse performance score of 98.",
             ]),
        ]),
        ("Achievements and Positions of Responsibility", [("bullets", [
            "Tech Lead – Web Development Club, mentoring 40 juniors (Aug 2024 – Present)",
            "Runner-up – Lakeview Webathon, 24-hour build (2025)",
        ])]),
        ("Certifications", [("bullets", ["Meta Front-End Developer | MongoDB Associate Developer"])]),
    ])

R8 = resume(
    "Karthik Iyer", "B.Tech Computer Science & Engineering · Software Engineer",
    "karthik.iyer@example.com | +91 90000 00008 | linkedin.com/in/karthik-iyer-example | github.com/karthik-iyer-example",
    [
        ("Education", [
            ("entry", "Northfield Institute of Technology, Bengaluru", "2021 – 2025",
             "B.Tech in Computer Science & Engineering – CGPA: 9.1/10"),
        ]),
        ("Technical Skills", [("skills", [
            ("Languages", "Python, Java, SQL, TypeScript"),
            ("Cloud & Infrastructure", "AWS (Lambda, API Gateway, DynamoDB, S3, Cognito), Docker"),
            ("Backend & APIs", "FastAPI, REST APIs, GraphQL"),
            ("Testing & Tooling", "pytest, GitHub Actions, Postman"),
        ])]),
        ("Experience", [
            ("entry", "Software Engineering Intern – Acme Fintech, Bengaluru", "Jun 2025 – Jun 2026", ""),
            ("bullets", [
                "Built 6 FastAPI endpoints for loan pre-approval serving 40,000 requests a day at p95 120 ms.",
                "Moved 3 cron jobs to AWS Lambda with DynamoDB, cutting the monthly bill by 35%.",
                "Raised test coverage from 48% to 86% with pytest and enforced it in GitHub Actions.",
            ]),
        ]),
        ("Projects", [
            ("project", "Expense Splitter API", "Python · FastAPI · PostgreSQL · Docker",
             "github.com/karthik-iyer-example/expense-splitter", "2025", [
                 "Splits shared expenses for 600 users; 140 pytest tests and a Docker image under 90 MB.",
             ]),
            ("project", "Serverless URL Shortener", "AWS Lambda · API Gateway · DynamoDB",
             "github.com/karthik-iyer-example/short-links", "2024", [
                 "Handles 1 million redirects a month inside the AWS free tier with Cognito-protected admin APIs.",
             ]),
            ("project", "Exam Seat Planner", "Java · SQL",
             "github.com/karthik-iyer-example/seat-planner", "2023", [
                 "Allocates 2,400 students to 60 rooms in 3 seconds with no clashes.",
             ]),
        ]),
        ("Achievements and Positions of Responsibility", [("bullets", [
            "Winner – Smart India Hackathon, fintech track (2024)",
            "Winner – Northfield 36-hour Hackathon, 80 teams (2023)",
            "Coordinator – Coding Club contest series, 12 contests (2023)",
        ])]),
        ("Certifications", [("bullets", ["AWS Certified Developer – Associate"])]),
    ])

RESUMES = {"R1": R1, "R2": R2, "R3": R3, "R4": R4, "R5": R5, "R6": R6, "R7": R7, "R8": R8}
SCANNED = {"R3"}

# ------------------------------------------------------------------ plain text (reading order)


def as_lines(r):
    """Lines in the order a PDF text extractor reads them; one None marks a page break."""
    lines = [r["name"], r["headline"], r["contact"]]
    for heading, items in r["sections"]:
        if heading == "pagebreak":
            lines.append(None)
            continue
        lines.append(heading)
        for item in items:
            kind = item[0]
            if kind == "entry":
                _, left, right, sub = item
                lines.append(f"{left}   {right}")
                if sub:
                    lines.append(sub)
            elif kind == "bullets":
                lines.extend("• " + b for b in item[1])
            elif kind == "skills":
                lines.extend(f"• {cat}: {text}" for cat, text in item[1])
            elif kind == "project":
                _, title, stack, link, year, bullets = item
                lines.append(f"{title} | {stack}   {year}")
                lines.append(link)
                lines.extend("• " + b for b in bullets)
    return lines


def as_text(r):
    return "\n".join(line for line in as_lines(r) if line is not None) + "\n"


# ------------------------------------------------------------------ text PDF (reportlab)

INK = colors.HexColor("#1f2933")
ACCENT = colors.HexColor("#1d4ed8")
MUTED = colors.HexColor("#52606d")


def styles():
    base = dict(fontName="Helvetica", fontSize=9.6, leading=12.6, textColor=INK)
    return {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=20, leading=24, alignment=TA_CENTER, textColor=INK),
        "headline": ParagraphStyle("headline", fontName="Helvetica", fontSize=10.5, leading=14, alignment=TA_CENTER, textColor=MUTED),
        "contact": ParagraphStyle("contact", fontName="Helvetica", fontSize=9, leading=12, alignment=TA_CENTER, textColor=MUTED),
        "heading": ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=ACCENT, spaceBefore=7),
        "body": ParagraphStyle("body", **base),
        "bold": ParagraphStyle("bold", **dict(base, fontName="Helvetica-Bold")),
        "right": ParagraphStyle("right", **dict(base, alignment=2, textColor=MUTED)),
        "link": ParagraphStyle("link", **dict(base, fontSize=8.6, textColor=MUTED)),
        "bullet": ParagraphStyle("bullet", **dict(base, leftIndent=11, bulletIndent=2)),
    }


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def two_col(left, right, st, left_style="bold"):
    t = Table([[Paragraph(esc(left), st[left_style]), Paragraph(esc(right), st["right"])]],
              colWidths=[132 * mm, 42 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def write_text_pdf(r, path):
    st = styles()
    story = [Paragraph(esc(r["name"]), st["name"]), Paragraph(esc(r["headline"]), st["headline"]),
             Paragraph(esc(r["contact"]), st["contact"]), Spacer(1, 4)]
    for heading, items in r["sections"]:
        if heading == "pagebreak":
            story.append(PageBreak())
            continue
        block = [Paragraph(esc(heading), st["heading"]),
                 HRFlowable(width="100%", thickness=0.7, color=ACCENT, spaceBefore=1, spaceAfter=3)]
        for item in items:
            kind = item[0]
            if kind == "entry":
                _, left, right, sub = item
                block.append(two_col(left, right, st))
                if sub:
                    block.append(Paragraph(esc(sub), st["body"]))
                block.append(Spacer(1, 2))
            elif kind == "bullets":
                block.extend(Paragraph(esc(b), st["bullet"], bulletText="•") for b in item[1])
            elif kind == "skills":
                block.extend(Paragraph(f"<b>{esc(cat)}:</b> {esc(text)}", st["bullet"], bulletText="•")
                             for cat, text in item[1])
            elif kind == "project":
                _, title, stack, link, year, bullets = item
                block.append(two_col(f"{title} | {stack}", year, st))
                block.append(Paragraph(esc(link), st["link"]))
                block.extend(Paragraph(esc(b), st["bullet"], bulletText="•") for b in bullets)
                block.append(Spacer(1, 3))
        story.append(KeepTogether(block[:4]))
        story.extend(block[4:])
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=14 * mm,
                            bottomMargin=14 * mm, title=f"{r['name']} – Resume", author=r["name"])
    doc.build(story)


# ------------------------------------------------------------------ scanned PDF (image only)

def _font(size, bold=False):
    names = ["arialbd.ttf" if bold else "arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
             "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"]
    for name in names:
        for folder in ("", "C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu",
                       "/usr/share/fonts/truetype/liberation", "/Library/Fonts"):
            try:
                return ImageFont.truetype(os.path.join(folder, name) if folder else name, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def write_scanned_pdf(r, path, dpi=200):
    """Render the resume as a slightly skewed, noisy greyscale scan saved as an image-only PDF."""
    rng = random.Random(3)
    w, h = int(8.27 * dpi), int(11.69 * dpi)
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    margin, y = int(0.75 * dpi), int(0.6 * dpi)
    headings = {s for s, _ in r["sections"]}
    for i, line in enumerate(l for l in as_lines(r) if l is not None):
        if i == 0:
            font, gap = _font(int(dpi * 0.24), True), int(dpi * 0.36)
        elif line in headings:
            y += int(dpi * 0.08)
            font, gap = _font(int(dpi * 0.13), True), int(dpi * 0.24)
        else:
            font, gap = _font(int(dpi * 0.105)), int(dpi * 0.19)
        draw.text((margin, y), line, fill=30, font=font)
        if line in headings:
            draw.line((margin, y + gap - 6, w - margin, y + gap - 6), fill=90, width=2)
        y += gap
    for _ in range(5000):   # scanner speckle
        draw.point((rng.randrange(w), rng.randrange(h)), fill=rng.randrange(120, 230))
    img = img.rotate(0.6, resample=Image.BICUBIC, expand=False, fillcolor=255).filter(ImageFilter.GaussianBlur(0.5))
    img.save(path, "PDF", resolution=dpi)


# ------------------------------------------------------------------ main

def main():
    os.makedirs(OUT, exist_ok=True)
    for rid, r in RESUMES.items():
        pdf_path = os.path.join(OUT, f"{rid}.pdf")
        if rid in SCANNED:
            write_scanned_pdf(r, pdf_path)
        else:
            write_text_pdf(r, pdf_path)
        with open(os.path.join(OUT, f"{rid}.txt"), "w", encoding="utf-8") as f:
            f.write(as_text(r))
        print(f"{rid}: {r['name']:<15} {os.path.relpath(pdf_path)} ({os.path.getsize(pdf_path) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
