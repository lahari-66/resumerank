"""Local tests for the api_handler Lambda with AWS calls replaced by in-memory fakes.

Needs boto3 installed locally (it is bundled in the Lambda runtime). No AWS account is used:
fake credentials are set before import and every client is swapped for a fake.

    python -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import sys
import unittest
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


class FakeTable:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.updates, self.puts = [], []

    def _match(self, item, key):
        return all(item.get(k) == v for k, v in key.items())

    def get_item(self, Key):
        for item in self.items:
            if self._match(item, Key):
                return {"Item": dict(item)}
        return {}

    def put_item(self, Item):
        self.puts.append(Item)
        self.items.append(Item)

    def update_item(self, **kwargs):
        if "attribute_exists" in kwargs.get("ConditionExpression", "") and not self.get_item(kwargs["Key"]):
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        self.updates.append(kwargs)

    def scan(self, **kwargs):
        return {"Items": list(self.items)}

    def query(self, **kwargs):
        self.last_query = kwargs
        job_id = kwargs["KeyConditionExpression"].get_expression()["values"][1]
        rows = [i for i in self.items if i.get("jobId") == job_id]
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
        self.patches = [mock.patch.object(api, "jobs_table", self.jobs),
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


if __name__ == "__main__":
    unittest.main()
