"""Draw the ResumeRank architecture diagram from one layout definition.

    python scripts/draw_architecture.py

Writes
  docs/architecture.drawio  – editable in app.diagrams.net, official AWS (aws4) icons
  docs/architecture.png     – the same layout rendered with Pillow, for the report and README
"""

import os
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 180, 92                     # node size

# category colours from the AWS architecture icon set
COLOURS = {
    "compute": "#ED7100", "storage": "#7AA116", "database": "#C925D1", "integration": "#E7157B",
    "ml": "#01A88D", "network": "#8C4FFF", "management": "#E7157B", "security": "#DD344C",
    "external": "#232F3E",
}

# id: (x, y, title, subtitle, category, aws4 icon)
NODES = {
    "users":    (30, 350, "Users", "recruiters & candidates", "external", "users"),
    "site":     (300, 140, "Amazon S3", "static website (4 pages)", "storage", "s3"),
    "apigw":    (570, 140, "API Gateway", "HTTP API · 8 routes · throttled", "network", "api_gateway"),
    "api":      (840, 140, "AWS Lambda", "api_handler", "compute", "lambda"),
    "ddb":      (1110, 350, "Amazon DynamoDB", "Jobs · Candidates · ScoreIndex", "database", "dynamodb"),
    "resumes":  (300, 560, "Amazon S3", "resumes bucket (private)", "storage", "s3"),
    "sqs":      (570, 560, "Amazon SQS", "queue · batch 1 · max 5", "integration", "sqs"),
    "dlq":      (570, 770, "Amazon SQS", "resumerank-dlq (dead letters)", "integration", "sqs"),
    "proc":     (840, 560, "AWS Lambda", "process_resume (auto-scales)", "compute", "lambda"),
    "ai":       (840, 770, "Textract · Comprehend", "OCR + NLP (pypdf fallback)", "ml", "textract"),
    "sns":      (1110, 560, "Amazon SNS", "resumerank-alerts", "integration", "sns"),
    "mail":     (1380, 560, "Recruiter inbox", "alert email (score ≥ 75)", "external", "email"),
    "iam":      (1380, 140, "AWS IAM", "role-api · role-processor", "security", "identity_and_access_management"),
    "cw":       (1380, 350, "Amazon CloudWatch", "logs · metrics · dashboard", "management", "cloudwatch_2"),
}

# (from, to, label, waypoints, dashed) – waypoints are absolute points between the two ends
EDGES = [
    ("users", "site", "1  load pages", [(250, 380), (250, 186)], False),
    ("site", "apigw", "2  fetch() + CORS", [], False),
    ("apigw", "api", "3  invoke", [], False),
    ("api", "ddb", "4  jobs, leaderboard, decisions", [(930, 395)], False),
    ("users", "resumes", "5  PUT PDF (pre-signed URL)", [(250, 410), (250, 606)], False),
    ("resumes", "sqs", "6  ObjectCreated", [], False),
    ("sqs", "proc", "7  poll", [], False),
    ("sqs", "dlq", "after 3 failures", [], True),
    ("proc", "ai", "8  text + entities", [], False),
    ("proc", "ddb", "9  score → SCORED / FAILED", [(970, 480), (1200, 480)], False),
    ("proc", "sns", "10  score ≥ 75", [], False),
    ("sns", "mail", "email", [], False),
]


def anchor(node, toward):
    """Point on the node's border facing `toward`."""
    x, y = NODES[node][0], NODES[node][1]
    cx, cy = x + W / 2, y + H / 2
    tx, ty = toward
    if abs(tx - cx) * H >= abs(ty - cy) * W:
        return (x + W if tx > cx else x, cy if not (y <= ty <= y + H) else ty)
    return (cx if not (x <= tx <= x + W) else tx, y + H if ty > cy else y)


def path(edge):
    a, b, _, pts, _ = edge
    first = pts[0] if pts else (NODES[b][0] + W / 2, NODES[b][1] + H / 2)
    last = pts[-1] if pts else (NODES[a][0] + W / 2, NODES[a][1] + H / 2)
    return [anchor(a, first), *pts, anchor(b, last)]


