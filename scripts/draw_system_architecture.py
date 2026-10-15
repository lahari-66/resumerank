"""Draw the ResumeRank *system* architecture: a simple layered view of the system.

    python scripts/draw_system_architecture.py

Writes docs/system-architecture.drawio (editable in app.diagrams.net, official AWS icons) and
docs/system-architecture.png (rendered with the same headless-browser helper as
draw_architecture.py). docs/architecture.png shows the numbered request and event flow; this
diagram shows the layers of the system at a glance.
"""

import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draw_architecture as base  # noqa: E402  (reuses its PNG renderer and colours)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1500, 920
ICON = 64
LANE = 88            # x of the arrow lane between the layer names and the icons

# layers, drawn as swimlanes with the name in a vertical strip: (name, y, height, header, body)
LAYERS = [
    ("Users", 20, 120, "#E3E8EF", "#F7F9FB"),
    ("Frontend", 155, 135, "#F6D3DA", "#FDF4F6"),
    ("Backend API", 305, 135, "#E3D7FB", "#F8F4FF"),
    ("Processing", 455, 135, "#FBDDBD", "#FFF8F0"),
    ("Storage", 605, 135, "#EBD3F2", "#FBF5FD"),
    ("Support", 755, 145, "#CFE4F2", "#F2F8FC"),
]

# AWS icons: id: (x, y, label, colour key, resIcon); labels sit below the icon
ICONS = {
    "amplify":  (110, 172, "AWS Amplify", "frontend", "amplify"),
    "apigw":    (110, 322, "API Gateway", "network", "api_gateway"),
    "api":      (330, 322, "Lambda<br>api_handler", "compute", "lambda"),
    "s3in":     (110, 472, "Amazon S3", "storage", "s3"),
    "sqs":      (330, 472, "Amazon SQS", "integration", "sqs"),
    "proc":     (550, 472, "Lambda<br>process_resume", "compute", "lambda"),
    "ddb":      (110, 622, "DynamoDB", "database", "dynamodb"),
    "s3data":   (330, 622, "Amazon S3", "storage", "s3"),
    "sns":      (110, 772, "Amazon SNS", "integration", "sns"),
    "cw":       (330, 772, "CloudWatch", "management", "cloudwatch_2"),
    "iam":      (550, 772, "IAM", "security", "identity_and_access_management"),
    "textract": (770, 772, "Textract", "ml", "textract"),
    "comp":     (990, 772, "Comprehend", "ml", "comprehend"),
}
PEOPLE = {"cand": (110, 40, "Candidate"), "rec": (330, 40, "Recruiter")}

# one plain-language summary per layer: (x, y, w, h, title, detail)
SUMMARIES = [
    (820, 180, 640, 80, "Website (HTTPS)", "Home · Apply · Track application · Recruiter dashboard"),
    (820, 330, 640, 80, "REST API", "jobs · uploads · ranked candidates · shortlist & notes"),
    (820, 480, 640, 80, "Resume pipeline", "read the PDF → find skills → score 0–100 → save → alert"),
    (820, 630, 640, 80, "Data", "jobs and candidates (DynamoDB) · resume PDFs (private S3)"),
    (1210, 780, 250, 80, "Shared services", "email alerts · monitoring · security · AI"),
]

# arrows: (source, target, exit, entry, waypoints, label, dashed)
EDGES = [
    ("cand", "amplify", (0, 0.5), (0, 0.3), [(LANE, 72), (LANE, 191)], "", False),
    ("amplify", "apigw", (0, 0.8), (0, 0.5), [(LANE, 223), (LANE, 354)], "", False),
    ("apigw", "api", (1, 0.5), (0, 0.5), [], "", False),
    ("amplify", "s3in", (0, 0.8), (0, 0.5), [(LANE, 223), (LANE, 504)], "upload", True),
    ("s3in", "sqs", (1, 0.5), (0, 0.5), [], "", False),
    ("sqs", "proc", (1, 0.5), (0, 0.5), [], "", False),
]


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

    for x, y, w, h, title, detail in SUMMARIES:
        label = f"<b>{escape(title)}</b><br><font style='font-size:13px' color='#545B64'>{escape(detail)}</font>"
        add(f'<mxCell id="{{id}}" value="{escape(label)}" style="rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor=#FFFFFF;'
            f'strokeColor=#8C9BAF;fontSize=15;fontColor=#232F3E;spacing=6;" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

    ids = {}
    for key, (x, y, label, cat, icon) in ICONS.items():
        style = (f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor={base.COLOUR[cat]};strokeColor=#ffffff;"
                 f"dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=13;aspect=fixed;"
                 f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{icon};")
        ids[key] = add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
                       f'<mxGeometry x="{x}" y="{y}" width="{ICON}" height="{ICON}" as="geometry"/></mxCell>')
    for key, (x, y, label) in PEOPLE.items():
        style = ("sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor=#232F3E;strokeColor=none;dashed=0;"
                 "labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=6;"
                 "html=1;fontSize=14;fontStyle=1;aspect=fixed;shape=mxgraph.aws4.user;")
        ids[key] = add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
                       f'<mxGeometry x="{x}" y="{y}" width="64" height="64" as="geometry"/></mxCell>')

    for src, dst, (ex, ey), (nx, ny), pts, label, dashed in EDGES:
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=open;endFill=0;endSize=8;strokeWidth=2;"
                 f"strokeColor=#232F3E;fontSize=12;fontColor=#232F3E;labelBackgroundColor=#ffffff;"
                 f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
                 f"{'dashed=1;' if dashed else ''}")
        points = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in pts)
        geo = (f'<mxGeometry relative="1" as="geometry"><Array as="points">{points}</Array></mxGeometry>'
               if pts else '<mxGeometry relative="1" as="geometry"/>')
        add(f'<mxCell id="{{id}}" value="{escape(label)}" style="{style}" edge="1" parent="1" '
            f'source="{ids[src]}" target="{ids[dst]}">{geo}</mxCell>')

    add('<mxCell id="{id}" value="&lt;b&gt;ResumeRank – system architecture&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:13px&quot; '
        'color=&quot;#545B64&quot;&gt;fully serverless on AWS · ap-south-1 · Rs. 0 on the Free Tier&lt;/font&gt;" '
        'style="text;html=1;fontSize=19;fontColor=#232F3E;align=right;verticalAlign=middle;" vertex="1" parent="1">'
        f'<mxGeometry x="760" y="50" width="{W - 800}" height="56" as="geometry"/></mxCell>')
    return ('<mxGraphModel dx="1500" dy="920" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
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
