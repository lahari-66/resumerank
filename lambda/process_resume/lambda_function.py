"""process_resume – S3 ObjectCreated -> Textract (or the PDF text layer) -> Comprehend -> score -> DynamoDB -> SNS.

Handler: lambda_function.lambda_handler (Python 3.12, 256 MB, 120 s).
Triggered through SQS (S3 -> resumerank-queue -> Lambda, DLQ resumerank-dlq) or directly by S3.
Key convention (INTERFACES.md): resumes/{jobId}/{candidateId}.pdf
"""

import io
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

import scoring

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JOBS_TABLE = os.environ.get("JOBS_TABLE", "Jobs")
CANDIDATES_TABLE = os.environ.get("CANDIDATES_TABLE", "Candidates")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
SCORE_THRESHOLD = int(os.environ.get("SCORE_THRESHOLD", "75"))
METRIC_NAMESPACE = os.environ.get("METRIC_NAMESPACE", "ResumeRank")
# auto: Textract, falling back to the PDF's own text layer if the account cannot use Textract
# textract: Textract only · pdftext: text layer only (no OCR, scanned PDFs fail)
TEXT_SOURCE = os.environ.get("TEXT_SOURCE", "auto").lower()

POLL_SECONDS = 3
SAFETY_MS = 15000            # stop polling Textract with this much Lambda time left
COMPREHEND_MAX_BYTES = 5000
ENTITY_TYPES = {"ORGANIZATION", "DATE", "TITLE"}
PREVIEW_CHARS = 300
FULL_TEXT_CHARS = 20000          # stored for recruiter full-text search (item limit is 400 KB)

KEY_RE = re.compile(r"^resumes/(?P<jobId>[A-Za-z0-9-]+)/(?P<candidateId>[A-Za-z0-9-]+)\.pdf$")

SERVICE_UNAVAILABLE_CODES = {"SubscriptionRequiredException", "AccessDeniedException",
                             "UnrecognizedClientException"}

s3 = boto3.client("s3")
textract = boto3.client("textract")
comprehend = boto3.client("comprehend")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")
cloudwatch = boto3.client("cloudwatch")

jobs_table = dynamodb.Table(JOBS_TABLE)
candidates_table = dynamodb.Table(CANDIDATES_TABLE)


class ProcessingError(Exception):
    """A failure that should be recorded on the candidate as status FAILED."""


class RetryableError(Exception):
    """A transient failure (e.g. DynamoDB unavailable). From SQS the message is retried, and after
    maxReceiveCount attempts it moves to the dead-letter queue instead of being lost."""


class Superseded(Exception):
    """The candidate applied again while this resume was queued; the old record must stay SUPERSEDED."""


class TextractUnavailable(Exception):
    """The account cannot call Textract at all (e.g. AWS Free plan), as opposed to a failed job."""


_textract_unavailable = False   # remembered for the life of a warm container
_comprehend_unavailable = False


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_key(key):
    m = KEY_RE.match(key)
    return (m.group("jobId"), m.group("candidateId")) if m else (None, None)


# ---------------------------------------------------------------- Textract

def extract_text(bucket, key, context):
    """Async text detection straight from S3; returns all LINE blocks joined in reading order."""
    try:
        job_id = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
        )["JobId"]
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in SERVICE_UNAVAILABLE_CODES:
            raise TextractUnavailable(str(e)) from e
        raise ProcessingError(f"textract start failed: {e}") from e
    except Exception as e:
        raise ProcessingError(f"textract start failed: {e}") from e
    logger.info("textract job started: %s", job_id)

    started = time.time()
    while True:
        if context is not None and context.get_remaining_time_in_millis() < SAFETY_MS:
            raise ProcessingError("textract did not finish before the lambda timeout")
        time.sleep(POLL_SECONDS)
        try:
            resp = textract.get_document_text_detection(JobId=job_id)
        except Exception as e:
            raise ProcessingError(f"textract poll failed: {e}") from e
        status = resp["JobStatus"]
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "PARTIAL_SUCCESS"):
            raise ProcessingError(f"textract job {status}: {resp.get('StatusMessage', '')}")

    lines = [b["Text"] for b in resp.get("Blocks", []) if b["BlockType"] == "LINE"]
    pages = resp.get("DocumentMetadata", {}).get("Pages", 0)
    token = resp.get("NextToken")
    while token:
        try:
            resp = textract.get_document_text_detection(JobId=job_id, NextToken=token)
        except Exception as e:
            raise ProcessingError(f"textract pagination failed: {e}") from e
        lines.extend(b["Text"] for b in resp.get("Blocks", []) if b["BlockType"] == "LINE")
        token = resp.get("NextToken")

    text = "\n".join(lines)
    logger.info("textract done in %.1fs: %d pages, %d lines, %d chars",
                time.time() - started, pages, len(lines), len(text))
    logger.info("text preview: %s", text[:500].replace("\n", " | "))
    return text