# ---------------------------------------------------------------- draw.io

def drawio():
    cells, n = [], 2

    def cell(xml):
        nonlocal n
        cells.append(xml.replace("{id}", f"c{n}"))
        n += 1
        return f"c{n - 1}"

    cell('<mxCell id="{id}" value="AWS Cloud" style="points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=13;fontStyle=1;'
         'container=1;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_aws_cloud_alt;'
         'strokeColor=#232F3E;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#232F3E;dashed=0;" vertex="1" parent="1">'
         '<mxGeometry x="270" y="60" width="1320" height="840" as="geometry"/></mxCell>')
    cell('<mxCell id="{id}" value="Region ap-south-1 (Mumbai)" style="points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;'
         'container=1;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_region;'
         'strokeColor=#00A4A6;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#147EBA;dashed=1;" vertex="1" parent="1">'
         '<mxGeometry x="285" y="95" width="1290" height="790" as="geometry"/></mxCell>')
    ids = {}
    for key, (x, y, title, sub, cat, icon) in NODES.items():
        colour = COLOURS[cat]
        if icon in ("users", "email"):
            shape = f"shape=mxgraph.aws4.{'users' if icon == 'users' else 'email_2'};fillColor=#232F3E;strokeColor=none;"
        else:
            shape = (f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{icon};"
                     f"fillColor={colour};strokeColor=#ffffff;gradientColor=none;")
        label = f"<b>{escape(title)}</b><br>{escape(sub)}"
        ids[key] = cell(
            f'<mxCell id="{{id}}" value="{escape(label, {chr(34): "&quot;"})}" style="sketch=0;outlineConnect=0;fontColor=#232F3E;'
            f'dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=11;aspect=fixed;{shape}" '
            f'vertex="1" parent="1"><mxGeometry x="{x + W / 2 - 28}" y="{y}" width="56" height="56" as="geometry"/></mxCell>')
    for a, b, label, pts, dashed in EDGES:
        points = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in pts)
        geo = f'<mxGeometry relative="1" as="geometry"><Array as="points">{points}</Array></mxGeometry>' if pts \
            else '<mxGeometry relative="1" as="geometry"/>'
        cell(f'<mxCell id="{{id}}" value="{escape(label)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;'
             f'strokeColor=#545B64;fontSize=10;labelBackgroundColor=#ffffff;{"dashed=1;" if dashed else ""}" edge="1" parent="1" '
             f'source="{ids[a]}" target="{ids[b]}">{geo}</mxCell>')
    cell('<mxCell id="{id}" value="Security &amp; observability apply to every component: least-privilege IAM roles, private bucket, '
         'pre-signed URLs, recruiter access key; CloudWatch logs for every invocation, custom metric ResumeRank/CandidateScore, dashboard." '
         'style="text;html=1;whiteSpace=wrap;fontSize=11;fontColor=#545B64;align=left;" vertex="1" parent="1">'
         '<mxGeometry x="1340" y="460" width="230" height="80" as="geometry"/></mxCell>')
    xml = ('<mxfile host="app.diagrams.net"><diagram name="ResumeRank architecture" id="resumerank">'
           '<mxGraphModel dx="1600" dy="920" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
           'fold="1" page="1" pageScale="1" pageWidth="1654" pageHeight="1000" math="0" shadow="0"><root>'
           '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>\n")
    with open(os.path.join(ROOT, "docs", "architecture.drawio"), "w", encoding="utf-8") as f:
        f.write(xml)


# ---------------------------------------------------------------- PNG

def font(size, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")):
        for folder in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", ""):
            try:
                return ImageFont.truetype(os.path.join(folder, name) if folder else name, size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


def png():
    S = 2                                           # render at 2x for a crisp image
    img = Image.new("RGB", (1620 * S, 920 * S), "white")
    d = ImageDraw.Draw(img)
    f_title, f_sub, f_label, f_group, f_head = font(15 * S, True), font(12 * S), font(11 * S), font(13 * S, True), font(20 * S, True)
    s = lambda *v: [int(round(c * S)) for c in v]   # noqa: E731

    d.text(s(30, 18), "ResumeRank – serverless resume screening on AWS", font=f_head, fill="#232F3E")
    d.rounded_rectangle(s(270, 60, 1590, 900), radius=6 * S, outline="#232F3E", width=2 * S)
    d.text(s(285, 68), "AWS Cloud", font=f_group, fill="#232F3E")
    for x in range(285, 1575, 14):                  # dashed region border
        d.line(s(x, 95, min(x + 7, 1575), 95), fill="#00A4A6", width=2 * S)
        d.line(s(x, 885, min(x + 7, 1575), 885), fill="#00A4A6", width=2 * S)
    for y in range(95, 885, 14):
        d.line(s(285, y, 285, min(y + 7, 885)), fill="#00A4A6", width=2 * S)
        d.line(s(1575, y, 1575, min(y + 7, 885)), fill="#00A4A6", width=2 * S)
    d.text(s(300, 102), "Region ap-south-1 (Mumbai)", font=f_label, fill="#147EBA")

    def arrow(points, label, dashed):
        pts = [tuple(s(*p)) for p in points]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if dashed:
                length = max(abs(x2 - x1), abs(y2 - y1))
                for t in range(0, length, 14 * S):
                    a, b = t / length, min(t + 7 * S, length) / length
                    d.line([(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a), (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)], fill="#545B64", width=2 * S)
            else:
                d.line([(x1, y1), (x2, y2)], fill="#545B64", width=2 * S)
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        dx, dy = (x2 > x1) - (x2 < x1), (y2 > y1) - (y2 < y1)
        k = 9 * S
        d.polygon([(x2, y2), (x2 - dx * k - dy * k / 2, y2 - dy * k - dx * k / 2),
                   (x2 - dx * k + dy * k / 2, y2 - dy * k + dx * k / 2)], fill="#545B64")
        # label on the longest segment
        seg = max(zip(pts, pts[1:]), key=lambda p: abs(p[1][0] - p[0][0]) + abs(p[1][1] - p[0][1]))
        mx, my = (seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2
        tw = d.textlength(label, font=f_label)
        if seg[0][1] == seg[1][1]:                  # horizontal: label above the line
            box = (mx - tw / 2 - 4 * S, my - 20 * S, mx + tw / 2 + 4 * S, my - 4 * S)
        else:                                       # vertical: label to the right
            box = (mx + 6 * S, my - 8 * S, mx + tw + 14 * S, my + 8 * S)
        d.rectangle(box, fill="white")
        d.text((box[0] + 4 * S, box[1] + 1 * S), label, font=f_label, fill="#232F3E")

    for edge in EDGES:
        arrow(path(edge), edge[2], edge[4])

    for key, (x, y, title, sub, cat, _) in NODES.items():
        colour = COLOURS[cat]
        d.rounded_rectangle(s(x, y, x + W, y + H), radius=8 * S, fill="white", outline=colour, width=2 * S)
        d.rounded_rectangle(s(x, y, x + W, y + 8), radius=4 * S, fill=colour)
        d.rectangle(s(x, y + 4, x + W, y + 8), fill=colour)
        for text, f, yy, col in ((title, f_title, y + 26, "#232F3E"), (sub, f_sub, y + 52, "#545B64")):
            tw = d.textlength(text, font=f)
            if tw > (W - 10) * S:                   # shrink long subtitles
                f = font(10 * S)
                tw = d.textlength(text, font=f)
            d.text((s(x + W / 2)[0] - tw / 2, s(yy)[0]), text, font=f, fill=col)

    note = ["Applies to every component:", "• least-privilege IAM roles", "• private bucket, pre-signed URLs",
            "• recruiter access key", "• CloudWatch logs + custom metric", "• Rs. 0 – AWS Free Tier only"]
    for i, line in enumerate(note):
        d.text(s(1385, 455 + i * 17), line, font=f_label if i else font(11 * S, True), fill="#545B64")

    img = img.resize((1620, 920), Image.LANCZOS)
    img.save(os.path.join(ROOT, "docs", "architecture.png"), optimize=True)


if __name__ == "__main__":
    drawio()
    png()
    print("wrote docs/architecture.drawio and docs/architecture.png")
