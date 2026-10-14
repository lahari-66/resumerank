"""Local tests for the api_handler Lambda with AWS calls replaced by in-memory fakes.

Needs boto3 installed locally (it is bundled in the Lambda runtime). No AWS account is used:
fake credentials are set before import and every client is swapped for a fake.

    python -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import re
import sys
import unittest
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from botocore.exceptions import ClientError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.update({
    "AWS_DEFAULT_REGION": "ap-south-1",
    "AWS_REGION": "ap-south-1",
    "AWS_ACCESS_KEY_ID": "AKIATESTONLY",
    "AWS_SECRET_ACCESS_KEY": "test-only",
    "RESUMES_BUCKET": "resumerank-resumes-test",
})
# POST /skills/extract imports scoring, which the package script copies into the api zip
sys.path.insert(0, os.path.join(ROOT, "lambda", "process_resume"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = load("api_handler_fn", os.path.join(ROOT, "lambda", "api_handler", "lambda_function.py"))

KEY = "test-recruiter-key"
UNKNOWN = "00000000-0000-4000-8000-000000000000"


def _evaluate(cond, item):
    """Evaluate the small subset of boto3 condition objects the handler uses (Eq, In, And)."""
    expr = cond.get_expression()
    op, values = expr["operator"], expr["values"]
    if op == "AND":
        return all(_evaluate(v, item) for v in values)
    name = values[0].name
    if op == "=":
        return item.get(name) == values[1]
    if op == "IN":
        return item.get(name) in values[1]
    raise NotImplementedError(op)


class FakeTable:
    """In-memory DynamoDB table: SET/REMOVE updates, attribute_exists / IN conditions, filtered queries."""

    def __init__(self, items=None):
        self.items = list(items or [])
        self.updates, self.puts = [], []

    def _match(self, item, key):
        return all(item.get(k) == v for k, v in key.items())

    def _find(self, key):
        return next((i for i in self.items if self._match(i, key)), None)

    def get_item(self, Key):
        item = self._find(Key)
        return {"Item": dict(item)} if item else {}

    def put_item(self, Item):
        self.puts.append(Item)
        self.items.append(Item)

    def update_item(self, **kwargs):
        names = kwargs.get("ExpressionAttributeNames", {})
        values = kwargs.get("ExpressionAttributeValues", {})
        item = self._find(kwargs["Key"])
        cond = kwargs.get("ConditionExpression", "")
        ok = item is not None if "attribute_exists" in cond else True
        m = re.search(r"(#?\w+) IN \(([^)]*)\)", cond)
        if m and item is not None:
            field = names.get(m.group(1), m.group(1))
            ok = item.get(field) in [values[v.strip()] for v in m.group(2).split(",")]
        if not ok:
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        self.updates.append(kwargs)
        if item is None:
            item = dict(kwargs["Key"])
            self.items.append(item)
        expression = kwargs["UpdateExpression"]
        set_part = re.search(r"SET (.*?)(?: REMOVE |$)", expression)
        if set_part:
            for assignment in set_part.group(1).split(","):
                field, value = (x.strip() for x in assignment.split("="))
                item[names.get(field, field)] = values[value]
        remove_part = re.search(r"REMOVE (.*)$", expression)
        if remove_part:
            for field in remove_part.group(1).split(","):
                item.pop(names.get(field.strip(), field.strip()), None)

    def scan(self, **kwargs):
        return {"Items": list(self.items)}

    def query(self, **kwargs):
        self.last_query = kwargs
        job_id = kwargs["KeyConditionExpression"].get_expression()["values"][1]
        rows = [i for i in self.items if i.get("jobId") == job_id]
        if kwargs.get("FilterExpression") is not None:
            rows = [i for i in rows if _evaluate(kwargs["FilterExpression"], i)]
        if kwargs.get("Select") == "COUNT":
            return {"Count": len(rows)}
        return {"Items": sorted(rows, key=lambda i: i.get("score", 0), reverse=True)}


def http(route, body=None, query=None, key=KEY):
    method, path = route.split(" ")
    headers = {"content-type": "application/json"}
    if key:
        headers["x-recruiter-key"] = key
    return {"routeKey": route, "rawPath": path, "headers": headers,
            "body": json.dumps(body) if body is not None else None,
            "queryStringParameters": query, "requestContext": {"http": {"method": method, "path": path}}}


class ApiHandlerTests(unittest.TestCase):
    def setUp(self):
        self.jobs = FakeTable()
        self.cands = FakeTable()
        self.s3 = mock.Mock(wraps=api.s3)
        self.sns = mock.Mock()
        self.patches = [mock.patch.object(api, "jobs_table", self.jobs),
                        mock.patch.object(api, "sns", self.sns),
                        mock.patch.object(api, "SNS_TOPIC_ARN", "arn:aws:sns:ap-south-1:111122223333:resumerank-alerts"),
                        mock.patch.object(api, "candidates_table", self.cands),
                        mock.patch.object(api, "s3", self.s3),
                        mock.patch.object(api, "RESUMES_BUCKET", "resumerank-resumes-test"),
                        mock.patch.object(api, "RECRUITER_KEY", KEY)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def call(self, *args, **kwargs):
        res = api.lambda_handler(http(*args, **kwargs), None)
        return res["statusCode"], json.loads(res["body"])

    def make_job(self, **extra):
        status, body = self.call("POST /jobs", {
            "title": "Cloud Engineer Intern", "requiredSkills": ["Python", " AWS", "python", "docker"],
            "minYears": 2, "recruiterEmail": "recruiter@example.com", **extra})
        self.assertEqual(status, 201)
        return body

    def add_candidates(self, job_id):
        self.cands.items = [
            {"jobId": job_id, "candidateId": "11111111-1111-4111-8111-111111111111", "name": "Low",
             "email": "low@example.com", "status": "SCORED", "score": Decimal(44),
             "skillScore": Decimal("24.0"), "matchedSkills": ["python"], "missingSkills": ["aws"],
             "s3Key": f"resumes/{job_id}/11111111-1111-4111-8111-111111111111.pdf"},
            {"jobId": job_id, "candidateId": "22222222-2222-4222-8222-222222222222", "name": "High",
             "status": "SCORED", "score": Decimal(100), "skillScore": Decimal("60.0"), "decision": "SHORTLISTED"},
            {"jobId": job_id, "candidateId": "33333333-3333-4333-8333-333333333333", "name": "Waiting",
             "status": "PENDING", "score": Decimal(0)},
        ]

    # ------------------------------------------------------------ recruiter key

    def test_recruiter_routes_need_the_key(self):
        job = self.make_job()
        for route, body, query in [("POST /jobs", {}, None),
                                   ("POST /jobs/status", {}, None),
                                   ("POST /shortlist/send", {}, None),
                                   ("GET /candidates", None, {"jobId": job["jobId"]}),
                                   ("POST /decision", {}, None),
                                   ("GET /resume-url", None, {"jobId": job["jobId"], "candidateId": UNKNOWN})]:
            for key in (None, "wrong"):
                status, out = self.call(route, body, query, key=key)
                self.assertEqual(status, 401, (route, key))
                self.assertIn("access key", out["error"])

    def test_public_routes_work_without_the_key(self):
        job = self.make_job()
        self.assertEqual(self.call("GET /jobs", key=None)[0], 200)
        self.assertEqual(self.call("GET /jobs", query={"jobId": job["jobId"]}, key=None)[0], 200)
        self.assertEqual(self.call("POST /skills/extract", {"text": "python"}, key=None)[0], 200)

    def test_no_key_configured_leaves_recruiter_routes_open(self):
        with mock.patch.object(api, "RECRUITER_KEY", ""):
            status, _ = self.call("POST /jobs", {"title": "x", "requiredSkills": ["go"],
                                                 "recruiterEmail": "r@example.com"}, key=None)
        self.assertEqual(status, 201)

    # ------------------------------------------------------------ jobs

    def test_create_job(self):
        job = self.make_job(description="  We need cloud people.  ")
        self.assertRegex(job["jobId"], api.UUID_RE)
        self.assertEqual(job["requiredSkills"], ["aws", "docker", "python"])
        self.assertEqual(self.jobs.puts[0]["requiredSkills"], {"aws", "docker", "python"})
        self.assertEqual(self.jobs.puts[0]["description"], "We need cloud people.")

    def test_create_job_validation(self):
        bad = [
            {},
            {"title": "x", "requiredSkills": [], "recruiterEmail": "r@example.com"},
            {"title": "x", "requiredSkills": ["python"], "recruiterEmail": "not-an-email"},
            {"title": "x", "requiredSkills": ["python"], "recruiterEmail": "r@example.com", "minYears": 40},
            {"title": "x", "requiredSkills": ["python"], "recruiterEmail": "r@example.com", "description": "x" * 6000},
        ]
        for body in bad:
            status, out = self.call("POST /jobs", body)
            self.assertEqual(status, 400, body)
            self.assertIn("error", out)
        res = api.lambda_handler({**http("POST /jobs"), "body": "{not json"}, None)
        self.assertEqual(res["statusCode"], 400)

    def test_list_jobs_with_counts(self):
        a = self.make_job()
        b = self.make_job(title="Data Analyst")
        self.jobs.items[0]["createdAt"] = "2026-01-01T00:00:00Z"   # a is older
        self.add_candidates(b["jobId"])
        status, out = self.call("GET /jobs", key=None)
        self.assertEqual(status, 200)
        self.assertEqual([j["title"] for j in out["jobs"]], ["Data Analyst", "Cloud Engineer Intern"])
        self.assertEqual([j["candidateCount"] for j in out["jobs"]], [3, 0])
        self.assertEqual(out["totalCandidates"], 3)
        self.assertNotIn("recruiterEmail", out["jobs"][0])
        status, one = self.call("GET /jobs", query={"jobId": a["jobId"]}, key=None)
        self.assertEqual((status, one["title"]), (200, "Cloud Engineer Intern"))
        self.assertNotIn("recruiterEmail", one)
        self.assertEqual(self.call("GET /jobs", query={"jobId": UNKNOWN})[0], 404)

    # ------------------------------------------------------------ uploads

    def test_upload_url(self):
        job = self.make_job()
        status, out = self.call("POST /upload-url", {
            "jobId": job["jobId"], "name": "Ananya", "email": "a@example.com",
            "contentType": "application/pdf", "fileSize": 120000}, key=None)
        self.assertEqual(status, 200)
        self.assertEqual(out["s3Key"], f"resumes/{job['jobId']}/{out['candidateId']}.pdf")
        self.assertTrue(out["uploadUrl"].startswith(
            "https://resumerank-resumes-test.s3.ap-south-1.amazonaws.com/resumes/"))
        self.assertIn("X-Amz-SignedHeaders=content-length%3Bcontent-type%3Bhost", out["uploadUrl"])
        self.assertIn("X-Amz-Expires=300", out["uploadUrl"])
        pending = self.cands.puts[0]
        self.assertEqual((pending["status"], pending["score"], pending["email"]), ("PENDING", 0, "a@example.com"))

    def test_upload_url_email_optional_for_bulk_upload(self):
        job = self.make_job()
        status, _ = self.call("POST /upload-url", {"jobId": job["jobId"], "name": "bulk.pdf",
                                                   "contentType": "application/pdf", "fileSize": 10})
        self.assertEqual(status, 200)
        self.assertNotIn("email", self.cands.puts[0])

    def test_upload_url_validation(self):
        job = self.make_job()
        base = {"jobId": job["jobId"], "name": "A", "email": "a@example.com",
                "contentType": "application/pdf", "fileSize": 1000}
        cases = [({"contentType": "image/png"}, 400), ({"fileSize": 6 * 1024 * 1024}, 400),
                 ({"fileSize": "1000"}, 400), ({"jobId": "not-a-uuid"}, 400),
                 ({"email": "nope"}, 400), ({"jobId": UNKNOWN}, 404)]
        for change, expected in cases:
            status, _ = self.call("POST /upload-url", {**base, **change})
            self.assertEqual(status, expected, change)
        self.assertEqual(self.cands.puts, [])

    # ------------------------------------------------------------ leaderboard

    def test_candidates_ranked(self):
        job = self.make_job()
        self.add_candidates(job["jobId"])
        status, out = self.call("GET /candidates", query={"jobId": job["jobId"]})
        self.assertEqual(status, 200)
        self.assertEqual([c["name"] for c in out["candidates"]], ["High", "Low", "Waiting"])
        self.assertEqual([c["rank"] for c in out["candidates"]], [1, 2, 3])
        self.assertEqual([c["decision"] for c in out["candidates"]], ["SHORTLISTED", "NONE", "NONE"])
        self.assertEqual(out["candidates"][1]["skillScore"], 24)
        self.assertEqual(out["candidates"][1]["email"], "low@example.com")   # recruiter-only route
        self.assertEqual(out["job"]["requiredSkills"], ["aws", "docker", "python"])
        self.assertEqual(self.cands.last_query["IndexName"], "ScoreIndex")
        self.assertFalse(self.cands.last_query["ScanIndexForward"])

    def test_candidates_unknown_job(self):
        self.assertEqual(self.call("GET /candidates", query={"jobId": UNKNOWN})[0], 404)
        self.assertEqual(self.call("GET /candidates")[0], 400)

    # ------------------------------------------------------------ decisions, resume view, status

    def test_decision(self):
        job = self.make_job()
        self.add_candidates(job["jobId"])
        cid = "11111111-1111-4111-8111-111111111111"
        status, out = self.call("POST /decision", {"jobId": job["jobId"], "candidateId": cid, "decision": "shortlisted"})
        self.assertEqual((status, out["decision"]), (200, "SHORTLISTED"))
        self.assertEqual(self.cands.updates[-1]["ExpressionAttributeValues"][":d"], "SHORTLISTED")
        self.assertEqual(self.cands._find({"candidateId": cid})["decision"], "SHORTLISTED")
        self.assertEqual(self.call("POST /decision", {"jobId": job["jobId"], "candidateId": cid,
                                                      "decision": "hire"})[0], 400)
        self.assertEqual(self.call("POST /decision", {"jobId": job["jobId"], "candidateId": UNKNOWN,
                                                      "decision": "REJECTED"})[0], 404)

    def test_resume_url(self):
        job = self.make_job()
        self.add_candidates(job["jobId"])
        cid = "11111111-1111-4111-8111-111111111111"
        self.s3.head_object = mock.Mock(return_value={})
        status, out = self.call("GET /resume-url", query={"jobId": job["jobId"], "candidateId": cid})
        self.assertEqual(status, 200)
        self.assertIn(f"/resumes/{job['jobId']}/{cid}.pdf?", out["url"])
        self.assertIn("response-content-disposition=inline", out["url"])
        self.s3.head_object = mock.Mock(side_effect=ClientError({"Error": {"Code": "404"}}, "HeadObject"))
        status, out = self.call("GET /resume-url", query={"jobId": job["jobId"], "candidateId": cid})
        self.assertEqual(status, 404)
        self.assertIn("7 days", out["error"])

    def test_status_for_candidate(self):
        job = self.make_job()
        self.add_candidates(job["jobId"])
        status, out = self.call("GET /status", query={"jobId": job["jobId"],
                                                      "candidateId": "11111111-1111-4111-8111-111111111111"}, key=None)
        self.assertEqual(status, 200)
        self.assertEqual((out["status"], out["score"], out["missingSkills"]), ("SCORED", 44, ["aws"]))
        self.assertNotIn("decision", out)
        self.assertNotIn("email", out)
        status, pending = self.call("GET /status", query={"jobId": job["jobId"],
                                                          "candidateId": "33333333-3333-4333-8333-333333333333"})
        self.assertIsNone(pending["score"])
        self.assertEqual(self.call("GET /status", query={"jobId": job["jobId"], "candidateId": UNKNOWN})[0], 404)

    # ------------------------------------------------------------ skill extraction

    def test_extract_skills_from_job_description(self):
        status, out = self.call("POST /skills/extract", {
            "text": "We want a backend intern comfortable with Python and Amazon Web Services. "
                    "Experience with Docker on Ubuntu and writing SQL queries is a plus."}, key=None)
        self.assertEqual(status, 200)
        self.assertEqual(out["skills"][:2], ["python", "aws"])
        self.assertTrue({"docker", "linux", "sql"} <= set(out["skills"]))
        self.assertEqual(self.call("POST /skills/extract", {"text": ""})[0], 400)

    def test_unknown_route(self):
        self.assertEqual(self.call("DELETE /jobs")[0], 404)

    # ------------------------------------------------------------ tier 2: job status and deadline

    def upload(self, job_id, email="a@example.com", name="A", key=None):
        body = {"jobId": job_id, "name": name, "contentType": "application/pdf", "fileSize": 1000}
        if email:
            body["email"] = email
        return self.call("POST /upload-url", body, key=key)

    def test_new_job_is_open_with_defaults(self):
        job = self.make_job()
        self.assertEqual((job["status"], job["alertThreshold"]), ("OPEN", 75))
        self.assertNotIn("deadline", job)
        tomorrow = (api.today_local() + timedelta(days=1)).isoformat()
        job = self.make_job(deadline=tomorrow, alertThreshold=90)
        self.assertEqual((job["deadline"], job["alertThreshold"]), (tomorrow, 90))

    def test_job_field_validation(self):
        yesterday = (api.today_local() - timedelta(days=1)).isoformat()
        base = {"title": "x", "requiredSkills": ["python"], "recruiterEmail": "r@example.com"}
        for extra in ({"deadline": "31/10/2026"}, {"deadline": yesterday}, {"alertThreshold": 49},
                      {"alertThreshold": 101}, {"alertThreshold": "high"}):
            self.assertEqual(self.call("POST /jobs", {**base, **extra})[0], 400, extra)

    def test_close_and_reopen_job(self):
        job = self.make_job()
        status, out = self.call("POST /jobs/status", {"jobId": job["jobId"], "status": "closed"})
        self.assertEqual((status, out["status"]), (200, "CLOSED"))
        self.assertEqual(self.jobs._find({"jobId": job["jobId"]})["status"], "CLOSED")
        status, out = self.upload(job["jobId"])
        self.assertEqual(status, 400)
        self.assertIn("closed", out["error"])
        self.assertEqual(self.call("POST /jobs/status", {"jobId": job["jobId"], "status": "OPEN"})[0], 200)
        self.assertEqual(self.upload(job["jobId"])[0], 200)
        self.assertEqual(self.call("POST /jobs/status", {"jobId": job["jobId"], "status": "PAUSED"})[0], 400)
        self.assertEqual(self.call("POST /jobs/status", {"jobId": UNKNOWN, "status": "OPEN"})[0], 404)
        self.assertEqual(self.call("POST /jobs/status", {"jobId": job["jobId"], "status": "OPEN"}, key=None)[0], 401)

    def test_past_deadline_blocks_uploads(self):
        job = self.make_job()
        self.jobs._find({"jobId": job["jobId"]})["deadline"] = (api.today_local() - timedelta(days=1)).isoformat()
        status, out = self.upload(job["jobId"])
        self.assertEqual(status, 400)
        self.assertIn("deadline", out["error"])
        self.jobs._find({"jobId": job["jobId"]})["deadline"] = api.today_local().isoformat()   # still open today
        self.assertEqual(self.upload(job["jobId"])[0], 200)

    def test_public_list_hides_closed_and_expired_jobs(self):
        open_job = self.make_job(title="Open")
        closed = self.make_job(title="Closed")
        expired = self.make_job(title="Expired")
        self.call("POST /jobs/status", {"jobId": closed["jobId"], "status": "CLOSED"})
        self.jobs._find({"jobId": expired["jobId"]})["deadline"] = "2020-01-01"
        legacy = {"jobId": "44444444-4444-4444-8444-444444444444", "title": "Legacy", "requiredSkills": {"go"},
                  "minYears": 0, "createdAt": "2026-01-01T00:00:00Z"}   # created before the status field
        self.jobs.items.append(legacy)
        _, public = self.call("GET /jobs", key=None)
        self.assertEqual(sorted(j["title"] for j in public["jobs"]), ["Legacy", "Open"])
        _, recruiter = self.call("GET /jobs")
        by_title = {j["title"]: j for j in recruiter["jobs"]}
        self.assertEqual(len(by_title), 4)
        self.assertEqual((by_title["Closed"]["status"], by_title["Closed"]["acceptingApplications"]), ("CLOSED", False))
        self.assertFalse(by_title["Expired"]["acceptingApplications"])
        self.assertEqual(by_title["Legacy"]["status"], "OPEN")
        _, one = self.call("GET /jobs", query={"jobId": closed["jobId"]}, key=None)   # shared link still explains
        self.assertFalse(one["acceptingApplications"])
        self.assertTrue(open_job["jobId"] in {j["jobId"] for j in public["jobs"]})

    # ------------------------------------------------------------ tier 2: duplicate applications

    def test_reapplying_supersedes_earlier_application(self):
        job = self.make_job()
        _, first = self.upload(job["jobId"], email="Dup@Example.com")
        self.cands._find({"candidateId": first["candidateId"]}).update(status="SCORED", score=Decimal(60))
        failed = {"candidateId": "55555555-5555-4555-8555-555555555555"}   # an earlier failed attempt
        self.cands.items.append({"jobId": job["jobId"], "status": "FAILED", "score": Decimal(0),
                                 "email": "dup@example.com", **failed})
        _, other = self.upload(job["jobId"], email="someone@example.com")
        status, second = self.upload(job["jobId"], email="dup@example.com")
        self.assertEqual(status, 200)
        self.assertEqual(second["supersedes"], [first["candidateId"]])   # the FAILED one is left alone
        old = self.cands._find({"candidateId": first["candidateId"]})
        self.assertEqual((old["status"], old["supersededBy"]), ("SUPERSEDED", second["candidateId"]))
        self.assertEqual(self.cands._find({"candidateId": failed["candidateId"]})["status"], "FAILED")
        self.assertEqual(self.cands._find({"candidateId": other["candidateId"]})["status"], "PENDING")
        self.assertEqual(self.cands._find({"candidateId": second["candidateId"]})["email"], "dup@example.com")

    def test_bulk_uploads_without_email_never_supersede(self):
        job = self.make_job()
        self.upload(job["jobId"], email=None, name="a.pdf")
        _, out = self.upload(job["jobId"], email=None, name="a.pdf")
        self.assertEqual(out["supersedes"], [])

    def test_superseded_rows_are_unranked(self):
        job = self.make_job()
        self.add_candidates(job["jobId"])
        self.cands.items[1]["status"] = "SUPERSEDED"   # "High", score 100
        _, out = self.call("GET /candidates", query={"jobId": job["jobId"]})
        ranks = {c["name"]: c["rank"] for c in out["candidates"]}
        self.assertEqual(ranks, {"High": None, "Low": 1, "Waiting": 2})

    # ------------------------------------------------------------ tier 2: notes

    def test_notes(self):
        job = self.make_job()
        self.add_candidates(job["jobId"])
        cid = "11111111-1111-4111-8111-111111111111"
        status, out = self.call("POST /decision", {"jobId": job["jobId"], "candidateId": cid, "note": "  good AWS projects "})
        self.assertEqual((status, out), (200, {"jobId": job["jobId"], "candidateId": cid, "note": "good AWS projects"}))
        stored = self.cands._find({"candidateId": cid})
        self.assertEqual(stored["note"], "good AWS projects")
        self.assertNotIn("decision", stored)                     # note-only keeps the decision as it was
        self.call("POST /decision", {"jobId": job["jobId"], "candidateId": cid, "decision": "REJECTED", "note": "no visa"})
        self.assertEqual((stored["decision"], stored["note"]), ("REJECTED", "no visa"))
        self.call("POST /decision", {"jobId": job["jobId"], "candidateId": cid, "note": ""})
        self.assertNotIn("note", stored)
        self.assertEqual(stored["decision"], "REJECTED")
        _, board = self.call("GET /candidates", query={"jobId": job["jobId"]})
        self.assertIn("note", board["candidates"][0])
        for bad in ({"note": "x" * 501}, {"note": 5}, {}):
            self.assertEqual(self.call("POST /decision", {"jobId": job["jobId"], "candidateId": cid, **bad})[0], 400, bad)

    # ------------------------------------------------------------ tier 2: send shortlist

    def test_send_shortlist(self):
        job = self.make_job()
        self.add_candidates(job["jobId"])
        self.cands.items[0].update(decision="SHORTLISTED", note="strong SQL")
        status, out = self.call("POST /shortlist/send", {"jobId": job["jobId"]})
        self.assertEqual((status, out["sent"]), (200, 2))
        kwargs = self.sns.publish.call_args.kwargs
        self.assertTrue(kwargs["TopicArn"].endswith(":resumerank-alerts"))
        self.assertEqual(kwargs["Subject"], "ResumeRank shortlist: Cloud Engineer Intern (2 candidates)")
        body = kwargs["Message"]
        self.assertLess(body.index("#1  High"), body.index("#2  Low"))
        self.assertIn("score 100", body)
        self.assertIn("low@example.com", body)
        self.assertIn("note:    strong SQL", body)
        self.assertNotIn("Waiting", body)

    def test_send_shortlist_rules(self):
        job = self.make_job()
        status, out = self.call("POST /shortlist/send", {"jobId": job["jobId"]})
        self.assertEqual(status, 400)
        self.assertIn("nobody is shortlisted", out["error"])
        self.assertEqual(self.call("POST /shortlist/send", {"jobId": UNKNOWN})[0], 404)
        self.assertEqual(self.call("POST /shortlist/send", {"jobId": job["jobId"]}, key=None)[0], 401)
        with mock.patch.object(api, "SNS_TOPIC_ARN", ""):
            self.assertEqual(self.call("POST /shortlist/send", {"jobId": job["jobId"]})[0], 500)
        self.sns.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
