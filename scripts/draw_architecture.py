"""Draw the ResumeRank architecture diagram in the AWS reference-architecture style.

    python scripts/draw_architecture.py

Writes
  docs/architecture.drawio  – editable in app.diagrams.net, official AWS (aws4) icons
  docs/architecture.png     – rendered from the same file by the draw.io viewer in headless
                              Chrome/Edge (needs internet access for viewer.diagrams.net)
"""

import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = 78                               # icon size, as in the AWS icon set
CANVAS_W, CANVAS_H = 1700, 1060

COLOUR = {"storage": "#7AA116", "network": "#8C4FFF", "compute": "#ED7100", "database": "#C925D1",
          "integration": "#E7157B", "ml": "#01A88D", "management": "#E7157B", "security": "#DD344C",
          "frontend": "#DD344C"}

# id: (x, y, label, category, aws4 resource icon)
ICONS = {
    "site":    (330, 190, "AWS Amplify Hosting<br>website over HTTPS", "frontend", "amplify"),
    "apigw":   (580, 190, "Amazon API Gateway<br>HTTP API · throttled", "network", "api_gateway"),
    "api":     (830, 190, "AWS Lambda<br>api_handler", "compute", "lambda"),
    "ddb":     (1080, 440, "Amazon DynamoDB<br>Jobs · Candidates", "database", "dynamodb"),
    "resumes": (330, 680, "Amazon S3<br>resumes (private)", "storage", "s3"),
    "sqs":     (580, 680, "Amazon SQS<br>upload queue", "integration", "sqs"),
    "dlq":     (580, 900, "Amazon SQS<br>dead-letter queue", "integration", "sqs"),
    "proc":    (830, 680, "AWS Lambda<br>process_resume", "compute", "lambda"),
    "textract": (770, 900, "Amazon Textract", "ml", "textract"),
    "comprehend": (900, 900, "Amazon Comprehend", "ml", "comprehend"),
    "sns":     (1080, 680, "Amazon SNS<br>alerts", "integration", "sns"),
    "iam":     (1310, 210, "AWS IAM<br>least-privilege roles", "security", "identity_and_access_management"),
    "cw":      (1480, 210, "Amazon CloudWatch<br>logs · metric · dashboard", "management", "cloudwatch_2"),
}
PLAIN = {   # icons that are not service tiles
    "users": (90, 445, "Recruiters &amp;<br>candidates", "shape=mxgraph.aws4.users;fillColor=#232F3E;strokeColor=none;"),
    "mail":  (1330, 686, "Recruiter<br>email", "shape=mxgraph.aws4.email_2;fillColor=#E7157B;strokeColor=none;"),
}

# (x, y, w, h, title, dashed, icon)
GROUPS = [
    (20, 20, 1660, 1020, "AWS Cloud", False, "group_aws_cloud_alt"),
    (230, 80, 1430, 945, "Region ap-south-1 (Mumbai)", True, "group_region"),
    (290, 130, 690, 200, "Request path", True, None),
    (290, 620, 690, 200, "Event path", True, None),
    (740, 850, 270, 160, "Managed AI (fallback: PDF text layer)", True, None),
    (1270, 140, 370, 230, "Security &amp; monitoring", True, None),
]

# (source, target, (exitX, exitY), (entryX, entryY), waypoints, dashed, label)
EDGES = [
    ("users", "site", (1, 0.3), (0, 0.5), [(260, 468), (260, 229)], False, ""),
    ("site", "apigw", (1, 0.5), (0, 0.5), [], False, ""),
    ("apigw", "api", (1, 0.5), (0, 0.5), [], False, ""),
    ("api", "ddb", (1, 0.5), (0.5, 0), [(1119, 229)], False, ""),
    ("users", "resumes", (1, 0.7), (0, 0.5), [(260, 500), (260, 719)], False, ""),
    ("resumes", "sqs", (1, 0.5), (0, 0.5), [], False, ""),
    ("sqs", "proc", (1, 0.5), (0, 0.5), [], False, ""),
    ("proc", "textract", (1, 0.85), (0.5, 0), [(1000, 746), (1000, 885), (809, 885)], False, ""),
    ("proc", "ddb", (0.5, 0), (0, 0.5), [(869, 479)], False, ""),
    ("proc", "sns", (1, 0.5), (0, 0.5), [], False, ""),
    ("sns", "mail", (1, 0.5), (0, 0.5), [], False, ""),
    ("sqs", "dlq", (0, 0.85), (0, 0.5), [(545, 746), (545, 939)], True, "after 3<br>failures"),
]

# numbered steps: (number, centre x, centre y)
STEPS = [(1, 280, 345), (2, 455, 195), (3, 705, 195), (4, 1150, 340), (5, 280, 610),
         (6, 455, 685), (7, 705, 685), (8, 1030, 815), (9, 840, 560), (10, 960, 685), (11, 1210, 685)]

LEGEND = [
    "1  Users open the website over HTTPS (Amplify)",
    "2  Pages call the API (CORS, throttling)",
    "3  API Gateway invokes api_handler",
    "4  Jobs, leaderboard, decisions in DynamoDB",
    "5  Browser PUTs the PDF with a pre-signed URL",
    "6  S3 sends ObjectCreated to the SQS queue",
    "7  Lambda scales out to drain the queue (max 5)",
    "8  Text + entities (Textract / Comprehend, or pypdf)",
    "9  Score written: SCORED or FAILED",
    "10  Score ≥ the job's alert threshold publishes an alert",
    "11  Recruiter receives the email",
]


