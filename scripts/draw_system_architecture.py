"""Draw the ResumeRank *system* architecture: the layers of the system and what lives in each.

    python scripts/draw_system_architecture.py

Writes docs/system-architecture.drawio (editable in app.diagrams.net, official AWS icons) and
docs/system-architecture.png (rendered with the same headless-browser helper as
draw_architecture.py). docs/architecture.png shows the numbered request and event flow; this
diagram shows the layered structure and the responsibilities inside each layer.
"""

import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draw_architecture as base  # noqa: E402  (reuses its PNG renderer and colours)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1700, 1180
ICON = 64

# layer bands, drawn as swimlanes with the name in a vertical strip: (name, y, height, header, body)
LAYERS = [
    ("Users", 20, 120, "#E3E8EF", "#F7F9FB"),
    ("Presentation", 155, 150, "#F6D3DA", "#FDF4F6"),
    ("Application (API)", 320, 250, "#E3D7FB", "#F8F4FF"),
    ("Processing", 585, 230, "#FBDDBD", "#FFF8F0"),
    ("Data", 830, 160, "#EBD3F2", "#FBF5FD"),
    ("Cross-cutting", 1005, 155, "#CFE4F2", "#F2F8FC"),
]

# AWS icons: id: (x, y, label, colour key, resIcon, label side "right" | "top" | "none")
ICONS = {
    "amplify": (100, 198, "<b>AWS Amplify Hosting</b><br>website over HTTPS", "frontend", "amplify", "right"),
    "apigw":   (100, 345, "<b>Amazon API Gateway</b><br>HTTP API · CORS · throttling", "network", "api_gateway", "right"),
    "api":     (100, 470, "<b>AWS Lambda</b><br>api_handler", "compute", "lambda", "right"),
    "s3in":    (360, 690, "<b>Amazon S3</b><br>browser PUT (pre-signed)", "storage", "s3", "top"),
    "sqs":     (570, 690, "<b>Amazon SQS</b><br>queue + dead-letter queue", "integration", "sqs", "top"),
    "proc":    (780, 690, "<b>AWS Lambda</b><br>process_resume", "compute", "lambda", "top"),
    "ddb":     (100, 873, "<b>Amazon DynamoDB</b><br>on-demand", "database", "dynamodb", "right"),
    "s3data":  (1290, 878, "", "storage", "s3", "none"),
    "sns":     (100, 1050, "<b>Amazon SNS</b><br>score alerts · emailed shortlist", "integration", "sns", "right"),
    "cw":      (420, 1050, "<b>Amazon CloudWatch</b><br>logs · CandidateScore metric<br>dashboard · zero-spend budget", "management", "cloudwatch_2", "right"),
    "iam":     (760, 1050, "<b>AWS IAM</b><br>two least-privilege roles<br>private bucket · recruiter key", "security", "identity_and_access_management", "right"),
    "textract": (1090, 1050, "<b>Amazon Textract</b><br>OCR (pypdf fallback<br>on the Free plan)", "ml", "textract", "right"),
    "comp":    (1390, 1050, "<b>Amazon Comprehend</b><br>key phrases · entities<br>(when available)", "ml", "comprehend", "right"),
}
PEOPLE = {
    "cand": (330, 38, "Candidate"),
    "rec":  (530, 38, "Recruiter"),
}

# responsibility boxes: (x, y, w, h, title, detail)
BOXES = [
    # presentation
    (360, 175, 315, 110, "Home · Apply", "open jobs · QR / shared link · drag-and-drop PDF upload · phone layout"),
    (685, 175, 315, 110, "Track application", "live status · weighted breakdown · skill advice · re-upload a failed PDF"),
    (1010, 175, 315, 110, "Recruiter dashboard", "insights · leaderboard · charts · blind screening · compare · notes · CSV"),
    (1335, 175, 325, 110, "Shared app.js · styles.css", "API client · recruiter key · dark mode · text-only rendering"),
    # application
    (360, 340, 315, 100, "Jobs", "create · list · close / reopen · deadline · alert threshold"),
    (685, 340, 315, 100, "Uploads", "pre-signed PUT · re-upload for FAILED · duplicate (SUPERSEDED) check"),
    (1010, 340, 315, 100, "Candidates", "ranked leaderboard (ScoreIndex) · status · resume view"),
    (1335, 340, 325, 100, "Decisions", "shortlist / reject · private notes"),
    (360, 452, 315, 100, "Skill extraction", "184-skill dictionary applied to a job description"),
    (685, 452, 315, 100, "Shortlist email", "ranked shortlist with notes → SNS"),
    (1010, 452, 650, 100, "Validation & access", "recruiter key (x-recruiter-key) · PDF only, ≤ 5 MB · CORS to the site · 20 req/s, burst 50"),
    # processing
    (950, 603, 230, 95, "Text extraction", "Textract OCR, or the PDF text layer (pypdf)"),
    (1190, 603, 230, 95, "NLP enrichment", "Comprehend key phrases & entities"),
    (1430, 603, 230, 95, "Scoring engine", "per-job weights · section-aware experience · preferred bonus"),
    (950, 708, 230, 95, "Persistence", "conditional UpdateItem: SCORED / FAILED, never over SUPERSEDED"),
    (1190, 708, 230, 95, "Alerts & metrics", "SNS at the job's threshold · CandidateScore metric"),
    (1430, 708, 230, 95, "Reliability", "partial batch failures · 3 retries · DLQ · max 5 copies"),
    # data
    (360, 850, 420, 120, "Jobs table", "jobId · title · required & preferred skills · weights · minYears · deadline · status · alert threshold"),
    (795, 850, 460, 120, "Candidates table + ScoreIndex GSI", "jobId + candidateId · status · score, components, bonus · skills · decision · note · full text"),
    (1370, 850, 290, 120, "Resumes bucket (S3)", "resumes/{jobId}/{candidateId}.pdf · private · pre-signed URLs only · 7-day lifecycle"),
]