def extract_text_layer(bucket, key):
    """Fallback without OCR: read the PDF's embedded text with pypdf. Scanned PDFs have none."""
    from pypdf import PdfReader   # bundled in the zip; imported lazily so Textract-only runs skip it

    try:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except Exception as e:
        raise ProcessingError(f"s3 download failed: {e}") from e
    try:
        reader = PdfReader(io.BytesIO(body))
        if reader.is_encrypted:
            raise ProcessingError("the PDF is password-protected")
        pages = [page.extract_text() or "" for page in reader.pages]
    except ProcessingError:
        raise
    except Exception as e:
        raise ProcessingError(f"could not read the PDF: {e}") from e

    text = "\n".join(p.strip() for p in pages if p.strip())
    logger.info("pdf text layer: %d pages, %d chars", len(pages), len(text))
    if not text.strip():
        raise ProcessingError("no text layer in the PDF (scanned image); OCR needs Textract, "
                              "which this AWS account cannot use")
    logger.info("text preview: %s", text[:500].replace("\n", " | "))
    return text


def get_text(bucket, key, context):
    """Textract first (OCR, any PDF); the PDF text layer when the account has no Textract access."""
    global _textract_unavailable
    if TEXT_SOURCE == "pdftext":
        return extract_text_layer(bucket, key)
    if TEXT_SOURCE == "auto" and _textract_unavailable:
        return extract_text_layer(bucket, key)
    try:
        return extract_text(bucket, key, context)
    except TextractUnavailable as e:
        if TEXT_SOURCE != "auto":
            raise ProcessingError(f"textract unavailable: {e}") from e
        _textract_unavailable = True
        logger.warning("textract unavailable for this account (%s); using the PDF text layer", e)
        return extract_text_layer(bucket, key)


# ---------------------------------------------------------------- Comprehend

def chunk_text(text, max_bytes=COMPREHEND_MAX_BYTES):
    """Split on line boundaries into chunks under max_bytes of UTF-8; yields (offset, chunk)."""
    chunks, start, current, size = [], 0, [], 0
    pos = 0
    for line in text.splitlines(keepends=True):
        b = len(line.encode("utf-8"))
        while b > max_bytes:                       # a single huge line: hard-split it
            cut = len(line.encode("utf-8")[:max_bytes].decode("utf-8", "ignore"))
            if current:
                chunks.append((start, "".join(current)))
                current, size = [], 0
            chunks.append((pos, line[:cut]))
            pos += cut
            line = line[cut:]
            b = len(line.encode("utf-8"))
        if size + b > max_bytes and current:
            chunks.append((start, "".join(current)))
            current, size = [], 0
        if not current:
            start = pos
        current.append(line)
        size += b
        pos += len(line)
    if current:
        chunks.append((start, "".join(current)))
    return [(o, c) for o, c in chunks if c.strip()]


def analyse_text(text):
    """Key phrases and ORGANIZATION / DATE / TITLE entities, with offsets into the full text.

    Comprehend is an enrichment: if it fails, scoring still runs on the extracted text alone.
    """
    global _comprehend_unavailable
    phrases, entities = [], []
    if _comprehend_unavailable:
        logger.info("comprehend unavailable for this account; scoring on the text only")
        return phrases, entities
    for offset, chunk in chunk_text(text):
        try:
            kp = comprehend.detect_key_phrases(Text=chunk, LanguageCode="en")
            phrases.extend(p["Text"] for p in kp.get("KeyPhrases", []))
            ents = comprehend.detect_entities(Text=chunk, LanguageCode="en")
            for e in ents.get("Entities", []):
                if e["Type"] in ENTITY_TYPES:
                    entities.append({
                        "Type": e["Type"],
                        "Text": e["Text"],
                        "BeginOffset": offset + e["BeginOffset"],
                    })
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in SERVICE_UNAVAILABLE_CODES:
                _comprehend_unavailable = True
                logger.warning("comprehend unavailable for this account (%s); scoring on the text only", e)
                return [], []
            logger.exception("comprehend call failed on chunk at offset %d; continuing", offset)
        except Exception:
            logger.exception("comprehend call failed on chunk at offset %d; continuing", offset)

    counts = {t: sum(1 for e in entities if e["Type"] == t) for t in sorted(ENTITY_TYPES)}
    logger.info("comprehend: %d key phrases, entities %s", len(phrases), counts)
    return phrases, entities


