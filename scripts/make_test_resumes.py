"""Generate the six team-authored test resumes (blueprint section 22.1) into tests/resumes/.

All people, employers and contact details are fictional.

    pip install fpdf2 Pillow
    python scripts/make_test_resumes.py

Writes R1..R6 as PDF plus a .txt with the same text (used by the local scoring tests).
R3 is an image-only PDF (no text layer), so Textract has to OCR it.
"""

import os
import random
import sys

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "resumes")

# Each resume: list of pages; each page: list of (kind, text). kind: name | contact | heading | line
R1 = [[
    ("name", "Ananya Rao"),
    ("contact", "ananya.rao@example.com  |  +91 90000 00001  |  Hyderabad"),
    ("heading", "SUMMARY"),
    ("line", "Cloud engineer with 3 years of experience building and running services on AWS."),
    ("heading", "EXPERIENCE"),
    ("line", "Cloud Engineer, Northwind Software Pvt Ltd   Jul 2022 - Jun 2025"),
    ("line", "- Built Python automation for AWS EC2, S3 and Lambda deployments."),
    ("line", "- Containerised six services with Docker and ran them on Linux hosts."),
    ("line", "- Wrote SQL reports on a MySQL database for the operations team."),
    ("heading", "SKILLS"),
    ("line", "Python, AWS, Docker, Linux, SQL, Git, Bash, REST APIs"),
    ("heading", "EDUCATION"),
    ("line", "B.Tech in Computer Science, Riverside Institute of Technology   2018 - 2022"),
    ("heading", "CERTIFICATIONS"),
    ("line", "AWS Certified Cloud Practitioner"),
]]

R2 = [[
    ("name", "Rohit Varma"),
    ("contact", "rohit.varma@example.com  |  +91 90000 00002  |  Bengaluru"),
    ("heading", "PROFILE"),
    ("line", "DevOps-minded developer, 2 years in industry."),
    ("heading", "WORK EXPERIENCE"),
    ("line", "Software Developer, Bluepeak Labs   Aug 2023 - Aug 2025"),
    ("line", "- Wrote Python3 scripts and JS dashboards for internal tooling."),
    ("line", "- Deployed services on Amazon Web Services using docker-compose."),
    ("line", "- Administered Ubuntu and RHEL servers; tuned PL/SQL queries."),
    ("heading", "TECHNICAL SKILLS"),
    ("line", "Python3, JS, Amazon Web Services, docker-compose, Ubuntu, RHEL, PL/SQL"),
    ("heading", "EDUCATION"),
    ("line", "Diploma in Computer Engineering, City Polytechnic   2020 - 2023"),
]]

R3 = [[
    ("name", "Kavya Menon"),
    ("contact", "kavya.menon@example.com  |  +91 90000 00003  |  Chennai"),
    ("heading", "SUMMARY"),
    ("line", "Cloud engineer with 3 years of experience on AWS."),
    ("heading", "EXPERIENCE"),
    ("line", "Cloud Engineer, Harbourline Systems   Jun 2022 - May 2025"),
    ("line", "- Automated AWS infrastructure with Python and Bash."),
    ("line", "- Packaged applications with Docker on Linux servers."),
    ("line", "- Maintained SQL schemas and backups."),
    ("heading", "SKILLS"),
    ("line", "Python, AWS, Docker, Linux, SQL"),
    ("heading", "EDUCATION"),
    ("line", "B.Tech in Information Technology, Lakeside College of Engineering   2018 - 2022"),
]]

R4 = [[
    ("name", "Imran Shaik"),
    ("contact", "imran.shaik@example.com  |  +91 90000 00004  |  Vijayawada"),
    ("heading", "OBJECTIVE"),
    ("line", "Junior developer looking for a cloud internship."),
    ("heading", "EXPERIENCE"),
    ("line", "Junior Developer, Greenfield Retail   Jan 2025 - Jan 2026"),
    ("line", "- Wrote Python scripts to clean sales data."),
    ("line", "- Built SQL queries for weekly reports."),
    ("heading", "SKILLS"),
    ("line", "Python, SQL, Microsoft Excel, Communication"),
    ("heading", "EDUCATION"),
    ("line", "Higher Secondary Certificate (Class 12), State Board   2020 - 2022"),
]]

