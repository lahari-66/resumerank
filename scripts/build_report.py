"""Merge docs/report/sections/*.md into one printable report.

    pip install markdown
    python scripts/build_report.py           # docs/report/report.html
    python scripts/build_report.py --pdf     # also docs/report/report.pdf via headless Chrome/Edge

Figures are written in the sections as  [[figure: path/relative/to/docs/report | caption]].
A figure whose image file does not exist yet is rendered as a labelled placeholder box, so the
report can be built before every screenshot has been taken. Drop the PNGs into
docs/report/screenshots/ and rebuild.
"""

import html
import os
import re
import shutil
import subprocess
import sys
from datetime import date

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "docs", "report")
SECTIONS = os.path.join(REPORT, "sections")
FIGURE_RE = re.compile(r"\[\[figure:\s*([^|\]]+?)\s*\|\s*([^\]]+?)\s*\]\]")

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "Segoe UI", Calibri, Arial, sans-serif; color: #1b2433; font-size: 10pt; line-height: 1.45; max-width: 900px; margin: 0 auto; padding: 0 12px; }
h1 { font-size: 16pt; color: #0f172a; border-bottom: 2px solid #2563eb; padding-bottom: 4px; margin-top: 26px; page-break-after: avoid; }
h2 { font-size: 13pt; color: #1e3a8a; margin-top: 18px; }
h3 { font-size: 11pt; }
p, li { text-align: justify; }
table { border-collapse: collapse; width: 100%; margin: 10px 0 14px; font-size: 9.2pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #cbd5e1; padding: 5px 7px; vertical-align: top; text-align: left; }
th { background: #eef2fb; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f1f5f9; padding: 0 3px; border-radius: 3px; }
pre { background: #f1f5f9; padding: 10px 12px; border-radius: 6px; font-size: 9pt; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
figure { margin: 14px 0; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; border: 1px solid #e2e8f0; }
figcaption { font-size: 9pt; color: #5f6b7d; margin-top: 4px; }
.placeholder { border: 2px dashed #94a3b8; border-radius: 8px; padding: 22px 16px; color: #64748b; background: #f8fafc; }
.cover { text-align: center; padding-top: 120px; page-break-after: always; }
.cover .kicker { letter-spacing: 0.25em; color: #2563eb; font-size: 10pt; font-weight: 600; }
.cover .title { font-size: 34pt; font-weight: 800; color: #0f172a; margin: 18px 0 6px; }
.cover .subtitle { font-size: 15pt; color: #334155; margin-bottom: 40px; }
.cover table { width: 70%; margin: 30px auto; font-size: 10.5pt; }
.cover .note { font-size: 9pt; color: #64748b; margin-top: 60px; }
.toc { page-break-after: always; }
.toc h1 { page-break-before: avoid; }
.toc ol { font-size: 11pt; line-height: 1.9; }
.abstract h1 { page-break-before: avoid; }
@media screen { body { background: #f4f6fb; } .sheet { background: white; padding: 24px 40px; margin: 20px auto; box-shadow: 0 2px 12px rgba(0,0,0,.08); } h1 { page-break-before: auto; margin-top: 30px; } }
"""

COVER = """
<div class="cover">
  <div class="kicker">CLOUD COMPUTING · COURSE PROJECT REPORT</div>
  <div class="title">ResumeRank</div>
  <div class="subtitle">Serverless AI Resume Screening on AWS</div>
  <table>
    <tr><th>Team</th><td>M. Lahari – Backend &amp; AI Lead<br>S. Mounika Reddy – API, Frontend &amp; Operations Lead</td></tr>
    <tr><th>Platform</th><td>Amazon Web Services, region ap-south-1 (Mumbai)</td></tr>
    <tr><th>Services</th><td>S3 · API Gateway · Lambda · SQS · DynamoDB · Textract · Comprehend · SNS · CloudWatch · IAM</td></tr>
    <tr><th>Cloud cost</th><td>Rs. 0 (AWS Free Tier)</td></tr>
    <tr><th>Date</th><td>{date}</td></tr>
  </table>
  <div class="note">The score described in this report orders resumes for human review. It is not a hiring decision.
  All test resumes are fictional.</div>
</div>
"""


def figure(match):
    path, caption = match.group(1).strip(), match.group(2).strip()
    cap = html.escape(caption)
    if os.path.exists(os.path.join(REPORT, path)):
        return f'\n<figure><img src="{html.escape(path)}" alt="{cap}"><figcaption>{cap}</figcaption></figure>\n'
    return (f'\n<figure><div class="placeholder">Screenshot to add: <code>docs/report/{html.escape(path)}</code></div>'
            f'<figcaption>{cap}</figcaption></figure>\n')


def build():
    files = sorted(f for f in os.listdir(SECTIONS) if f.endswith(".md"))
    parts, toc = [], []
    for name in files:
        with open(os.path.join(SECTIONS, name), encoding="utf-8") as f:
            text = FIGURE_RE.sub(figure, f.read())
        for heading in re.findall(r"^# (.+)$", text, re.M):
            if not heading.lower().startswith("abstract"):
                toc.append(heading)
        body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
        cls = ' class="abstract"' if name.startswith("00") else ""
        parts.append(f"<section{cls}>{body}</section>")

    toc_html = "<div class='toc'><h1>Contents</h1><ol style='list-style:none;padding-left:0'>" + \
        "".join(f"<li>{html.escape(h)}</li>" for h in toc) + "</ol></div>"
    page = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>ResumeRank – Project Report</title><style>{CSS}</style></head><body><div class='sheet'>"
        + COVER.format(date=date.today().strftime("%d %B %Y"))
        + parts[0] + toc_html + "".join(parts[1:])
        + "</div></body></html>"
    )
    out = os.path.join(REPORT, "report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    missing = len(re.findall(r'class="placeholder"', page))
    print(f"wrote {os.path.relpath(out, ROOT)} ({len(files)} sections, {missing} screenshot placeholder(s) left)")
    return out


def to_pdf(html_path):
    candidates = [
        shutil.which("chrome"), shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    browser = next((c for c in candidates if c and os.path.exists(c)), None)
    if not browser:
        print("no Chrome/Edge found – open report.html and use Print -> Save as PDF")
        return
    pdf = os.path.join(REPORT, "report.pdf")
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", "file:///" + html_path.replace("\\", "/")],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    print(f"wrote {os.path.relpath(pdf, ROOT)}")


if __name__ == "__main__":
    path = build()
    if "--pdf" in sys.argv:
        to_pdf(path)