# arrows: (source, target, exit, entry, waypoints, label)
EDGES = [
    ("cand", "amplify", (0.5, 1), (0.5, 0), [(362, 147), (132, 147)], ""),
    ("rec", "amplify", (0.5, 1), (0.5, 0), [(562, 147), (132, 147)], ""),
    ("amplify", "apigw", (0.5, 1), (0.5, 0), [], "HTTPS + CORS"),
    ("apigw", "api", (0.5, 1), (0.5, 0), [], ""),
    ("api", "ddb", (0.25, 1), (0.25, 0), [], "read / write"),
    ("s3in", "sqs", (1, 0.5), (0, 0.5), [], ""),
    ("sqs", "proc", (1, 0.5), (0, 0.5), [], ""),
    ("proc", "ddb", (0.5, 1), (0.75, 0), [(812, 822), (148, 822)], "score / FAILED"),
]

LABEL_STYLE = {
    "right": "labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=6;",
    "top": "labelPosition=center;verticalLabelPosition=top;align=center;verticalAlign=bottom;",
    "none": "",
}


def build_xml():
    cells, n = [], [2]

    def add(xml):
        cid = f"y{n[0]}"
        n[0] += 1
        cells.append(xml.replace("{id}", cid))
        return cid

    for name, y, h, header, body in LAYERS:
        add(f'<mxCell id="{{id}}" value="{escape(name)}" style="swimlane;horizontal=0;startSize=44;container=0;collapsible=0;'
            f'html=1;whiteSpace=wrap;fillColor={header};swimlaneFillColor={body};strokeColor=#B7C2D0;fontStyle=1;fontSize=14;'
            f'fontColor=#232F3E;rounded=1;arcSize=2;" vertex="1" parent="1">'
            f'<mxGeometry x="20" y="{y}" width="{W - 40}" height="{h}" as="geometry"/></mxCell>')

    for x, y, w, h, title, detail in BOXES:
        label = f"<b>{escape(title)}</b><br><font style='font-size:11px' color='#545B64'>{escape(detail)}</font>"
        add(f'<mxCell id="{{id}}" value="{escape(label)}" style="rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor=#FFFFFF;'
            f'strokeColor=#8C9BAF;fontSize=13;fontColor=#232F3E;spacing=6;" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

    ids = {}
    for key, (x, y, label, cat, icon, side) in ICONS.items():
        style = (f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor={base.COLOUR[cat]};strokeColor=#ffffff;"
                 f"dashed=0;html=1;fontSize=12;aspect=fixed;whiteSpace=nowrap;{LABEL_STYLE[side]}"
                 f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{icon};")
        ids[key] = add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
                       f'<mxGeometry x="{x}" y="{y}" width="{ICON}" height="{ICON}" as="geometry"/></mxCell>')
    for key, (x, y, label) in PEOPLE.items():
        style = ("sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor=#232F3E;strokeColor=none;dashed=0;"
                 "labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=6;"
                 "html=1;fontSize=14;fontStyle=1;aspect=fixed;shape=mxgraph.aws4.user;")
        ids[key] = add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
                       f'<mxGeometry x="{x}" y="{y}" width="64" height="64" as="geometry"/></mxCell>')

    for src, dst, (ex, ey), (nx, ny), pts, label in EDGES:
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=open;endFill=0;endSize=8;strokeWidth=2;"
                 f"strokeColor=#232F3E;fontSize=11;fontColor=#232F3E;labelBackgroundColor=#ffffff;"
                 f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={nx};entryY={ny};entryDx=0;entryDy=0;")
        points = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in pts)
        geo = (f'<mxGeometry relative="1" as="geometry"><Array as="points">{points}</Array></mxGeometry>'
               if pts else '<mxGeometry relative="1" as="geometry"/>')
        add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" edge="1" parent="1" '
            f'source="{ids[src]}" target="{ids[dst]}">{geo}</mxCell>')

    add('<mxCell id="{id}" value="&lt;b&gt;ResumeRank – system architecture&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:13px&quot; '
        'color=&quot;#545B64&quot;&gt;AWS ap-south-1 · fully serverless · Rs. 0 on the AWS Free Tier&lt;/font&gt;" '
        'style="text;html=1;fontSize=19;fontColor=#232F3E;align=right;verticalAlign=middle;" vertex="1" parent="1">'
        '<mxGeometry x="900" y="45" width="760" height="56" as="geometry"/></mxCell>')
    return ('<mxGraphModel dx="1700" dy="1180" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
            f'fold="1" page="1" pageScale="1" pageWidth="{W}" pageHeight="{H}" math="0" shadow="0">'
            '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel>")


def main():
    model = build_xml()
    drawio = os.path.join(ROOT, "docs", "system-architecture.drawio")
    with open(drawio, "w", encoding="utf-8") as f:
        f.write('<mxfile host="app.diagrams.net"><diagram name="ResumeRank system architecture" id="resumerank-system">'
                + model + "</diagram></mxfile>\n")
    print("wrote docs/system-architecture.drawio")
    if "--no-png" not in sys.argv:
        base.CANVAS_W, base.CANVAS_H = W, H
        if base.render_png(model, os.path.join(ROOT, "docs", "system-architecture.png")):
            print("wrote docs/system-architecture.png")


if __name__ == "__main__":
    main()