# ---------------------------------------------------------------- persistence

def to_dynamo(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    return value


def save_scored(job_id, candidate_id, key, result, text):
    fields = {
        "status": "SCORED",
        "score": result["score"],
        "skillScore": result["skillScore"],
        "expScore": result["expScore"],
        "eduScore": result["eduScore"],
        "bonusScore": result["bonusScore"],
        "matchedSkills": result["matchedSkills"],
        "missingSkills": result["missingSkills"],
        "matchedPreferred": result["matchedPreferred"],
        "weights": result["weights"],
        "yearsExperience": result["yearsExperience"],
        "textPreview": text[:PREVIEW_CHARS],
        "fullText": text[:FULL_TEXT_CHARS],
        "s3Key": key,
        "processedAt": now_iso(),
    }
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": to_dynamo(v) for k, v in fields.items()}
    values[":superseded"] = "SUPERSEDED"
    try:
        candidates_table.update_item(
            Key={"jobId": job_id, "candidateId": candidate_id},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in fields) + " REMOVE failureReason",
            ConditionExpression="attribute_not_exists(#status) OR #status <> :superseded",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise Superseded() from e
        raise


def save_failed(job_id, candidate_id, key, reason):
    try:
        candidates_table.update_item(
            Key={"jobId": job_id, "candidateId": candidate_id},
            UpdateExpression="SET #s = :s, failureReason = :r, s3Key = :k, processedAt = :p, "
                             "score = if_not_exists(score, :zero)",
            ConditionExpression="attribute_not_exists(#s) OR #s <> :superseded",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "FAILED", ":r": reason[:500], ":k": key, ":p": now_iso(), ":zero": 0,
                ":superseded": "SUPERSEDED",
            },
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info("%s/%s was superseded; FAILED not written", job_id, candidate_id)
        else:
            logger.exception("could not write FAILED status for %s/%s", job_id, candidate_id)
    except Exception:
        logger.exception("could not write FAILED status for %s/%s", job_id, candidate_id)


def put_score_metric(score):
    try:
        cloudwatch.put_metric_data(
            Namespace=METRIC_NAMESPACE,
            MetricData=[{"MetricName": "CandidateScore", "Value": float(score), "Unit": "None"}],
        )
    except Exception:
        logger.exception("put_metric_data failed")


def alert_threshold(job):
    """The job's own alertThreshold (50-100) when set, otherwise the SCORE_THRESHOLD default."""
    try:
        value = int(job.get("alertThreshold", SCORE_THRESHOLD))
    except (TypeError, ValueError):
        return SCORE_THRESHOLD
    return value if 0 < value <= 100 else SCORE_THRESHOLD


def notify(job, candidate, result):
    if not SNS_TOPIC_ARN:
        logger.warning("SNS_TOPIC_ARN not set; skipping alert")
        return
    name = candidate.get("name", "Unknown candidate")
    title = job.get("title", job["jobId"])
    subject = f"ResumeRank: {name} scored {result['score']} for {title}"[:100]
    body = "\n".join([
        f"A candidate crossed this job's {alert_threshold(job)}-point alert threshold.",
        "",
        f"Job:        {title} ({job['jobId']})",
        f"Candidate:  {name}",
        f"Email:      {candidate.get('email', '-')}",
        f"Score:      {result['score']} / 100",
        f"  skills {result['skillScore']} / {result['weights']['skills']}, "
        f"experience {result['expScore']} / {result['weights']['experience']}, "
        f"education {result['eduScore']} / {result['weights']['education']}, "
        f"bonus {result['bonusScore']} / 10",
        f"Preferred:  {', '.join(result['matchedPreferred']) or '-'}",
        f"Experience: {result['yearsExperience']} years (estimated)",
        f"Matched:    {', '.join(result['matchedSkills']) or '-'}",
        f"Missing:    {', '.join(result['missingSkills']) or '-'}",
        "",
        "This score orders resumes for human review; it is not a hiring decision.",
    ])
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=body)
        logger.info("sns alert published for %s", candidate.get("candidateId"))
    except Exception:
        logger.exception("sns publish failed")


