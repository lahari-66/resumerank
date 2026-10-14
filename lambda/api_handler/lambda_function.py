"""api_handler – HTTP API (payload format 2.0) routes for ResumeRank.

Public (candidates and the home page):
    GET  /jobs              list jobs with applicant counts, or one job with ?jobId=
    POST /upload-url        PENDING candidate + pre-signed S3 PUT URL
    GET  /status            a candidate's own result, ?jobId=&candidateId=
    POST /skills/extract    required skills found in a pasted job description

Recruiter (header x-recruiter-key must match the RECRUITER_KEY environment variable):
    POST /jobs              create a job
    GET  /candidates        ranked candidates for ?jobId= (ScoreIndex, descending)
    POST /decision          shortlist / reject / clear a candidate
    GET  /resume-url        short-lived pre-signed GET URL to view a resume PDF

Handler: lambda_function.lambda_handler (Python 3.12, 256 MB, 10 s). Contract: INTERFACES.md.
"""

import base64
import hmac
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
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JOBS_TABLE = os.environ.get("JOBS_TABLE", "Jobs")
CANDIDATES_TABLE = os.environ.get("CANDIDATES_TABLE", "Candidates")
SCORE_INDEX = os.environ.get("SCORE_INDEX", "ScoreIndex")
RESUMES_BUCKET = os.environ.get("RESUMES_BUCKET", "")
RECRUITER_KEY = os.environ.get("RECRUITER_KEY", "")
UPLOAD_URL_TTL = int(os.environ.get("UPLOAD_URL_TTL", "300"))
VIEW_URL_TTL = int(os.environ.get("VIEW_URL_TTL", "300"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
REGION = os.environ.get("AWS_REGION", "ap-south-1")

PDF_TYPE = "application/pdf"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_TEXT = 200
MAX_DESCRIPTION = 5000
MAX_EXTRACT_TEXT = 20000
DECISIONS = {"SHORTLISTED", "REJECTED", "NONE"}

dynamodb = boto3.resource("dynamodb")
# SigV4 + regional virtual-hosted endpoint so the browser talks straight to the bucket's region
s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)
jobs_table = dynamodb.Table(JOBS_TABLE)
candidates_table = dynamodb.Table(CANDIDATES_TABLE)

if not RECRUITER_KEY:
    logger.warning("RECRUITER_KEY is not set: recruiter routes are open to anyone")


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


def query_params(event):
    return event.get("queryStringParameters") or {}


def text_field(body, name, max_len=MAX_TEXT):
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise BadRequest(f"'{name}' is required")
    value = value.strip()
    if len(value) > max_len:
        raise BadRequest(f"'{name}' is too long (max {max_len} characters)")
    return value


def email_field(body, name, required=True):
    if not required and not (isinstance(body.get(name), str) and body[name].strip()):
        return None
    value = text_field(body, name)
    if not EMAIL_RE.match(value):
        raise BadRequest(f"'{name}' is not a valid email address")
    return value


def id_field(value, name):
    if not isinstance(value, str) or not UUID_RE.match(value.strip().lower()):
        raise BadRequest(f"'{name}' must be an id issued by the API")
    return value.strip().lower()


def require_recruiter(event):
    if not RECRUITER_KEY:
        return
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    supplied = headers.get("x-recruiter-key", "")
    if not hmac.compare_digest(supplied.encode(), RECRUITER_KEY.encode()):
        raise BadRequest("recruiter access key missing or wrong", status=401)


def get_job(job_id):
    job = jobs_table.get_item(Key={"jobId": job_id}).get("Item")
    if not job:
        raise BadRequest("job not found", status=404)
    return job


def get_candidate(job_id, candidate_id):
    item = candidates_table.get_item(Key={"jobId": job_id, "candidateId": candidate_id}).get("Item")
    if not item:
        raise BadRequest("candidate not found", status=404)
    return item


def public_job(job):
    return {
        "jobId": job["jobId"],
        "title": job.get("title"),
        "requiredSkills": job.get("requiredSkills", set()),
        "minYears": job.get("minYears", 0),
        "description": job.get("description", ""),
        "createdAt": job.get("createdAt"),
    }


def count_candidates(job_id):
    total, kwargs = 0, {"KeyConditionExpression": Key("jobId").eq(job_id), "Select": "COUNT"}
    while True:
        page = candidates_table.query(**kwargs)
        total += page.get("Count", 0)
        if "LastEvaluatedKey" not in page:
            return total
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


# ---------------------------------------------------------------- public routes

def list_jobs(event):
    job_id = query_params(event).get("jobId")
    if job_id:
        return respond(200, public_job(get_job(id_field(job_id, "jobId"))))

    jobs, kwargs = [], {}
    while True:
        page = jobs_table.scan(**kwargs)
        jobs.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    jobs.sort(key=lambda j: j.get("createdAt", ""), reverse=True)
    jobs = jobs[:50]

    out = []
    for job in jobs:
        row = public_job(job)
        row.pop("description", None)
        row["candidateCount"] = count_candidates(job["jobId"])
        out.append(row)
    return respond(200, {"count": len(out), "jobs": out,
                         "totalCandidates": sum(j["candidateCount"] for j in out)})


def create_upload_url(event):
    if not RESUMES_BUCKET:
        raise BadRequest("server is missing RESUMES_BUCKET", status=500)
    body = parse_body(event)
    job_id = id_field(body.get("jobId"), "jobId")
    name = text_field(body, "name")
    email = email_field(body, "email", required=False)

    if body.get("contentType") != PDF_TYPE:
        raise BadRequest("only PDF files are accepted (contentType must be application/pdf)")
    size = body.get("fileSize")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise BadRequest("'fileSize' must be the file size in bytes")
    if size > MAX_UPLOAD_BYTES:
        raise BadRequest(f"file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")

    get_job(job_id)

    candidate_id = str(uuid.uuid4())
    key = f"resumes/{job_id}/{candidate_id}.pdf"
    item = {
        "jobId": job_id,
        "candidateId": candidate_id,
        "name": name,
        "status": "PENDING",
        "score": 0,
        "s3Key": key,
        "createdAt": now_iso(),
    }
    if email:
        item["email"] = email
    candidates_table.put_item(Item=item)

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


def candidate_status(event):
    params = query_params(event)
    job_id = id_field(params.get("jobId"), "jobId")
    candidate_id = id_field(params.get("candidateId"), "candidateId")
    job = get_job(job_id)
    c = get_candidate(job_id, candidate_id)
    scored = c.get("status") == "SCORED"
    return respond(200, {
        "jobId": job_id,
        "candidateId": candidate_id,
        "job": {"title": job.get("title"), "requiredSkills": job.get("requiredSkills", set()),
                "minYears": job.get("minYears", 0)},
        "name": c.get("name"),
        "status": c.get("status"),
        "submittedAt": c.get("createdAt"),
        "processedAt": c.get("processedAt"),
        "score": c.get("score") if scored else None,
        "skillScore": c.get("skillScore"),
        "expScore": c.get("expScore"),
        "eduScore": c.get("eduScore"),
        "yearsExperience": c.get("yearsExperience"),
        "matchedSkills": c.get("matchedSkills", []),
        "missingSkills": c.get("missingSkills", []),
        "failureReason": c.get("failureReason"),
    })


def extract_skills(event):
    import scoring   # bundled into this zip from lambda/process_resume by scripts/package_lambda.py

    body = parse_body(event)
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise BadRequest("'text' is required")
    if len(text) > MAX_EXTRACT_TEXT:
        raise BadRequest(f"'text' is too long (max {MAX_EXTRACT_TEXT} characters)")
    ordered = scoring.skills_in_order(text)   # first-mentioned skills first
    return respond(200, {"skills": ordered, "count": len(ordered)})


# ---------------------------------------------------------------- recruiter routes

def create_job(event):
    require_recruiter(event)
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

    description = body.get("description") or ""
    if not isinstance(description, str) or len(description) > MAX_DESCRIPTION:
        raise BadRequest(f"'description' must be text of at most {MAX_DESCRIPTION} characters")

    item = {
        "jobId": str(uuid.uuid4()),
        "title": title,
        "requiredSkills": skills,
        "minYears": min_years,
        "recruiterEmail": recruiter_email,
        "createdAt": now_iso(),
    }
    if description.strip():
        item["description"] = description.strip()
    jobs_table.put_item(Item=item)
    logger.info("job created: %s (%s)", item["jobId"], title)
    return respond(201, item)


CANDIDATE_FIELDS = (
    "candidateId", "name", "email", "status", "score", "skillScore", "expScore", "eduScore",
    "matchedSkills", "missingSkills", "yearsExperience", "textPreview", "createdAt", "processedAt",
    "failureReason", "decision", "decidedAt",
)


def list_candidates(event):
    require_recruiter(event)
    job_id = id_field(query_params(event).get("jobId"), "jobId")
    job = get_job(job_id)

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
        row["decision"] = row["decision"] or "NONE"
        row["rank"] = rank
        candidates.append(row)

    return respond(200, {
        "jobId": job_id,
        "job": public_job(job),
        "count": len(candidates),
        "candidates": candidates,
    })


def set_decision(event):
    require_recruiter(event)
    body = parse_body(event)
    job_id = id_field(body.get("jobId"), "jobId")
    candidate_id = id_field(body.get("candidateId"), "candidateId")
    decision = str(body.get("decision", "")).upper()
    if decision not in DECISIONS:
        raise BadRequest("'decision' must be SHORTLISTED, REJECTED or NONE")
    try:
        candidates_table.update_item(
            Key={"jobId": job_id, "candidateId": candidate_id},
            UpdateExpression="SET decision = :d, decidedAt = :t",
            ConditionExpression="attribute_exists(candidateId)",
            ExpressionAttributeValues={":d": decision, ":t": now_iso()},
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise BadRequest("candidate not found", status=404)
        raise
    logger.info("decision %s for %s/%s", decision, job_id, candidate_id)
    return respond(200, {"jobId": job_id, "candidateId": candidate_id, "decision": decision})


def resume_url(event):
    require_recruiter(event)
    params = query_params(event)
    job_id = id_field(params.get("jobId"), "jobId")
    candidate_id = id_field(params.get("candidateId"), "candidateId")
    c = get_candidate(job_id, candidate_id)
    key = c.get("s3Key") or f"resumes/{job_id}/{candidate_id}.pdf"
    try:
        s3.head_object(Bucket=RESUMES_BUCKET, Key=key)
    except ClientError:
        raise BadRequest("resume file not found (uploads are deleted after 7 days)", status=404)
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": RESUMES_BUCKET, "Key": key, "ResponseContentType": PDF_TYPE,
                "ResponseContentDisposition": "inline"},
        ExpiresIn=VIEW_URL_TTL,
    )
    return respond(200, {"url": url, "expiresIn": VIEW_URL_TTL})


ROUTES = {
    "GET /jobs": list_jobs,
    "POST /jobs": create_job,
    "POST /upload-url": create_upload_url,
    "GET /candidates": list_candidates,
    "GET /status": candidate_status,
    "POST /decision": set_decision,
    "GET /resume-url": resume_url,
    "POST /skills/extract": extract_skills,
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
