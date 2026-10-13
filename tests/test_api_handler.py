"""Local tests for the api_handler Lambda with AWS calls replaced by in-memory fakes.

Needs boto3 installed locally (it is bundled in the Lambda runtime). No AWS account is used:
fake credentials are set before import and every client is swapped for a fake.

    python -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import unittest
from decimal import Decimal
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.update({
    "AWS_DEFAULT_REGION": "ap-south-1",
    "AWS_REGION": "ap-south-1",
    "AWS_ACCESS_KEY_ID": "AKIATESTONLY",
    "AWS_SECRET_ACCESS_KEY": "test-only",
    "RESUMES_BUCKET": "resumerank-resumes-test",
    "SNS_TOPIC_ARN": "arn:aws:sns:ap-south-1:000000000000:resumerank-alerts",
})

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

api = load("api_handler_fn", os.path.join(ROOT, "lambda", "api_handler", "lambda_function.py"))

class FakeTable:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.updates, self.puts = [], []

    def get_item(self, Key):
        for item in self.items:
            if all(item.get(k) == v for k, v in Key.items()):
                return {"Item": dict(item)}
        return {}

    def put_item(self, Item):
        self.puts.append(Item)
        self.items.append(Item)

    def update_item(self, **kwargs):
        self.updates.append(kwargs)

    def query(self, **kwargs):
        self.last_query = kwargs
        return {"Items": sorted(self.items, key=lambda i: i.get("score", 0), reverse=True)}

def http(route, body=None, query=None):
    method, path = route.split(" ")
    return {"routeKey": route, "rawPath": path, "body": json.dumps(body) if body is not None else None,
            "queryStringParameters": query, "requestContext": {"http": {"method": method, "path": path}}}


class ApiHandlerTests(unittest.TestCase):
    def setUp(self):
        self.jobs = FakeTable()
        self.cands = FakeTable()
        self.patches = [mock.patch.object(api, "jobs_table", self.jobs),
                        mock.patch.object(api, "candidates_table", self.cands),
                        mock.patch.object(api, "RESUMES_BUCKET", "resumerank-resumes-test")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def call(self, *args, **kwargs):
        res = api.lambda_handler(http(*args, **kwargs), None)
        return res["statusCode"], json.loads(res["body"])

    def make_job(self):
        status, body = self.call("POST /jobs", {
            "title": "Cloud Engineer Intern", "requiredSkills": ["Python", " AWS", "python", "docker"],
            "minYears": 2, "recruiterEmail": "recruiter@example.com"})
        self.assertEqual(status, 201)
        return body

    def test_create_job(self):
        job = self.make_job()
        self.assertRegex(job["jobId"], api.UUID_RE)
        self.assertEqual(job["requiredSkills"], ["aws", "docker", "python"])
        self.assertEqual(self.jobs.puts[0]["requiredSkills"], {"aws", "docker", "python"})

    def test_create_job_validation(self):
        bad = [
            {},
            {"title": "x", "requiredSkills": [], "recruiterEmail": "r@example.com"},
            {"title": "x", "requiredSkills": ["python"], "recruiterEmail": "not-an-email"},
            {"title": "x", "requiredSkills": ["python"], "recruiterEmail": "r@example.com", "minYears": 40},
        ]
        for body in bad:
            status, out = self.call("POST /jobs", body)
            self.assertEqual(status, 400, body)
            self.assertIn("error", out)
        res = api.lambda_handler({**http("POST /jobs"), "body": "{not json"}, None)
        self.assertEqual(res["statusCode"], 400)

    def test_upload_url(self):
        job = self.make_job()
        status, out = self.call("POST /upload-url", {
            "jobId": job["jobId"], "name": "Ananya", "email": "a@example.com",
            "contentType": "application/pdf", "fileSize": 120000})
        self.assertEqual(status, 200)
        self.assertEqual(out["s3Key"], f"resumes/{job['jobId']}/{out['candidateId']}.pdf")
        self.assertTrue(out["uploadUrl"].startswith(
            "https://resumerank-resumes-test.s3.ap-south-1.amazonaws.com/resumes/"))
        self.assertIn("X-Amz-SignedHeaders=content-length%3Bcontent-type%3Bhost", out["uploadUrl"])
        self.assertIn("X-Amz-Expires=300", out["uploadUrl"])
        self.assertEqual(out["headers"], {"Content-Type": "application/pdf"})
        pending = self.cands.puts[0]
        self.assertEqual((pending["status"], pending["score"]), ("PENDING", 0))

    def test_upload_url_validation(self):
        job = self.make_job()
        base = {"jobId": job["jobId"], "name": "A", "email": "a@example.com",
                "contentType": "application/pdf", "fileSize": 1000}
        cases = [({"contentType": "image/png"}, 400), ({"fileSize": 6 * 1024 * 1024}, 400),
                 ({"fileSize": "1000"}, 400), ({"jobId": "not-a-uuid"}, 400),
                 ({"jobId": "00000000-0000-4000-8000-000000000000"}, 404)]
        for change, expected in cases:
            status, _ = self.call("POST /upload-url", {**base, **change})
            self.assertEqual(status, expected, change)
        self.assertEqual(self.cands.puts, [])

    def test_candidates_ranked(self):
        job = self.make_job()
        self.cands.items = [
            {"jobId": job["jobId"], "candidateId": "c1", "name": "Low", "status": "SCORED",
             "score": Decimal(44), "skillScore": Decimal("24.0"), "email": "hidden@example.com"},
            {"jobId": job["jobId"], "candidateId": "c2", "name": "High", "status": "SCORED",
             "score": Decimal(100), "skillScore": Decimal("60.0")},
            {"jobId": job["jobId"], "candidateId": "c3", "name": "Waiting", "status": "PENDING", "score": Decimal(0)},
        ]
        status, out = self.call("GET /candidates", query={"jobId": job["jobId"]})
        self.assertEqual(status, 200)
        self.assertEqual([c["name"] for c in out["candidates"]], ["High", "Low", "Waiting"])
        self.assertEqual([c["rank"] for c in out["candidates"]], [1, 2, 3])
        self.assertEqual(out["candidates"][1]["skillScore"], 24)
        self.assertNotIn("email", out["candidates"][1])
        self.assertEqual(out["job"]["requiredSkills"], ["aws", "docker", "python"])
        self.assertEqual(self.cands.last_query["IndexName"], "ScoreIndex")
        self.assertFalse(self.cands.last_query["ScanIndexForward"])

    def test_candidates_unknown_job(self):
        status, _ = self.call("GET /candidates", query={"jobId": "00000000-0000-4000-8000-000000000000"})
        self.assertEqual(status, 404)
        status, _ = self.call("GET /candidates")
        self.assertEqual(status, 400)

    def test_unknown_route(self):
        status, _ = self.call("DELETE /jobs")
        self.assertEqual(status, 404)

if __name__ == "__main__":
    unittest.main()