R5 = [[
    ("name", "Sneha Kulkarni"),
    ("contact", "sneha.kulkarni@example.com  |  +91 90000 00005  |  Pune"),
    ("heading", "SUMMARY"),
    ("line", "Mechanical design engineer with 5 years of experience in product design."),
    ("heading", "EXPERIENCE"),
    ("line", "Design Engineer, Apex Motors   Jun 2019 - May 2024"),
    ("line", "- Modelled gearbox housings in SolidWorks and AutoCAD."),
    ("line", "- Ran structural simulations in ANSYS and MATLAB."),
    ("heading", "SKILLS"),
    ("line", "SolidWorks, AutoCAD, ANSYS, MATLAB, CATIA, Teamwork"),
    ("heading", "EDUCATION"),
    ("line", "M.Tech in Machine Design, Western University of Engineering   2017 - 2019"),
]]

R6 = [
    [
        ("name", "Arjun Reddy"),
        ("contact", "arjun.reddy@example.com  |  +91 90000 00006  |  Warangal"),
        ("heading", "SUMMARY"),
        ("line", "Cloud engineer with 3 years of experience. Technical skills are listed on page 2."),
        ("heading", "EXPERIENCE"),
        ("line", "Cloud Engineer, Silverline Tech   Aug 2022 - Jul 2025"),
        ("line", "- Owned build pipelines and on-call rotation for a payments team."),
        ("line", "- Reduced deployment time from 40 minutes to 8 minutes."),
        ("line", "- Mentored two interns."),
        ("heading", "EDUCATION"),
        ("line", "B.Tech in Computer Science, Eastgate Institute of Technology   2018 - 2022"),
    ],
    [
        ("heading", "SKILLS"),
        ("line", "Languages: Python, SQL"),
        ("line", "Cloud: AWS (EC2, S3, Lambda, DynamoDB)"),
        ("line", "Platforms: Docker, Linux"),
        ("heading", "PROJECTS"),
        ("line", "Serverless file converter on AWS Lambda   Jan 2024 - Mar 2024"),
        ("line", "Container monitoring dashboard with Docker and Grafana   Sep 2024 - Nov 2024"),
    ],
]

RESUMES = {"R1": R1, "R2": R2, "R3": R3, "R4": R4, "R5": R5, "R6": R6}
SCANNED = {"R3"}


def as_text(pages):
    return "\n".join(text for page in pages for _, text in page) + "\n"


def write_text_pdf(pages, path):
    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(False)
    for page in pages:
        pdf.add_page()
        for kind, text in page:
            if kind == "name":
                pdf.set_font("Helvetica", "B", 20)
                pdf.cell(0, 11, text, new_x="LMARGIN", new_y="NEXT")
            elif kind == "contact":
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
            elif kind == "heading":
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.set_font("Helvetica", "", 11)
                pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
    pdf.output(path)


def _font(size, bold=False):
    candidates = ["arialbd.ttf" if bold else "arial.ttf",
                  "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
                  "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"]
    for name in candidates:
        for folder in ("", "C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu",
                       "/usr/share/fonts/truetype/liberation", "/Library/Fonts"):
            try:
                return ImageFont.truetype(os.path.join(folder, name) if folder else name, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def write_scanned_pdf(pages, path, dpi=200):
    """Render each page to a slightly skewed, noisy greyscale image and save as an image-only PDF."""
    rng = random.Random(3)
    w, h = int(8.27 * dpi), int(11.69 * dpi)
    images = []
    for page in pages:
        img = Image.new("L", (w, h), 255)
        draw = ImageDraw.Draw(img)
        y = int(0.8 * dpi)
        x = int(0.8 * dpi)
        for kind, text in page:
            if kind == "name":
                font, gap = _font(int(dpi * 0.26), True), int(dpi * 0.42)
            elif kind == "heading":
                y += int(dpi * 0.12)
                font, gap = _font(int(dpi * 0.16), True), int(dpi * 0.3)
            else:
                font, gap = _font(int(dpi * 0.14)), int(dpi * 0.26)
            draw.text((x, y), text, fill=25, font=font)
            y += gap
        for _ in range(4000):  # scanner speckle
            draw.point((rng.randrange(w), rng.randrange(h)), fill=rng.randrange(120, 230))
        img = img.rotate(0.7, resample=Image.BICUBIC, expand=False, fillcolor=255)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
        images.append(img)
    images[0].save(path, "PDF", resolution=dpi, save_all=True, append_images=images[1:])


def main():
    os.makedirs(OUT, exist_ok=True)
    for rid, pages in RESUMES.items():
        pdf_path = os.path.join(OUT, f"{rid}.pdf")
        if rid in SCANNED:
            write_scanned_pdf(pages, pdf_path)
        else:
            write_text_pdf(pages, pdf_path)
        with open(os.path.join(OUT, f"{rid}.txt"), "w", encoding="utf-8") as f:
            f.write(as_text(pages))
        print(f"{rid}: {os.path.relpath(pdf_path)} ({os.path.getsize(pdf_path) // 1024} KB, {len(pages)} page(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