def build_xml():
    cells, n = [], [2]

    def add(xml):
        cid = f"c{n[0]}"
        n[0] += 1
        cells.append(xml.replace("{id}", cid))
        return cid

    for x, y, w, h, title, dashed, icon in GROUPS:
        if icon:
            colour = "#232F3E" if icon == "group_aws_cloud_alt" else "#00A4A6"
            font = "#232F3E" if icon == "group_aws_cloud_alt" else "#147EBA"
            style = (f"points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=15;"
                     f"fontStyle=0;container=1;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;"
                     f"grIcon=mxgraph.aws4.{icon};strokeColor={colour};fillColor=none;verticalAlign=top;align=left;"
                     f"spacingLeft=30;fontColor={font};dashed={1 if dashed else 0};strokeWidth=2;")
        else:
            style = ("fillColor=none;strokeColor=#5A6C86;dashed=1;verticalAlign=top;fontStyle=0;fontColor=#232F3E;"
                     "whiteSpace=wrap;html=1;fontSize=13;align=center;")
        add(f'<mxCell id="{{id}}" value="{escape(title)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

    ids = {}
    for key, (x, y, label, cat, icon) in ICONS.items():
        style = (f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor={COLOUR[cat]};"
                 f"strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;"
                 f"fontSize=13;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{icon};")
        ids[key] = add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
                       f'<mxGeometry x="{x}" y="{y}" width="{SIZE}" height="{SIZE}" as="geometry"/></mxCell>')
    for key, (x, y, label, shape) in PLAIN.items():
        style = (f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;dashed=0;verticalLabelPosition=bottom;"
                 f"verticalAlign=top;align=center;html=1;fontSize=13;aspect=fixed;{shape}")
        ids[key] = add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
                       f'<mxGeometry x="{x}" y="{y}" width="{SIZE - 12}" height="{SIZE - 12}" as="geometry"/></mxCell>')

    for src, dst, (ex, ey), (nx, ny), pts, dashed, label in EDGES:
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=open;endFill=0;endSize=9;strokeWidth=2;"
                 f"strokeColor=#232F3E;fontSize=12;fontColor=#232F3E;labelBackgroundColor=#ffffff;"
                 f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
                 f"{'dashed=1;' if dashed else ''}")
        points = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in pts)
        geo = (f'<mxGeometry relative="1" as="geometry"><Array as="points">{points}</Array></mxGeometry>'
               if pts else '<mxGeometry relative="1" as="geometry"/>')
        add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" edge="1" parent="1" '
            f'source="{ids[src]}" target="{ids[dst]}">{geo}</mxCell>')

    for num, cx, cy in STEPS:
        d = 34
        add(f'<mxCell id="{{id}}" value="{num}" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#232F3E;'
            f'strokeColor=none;fontColor=#FFFFFF;fontStyle=1;fontSize=15;" vertex="1" parent="1">'
            f'<mxGeometry x="{cx - d / 2}" y="{cy - d / 2}" width="{d}" height="{d}" as="geometry"/></mxCell>')

    legend = "<b>Flow</b><br>" + "<br>".join(escape(line) for line in LEGEND)
    add(f'<mxCell id="{{id}}" value="{escape(legend)}" style="text;html=1;whiteSpace=wrap;fontSize=12;fontColor=#232F3E;'
        f'align=left;verticalAlign=top;spacing=6;" vertex="1" parent="1">'
        f'<mxGeometry x="1280" y="790" width="370" height="225" as="geometry"/></mxCell>')
    add('<mxCell id="{id}" value="HTTPS via Amplify · private resumes bucket · pre-signed URLs · recruiter access key · '
        'CORS limited to the site · Rs. 0 on the AWS Free Tier" style="text;html=1;whiteSpace=wrap;fontSize=12;'
        'fontColor=#545B64;align=center;" vertex="1" parent="1"><mxGeometry x="1280" y="380" width="350" height="44" as="geometry"/></mxCell>')

    model = ('<mxGraphModel dx="1700" dy="1060" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
             f'fold="1" page="1" pageScale="1" pageWidth="{CANVAS_W}" pageHeight="{CANVAS_H}" math="0" shadow="0">'
             '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel>")
    return model


def browser():
    for c in (shutil.which("chrome"), shutil.which("msedge"),
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              shutil.which("google-chrome"), shutil.which("chromium")):
        if c and os.path.exists(c):
            return c
    return None


def render_png(model, out):
    exe = browser()
    if not exe:
        print("no Chrome/Edge found – open docs/architecture.drawio in app.diagrams.net and export PNG")
        return False
    config = json.dumps({"lightbox": False, "nav": False, "toolbar": "", "border": 0, "xml": model})
    page = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>html,body{margin:0;background:#fff}"
            ".mxgraph{width:%dpx}</style></head><body><div class='mxgraph' data-mxgraph=\"%s\"></div>"
            "<script src='https://viewer.diagrams.net/js/viewer-static.min.js'></script></body></html>"
            % (CANVAS_W, html.escape(config, quote=True)))
    tmp = tempfile.mkdtemp(prefix="rr-diagram-")
    try:
        src = os.path.join(tmp, "diagram.html")
        with open(src, "w", encoding="utf-8") as f:
            f.write(page)
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                        "--virtual-time-budget=20000", f"--window-size={CANVAS_W},{CANVAS_H}",
                        f"--screenshot={out}", "file:///" + src.replace("\\", "/")],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return os.path.exists(out)


def main():
    model = build_xml()
    drawio = os.path.join(ROOT, "docs", "architecture.drawio")
    with open(drawio, "w", encoding="utf-8") as f:
        f.write('<mxfile host="app.diagrams.net"><diagram name="ResumeRank architecture" id="resumerank">'
                + model + "</diagram></mxfile>\n")
    print("wrote docs/architecture.drawio")
    if "--no-png" not in sys.argv and render_png(model, os.path.join(ROOT, "docs", "architecture.png")):
        print("wrote docs/architecture.png")


if __name__ == "__main__":
    main()