# ---------------------------------------------------------------- handler

def process_record(record, context, retryable=False):
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    job_id, candidate_id = parse_key(key)
    logger.info("received s3://%s/%s -> jobId=%s candidateId=%s", bucket, key, job_id, candidate_id)
    if not job_id:
        logger.warning("key does not match resumes/{jobId}/{candidateId}.pdf; ignoring")
        return {"key": key, "status": "IGNORED"}

    try:
        try:
            job = jobs_table.get_item(Key={"jobId": job_id}).get("Item")
            candidate = candidates_table.get_item(
                Key={"jobId": job_id, "candidateId": candidate_id}).get("Item") or {}
        except Exception as e:
            if retryable:
                raise RetryableError(f"dynamodb read failed: {e}") from e
            raise ProcessingError(f"dynamodb read failed: {e}") from e
        if not job:
            raise ProcessingError(f"job {job_id} not found")
        if candidate.get("status") == "SUPERSEDED":
            logger.info("%s was replaced by a newer application; skipping", candidate_id)
            return {"key": key, "status": "SUPERSEDED"}
        candidate.setdefault("candidateId", candidate_id)

        text = get_text(bucket, key, context)
        if not text.strip():
            raise ProcessingError("no text found in the PDF")

        phrases, entities = analyse_text(text)
        dates = [e for e in entities if e["Type"] == "DATE"]
        result = scoring.score_candidate(
            text,
            required_skills=list(job.get("requiredSkills", [])),
            min_years=int(job.get("minYears", 0)),
            key_phrases=phrases,
            date_entities=dates,
            preferred_skills=list(job.get("preferredSkills") or []),
            weights=job.get("weights"),
        )
        logger.info("score: %s", json.dumps(result))

        try:
            save_scored(job_id, candidate_id, key, result, text)
        except Superseded:
            logger.info("%s was superseded while being scored; result discarded, no alert", candidate_id)
            return {"key": key, "status": "SUPERSEDED"}
        except Exception as e:
            if retryable:
                raise RetryableError(f"dynamodb update failed: {e}") from e
            raise ProcessingError(f"dynamodb update failed: {e}") from e

        put_score_metric(result["score"])
        if result["score"] >= alert_threshold(job):
            notify(job, candidate, result)
        return {"key": key, "status": "SCORED", "score": result["score"]}

    except RetryableError:
        raise
    except ProcessingError as e:
        logger.error("FAILED %s: %s", key, e)
        save_failed(job_id, candidate_id, key, str(e))
        return {"key": key, "status": "FAILED", "reason": str(e)}
    except Exception as e:
        logger.exception("unexpected error on %s", key)
        save_failed(job_id, candidate_id, key, f"unexpected error: {e}")
        return {"key": key, "status": "FAILED", "reason": str(e)}


def s3_records_from_sqs(message):
    """An SQS message body is the S3 event notification JSON. S3's setup test event has no Records."""
    body = json.loads(message["body"])
    if body.get("Event") == "s3:TestEvent":
        logger.info("s3 test event from %s; nothing to do", body.get("Bucket"))
        return []
    return [r for r in body.get("Records", []) if "s3" in r]


def handle_sqs(event, context):
    """S3 -> SQS -> Lambda. Reports partial batch failures so only the failed messages are retried."""
    results, failures = [], []
    for message in event["Records"]:
        try:
            for record in s3_records_from_sqs(message):
                results.append(process_record(record, context, retryable=True))
        except (RetryableError, ValueError, KeyError) as e:
            logger.error("message %s will be retried (then dead-lettered): %s", message.get("messageId"), e)
            failures.append({"itemIdentifier": message["messageId"]})
    logger.info("done: %s; retrying %d message(s)", json.dumps(results), len(failures))
    return {"batchItemFailures": failures, "results": results}


def lambda_handler(event, context):
    records = event.get("Records", [])
    if records and records[0].get("eventSource") == "aws:sqs":
        return handle_sqs(event, context)
    results = [process_record(r, context) for r in records if "s3" in r]   # direct S3 trigger
    logger.info("done: %s", json.dumps(results))
    return {"results": results}
