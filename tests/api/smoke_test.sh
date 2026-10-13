#!/usr/bin/env bash
# End-to-end API check with curl (Git Bash on Windows, or any bash with curl + python).
#
#   bash tests/api/smoke_test.sh                 # uses API_BASE_URL from .env
#   bash tests/api/smoke_test.sh tests/resumes/R4.pdf
#
# 1. POST /jobs  2. POST /upload-url  3. PUT the PDF to S3  4. poll GET /candidates
set -euo pipefail

cd "$(dirname "$0")/../.."
[ -f .env ] && set -a && . ./.env && set +a
API="${API_BASE_URL:?set API_BASE_URL in .env (API Gateway invoke URL)}"
API="${API%/}"
PDF="${1:-tests/resumes/R1.pdf}"
PY=""
for c in python3 python py; do   # skip the Windows Store "python3" stub, which exits non-zero
  if command -v "$c" >/dev/null && "$c" -c "pass" 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "python not found"; exit 1; }

json() { "$PY" -c "import json,sys; print(json.load(sys.stdin)$1)"; }

echo "== POST /jobs"
JOB=$(curl -sS -f -X POST "$API/jobs" -H "Content-Type: application/json" \
  -d '{"title":"Cloud Engineer Intern","requiredSkills":["python","aws","docker","linux","sql"],"minYears":2,"recruiterEmail":"recruiter@example.com"}')
echo "$JOB"
JOB_ID=$(echo "$JOB" | json '["jobId"]')

echo "== POST /upload-url  ($PDF)"
SIZE=$(wc -c < "$PDF" | tr -d ' ')
SIGNED=$(curl -sS -f -X POST "$API/upload-url" -H "Content-Type: application/json" \
  -d "{\"jobId\":\"$JOB_ID\",\"name\":\"Smoke Test\",\"email\":\"smoke@example.com\",\"contentType\":\"application/pdf\",\"fileSize\":$SIZE}")
echo "$SIGNED" | "$PY" -c "import json,sys; d=json.load(sys.stdin); d['uploadUrl']=d['uploadUrl'][:90]+'...'; print(d)"
URL=$(echo "$SIGNED" | json '["uploadUrl"]')

echo "== PUT to S3"
curl -sS -f -X PUT "$URL" -H "Content-Type: application/pdf" --data-binary "@$PDF" -o /dev/null -w "HTTP %{http_code}\n"

echo "== negative checks (expect 400s)"
curl -sS -o /dev/null -w "non-pdf -> HTTP %{http_code}\n" -X POST "$API/upload-url" -H "Content-Type: application/json" \
  -d "{\"jobId\":\"$JOB_ID\",\"name\":\"x\",\"email\":\"x@example.com\",\"contentType\":\"image/png\",\"fileSize\":10}"
curl -sS -o /dev/null -w "6 MB    -> HTTP %{http_code}\n" -X POST "$API/upload-url" -H "Content-Type: application/json" \
  -d "{\"jobId\":\"$JOB_ID\",\"name\":\"x\",\"email\":\"x@example.com\",\"contentType\":\"application/pdf\",\"fileSize\":6291456}"

echo "== GET /candidates (polling up to 60 s for SCORED)"
for i in $(seq 1 20); do
  OUT=$(curl -sS -f "$API/candidates?jobId=$JOB_ID")
  STATUS=$(echo "$OUT" | json '["candidates"][0]["status"]')
  echo "  try $i: $STATUS"
  [ "$STATUS" != "PENDING" ] && break
  sleep 3
done
echo "$OUT" | "$PY" -m json.tool

if [ -n "${SITE_BUCKET:-}" ]; then
  ORIGIN="http://$SITE_BUCKET.s3-website.${AWS_REGION:-ap-south-1}.amazonaws.com"
  echo "== CORS preflight from $ORIGIN"
  curl -sS -o /dev/null -D - -X OPTIONS "$API/jobs" -H "Origin: $ORIGIN" \
    -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type" \
    | grep -i "^access-control" || echo "  no CORS headers returned"
fi
echo "jobId=$JOB_ID"
