"""api_handler – HTTP API (payload format 2.0) routes for ResumeRank.

    POST /jobs           create a job
    POST /upload-url     PENDING candidate + pre-signed S3 PUT URL
    GET  /candidates     ranked candidates for ?jobId= (ScoreIndex, descending)

Handler: lambda_function.lambda_handler (Python 3.12, 256 MB, 10 s). Contract: INTERFACES.md.
"""

import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JOBS_TABLE = os.environ.get("JOBS_TABLE", "Jobs")
CANDIDATES_TABLE = os.environ.get("CANDIDATES_TABLE", "Candidates")
SCORE_INDEX = os.environ.get("SCORE_INDEX", "ScoreIndex")
RESUMES_BUCKET = os.environ.get("RESUMES_BUCKET", "")
UPLOAD_URL_TTL = int(os.environ.get("UPLOAD_URL_TTL", "300"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
REGION = os.environ.get("AWS_REGION", "ap-south-1")

PDF_TYPE = "application/pdf"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_TEXT = 200

dynamodb = boto3.resource("dynamodb")
# SigV4 + regional virtual-hosted endpoint so the browser PUT goes straight to the bucket's region
s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)
jobs_table = dynamodb.Table(JOBS_TABLE)
candidates_table = dynamodb.Table(CANDIDATES_TABLE)


class BadRequest(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"not serialisable: {type(value)}")


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def parse_body(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        raise BadRequest("body must be valid JSON")
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    return body


def text_field(body, name, max_len=MAX_TEXT):
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise BadRequest(f"'{name}' is required")
    value = value.strip()
    if len(value) > max_len:
        raise BadRequest(f"'{name}' is too long (max {max_len} characters)")
    return value


def email_field(body, name):
    value = text_field(body, name)
    if not EMAIL_RE.match(value):
        raise BadRequest(f"'{name}' is not a valid email address")
    return value


def job_id_field(value):
    if not isinstance(value, str) or not UUID_RE.match(value.strip().lower()):
        raise BadRequest("'jobId' must be a job id returned by POST /jobs")
    return value.strip().lower()


# ---------------------------------------------------------------- routes

def create_job(event):
    body = parse_body(event)
    title = text_field(body, "title")
    recruiter_email = email_field(body, "recruiterEmail")

    skills = body.get("requiredSkills")
    if isinstance(skills, str):
        skills = skills.split(",")
    if not isinstance(skills, list):
        raise BadRequest("'requiredSkills' must be a list of skill names")
    skills = {s.strip().lower() for s in skills if isinstance(s, str) and s.strip()}
    if not skills:
        raise BadRequest("'requiredSkills' must contain at least one skill")
    if len(skills) > 30 or any(len(s) > 50 for s in skills):
        raise BadRequest("'requiredSkills' allows at most 30 skills of up to 50 characters")

    min_years = body.get("minYears", 0)
    try:
        min_years = int(min_years)
    except (TypeError, ValueError):
        raise BadRequest("'minYears' must be a whole number")
    if not 0 <= min_years <= 15:
        raise BadRequest("'minYears' must be between 0 and 15")

    item = {
        "jobId": str(uuid.uuid4()),
        "title": title,
        "requiredSkills": skills,
        "minYears": min_years,
        "recruiterEmail": recruiter_email,
        "createdAt": now_iso(),
    }
    jobs_table.put_item(Item=item)
    logger.info("job created: %s (%s)", item["jobId"], title)
    return respond(201, item)


def create_upload_url(event):
    if not RESUMES_BUCKET:
        raise BadRequest("server is missing RESUMES_BUCKET", status=500)
    body = parse_body(event)
    job_id = job_id_field(body.get("jobId"))
    name = text_field(body, "name")
    email = email_field(body, "email")

    if body.get("contentType") != PDF_TYPE:
        raise BadRequest("only PDF files are accepted (contentType must be application/pdf)")
    size = body.get("fileSize")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise BadRequest("'fileSize' must be the file size in bytes")
    if size > MAX_UPLOAD_BYTES:
        raise BadRequest(f"file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")

    if not jobs_table.get_item(Key={"jobId": job_id}).get("Item"):
        raise BadRequest("job not found", status=404)

    candidate_id = str(uuid.uuid4())
    key = f"resumes/{job_id}/{candidate_id}.pdf"

    candidates_table.put_item(Item={
        "jobId": job_id,
        "candidateId": candidate_id,
        "name": name,
        "email": email,
        "status": "PENDING",
        "score": 0,
        "s3Key": key,
        "createdAt": now_iso(),
    })

    # ContentType and ContentLength are signed, so S3 rejects any other type or size
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": RESUMES_BUCKET, "Key": key, "ContentType": PDF_TYPE, "ContentLength": size},
        ExpiresIn=UPLOAD_URL_TTL,
        HttpMethod="PUT",
    )
    logger.info("upload url issued: %s (%d bytes)", key, size)
    return respond(200, {
        "candidateId": candidate_id,
        "s3Key": key,
        "uploadUrl": url,
        "expiresIn": UPLOAD_URL_TTL,
        "headers": {"Content-Type": PDF_TYPE},
    })


CANDIDATE_FIELDS = (
    "candidateId", "name", "status", "score", "skillScore", "expScore", "eduScore",
    "matchedSkills", "missingSkills", "yearsExperience", "textPreview", "processedAt",
    "failureReason",
)


def list_candidates(event):
    params = event.get("queryStringParameters") or {}
    job_id = job_id_field(params.get("jobId"))

    job = jobs_table.get_item(Key={"jobId": job_id}).get("Item")
    if not job:
        raise BadRequest("job not found", status=404)

    items, kwargs = [], {
        "IndexName": SCORE_INDEX,
        "KeyConditionExpression": Key("jobId").eq(job_id),
        "ScanIndexForward": False,
    }
    while True:
        page = candidates_table.query(**kwargs)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    candidates = []
    for rank, item in enumerate(items, start=1):
        row = {f: item.get(f) for f in CANDIDATE_FIELDS}
        row["rank"] = rank
        candidates.append(row)

    return respond(200, {
        "jobId": job_id,
        "job": {
            "title": job.get("title"),
            "requiredSkills": job.get("requiredSkills", set()),
            "minYears": job.get("minYears", 0),
        },
        "count": len(candidates),
        "candidates": candidates,
    })


ROUTES = {
    "POST /jobs": create_job,
    "POST /upload-url": create_upload_url,
    "GET /candidates": list_candidates,
}


def lambda_handler(event, context):
    route = event.get("routeKey")
    if not route:  # console test events without routeKey: rebuild it from the request context
        http = event.get("requestContext", {}).get("http", {})
        route = f"{http.get('method', '')} {http.get('path', event.get('rawPath', ''))}"
    handler = ROUTES.get(route)
    if handler is None:
        return respond(404, {"error": f"no route for {route}"})
    try:
        return handler(event)
    except BadRequest as e:
        logger.info("rejected %s: %s", route, e)
        return respond(e.status, {"error": str(e)})
    except Exception:
        logger.exception("unhandled error on %s", route)
        return respond(500, {"error": "internal error"})
