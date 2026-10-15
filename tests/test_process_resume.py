"""Local tests for the process_resume Lambda with AWS calls replaced by in-memory fakes.

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
    "SNS_TOPIC_ARN": "arn:aws:sns:ap-south-1:000000000000:resumerank-alerts",
})
sys.path.insert(0, os.path.join(ROOT, "lambda", "process_resume"))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

processor = load("process_resume_fn", os.path.join(ROOT, "lambda", "process_resume", "lambda_function.py"))

JOB_ID = "3f1c2a7e-5b8d-4c1e-9a0f-2d6b7e8c9a10"
CAND_ID = "a9e4d1b2-7c3f-4e5a-8b6d-0f1e2d3c4b5a"
KEY = f"resumes/{JOB_ID}/{CAND_ID}.pdf"

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
        # honour the processor's only condition: never overwrite a SUPERSEDED record
        cond = kwargs.get("ConditionExpression", "")
        if "<> :superseded" in cond:
            current = self.get_item(kwargs["Key"]).get("Item", {})
            if current.get("status") == "SUPERSEDED":
                raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        self.updates.append(kwargs)

    def query(self, **kwargs):
        self.last_query = kwargs
        return {"Items": sorted(self.items, key=lambda i: i.get("score", 0), reverse=True)}

class FakeContext:
    def get_remaining_time_in_millis(self):
        return 100000


def s3_event(key=KEY):
    return {"Records": [{"s3": {"bucket": {"name": "resumerank-resumes-test"}, "object": {"key": key}}}]}


def sqs_event(*bodies):
    return {"Records": [{"eventSource": "aws:sqs", "messageId": f"m{i}", "body": body}
                        for i, body in enumerate(bodies)]}


STRONG_LINES = ["Ananya Rao", "EXPERIENCE", "Cloud Engineer  Jul 2022 - Jun 2025",
                "Python, AWS, Docker, Linux, SQL", "EDUCATION", "B.Tech 2018 - 2022"]


class ProcessResumeTests(unittest.TestCase):
    def setUp(self):
        self.jobs = FakeTable([{"jobId": JOB_ID, "title": "Cloud Engineer Intern",
                                "requiredSkills": {"python", "aws", "docker", "linux", "sql"},
                                "minYears": Decimal(2)}])
        self.cands = FakeTable([{"jobId": JOB_ID, "candidateId": CAND_ID, "name": "Ananya Rao",
                                 "email": "a@example.com", "status": "PENDING", "score": 0}])
        self.textract = mock.Mock()
        self.comprehend = mock.Mock()
        self.comprehend.detect_key_phrases.return_value = {"KeyPhrases": [{"Text": "cloud engineer"}]}
        self.comprehend.detect_entities.return_value = {"Entities": [
            {"Type": "DATE", "Text": "Jul 2022", "BeginOffset": 0},
            {"Type": "PERSON", "Text": "Ananya Rao", "BeginOffset": 0}]}
        self.sns, self.cw, self.s3 = mock.Mock(), mock.Mock(), mock.Mock()
        self.patches = [
            mock.patch.object(processor, "s3", self.s3),
            mock.patch.object(processor, "_textract_unavailable", False),
            mock.patch.object(processor, "_comprehend_unavailable", False),
            mock.patch.object(processor, "jobs_table", self.jobs),
            mock.patch.object(processor, "candidates_table", self.cands),
            mock.patch.object(processor, "textract", self.textract),
            mock.patch.object(processor, "comprehend", self.comprehend),
            mock.patch.object(processor, "sns", self.sns),
            mock.patch.object(processor, "cloudwatch", self.cw),
            mock.patch.object(processor.time, "sleep"),
            mock.patch.object(processor, "SNS_TOPIC_ARN", os.environ["SNS_TOPIC_ARN"]),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def textract_returns(self, lines, split=2):
        blocks = [{"BlockType": "LINE", "Text": t} for t in lines]
        self.textract.start_document_text_detection.return_value = {"JobId": "tx-1"}
        self.textract.get_document_text_detection.side_effect = [
            {"JobStatus": "IN_PROGRESS"},
            {"JobStatus": "SUCCEEDED", "DocumentMetadata": {"Pages": 2},
             "Blocks": [{"BlockType": "PAGE"}] + blocks[:split], "NextToken": "t2"},
            {"JobStatus": "SUCCEEDED", "Blocks": blocks[split:]},
        ]

    def test_strong_resume_scored_alerted_and_metric_sent(self):
        self.textract_returns(STRONG_LINES)
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["status"], "SCORED")
        self.assertEqual(out["results"][0]["score"], 100)

        upd = self.cands.updates[0]
        self.assertEqual(upd["Key"], {"jobId": JOB_ID, "candidateId": CAND_ID})
        self.assertIn("REMOVE failureReason", upd["UpdateExpression"])
        values = upd["ExpressionAttributeValues"]
        self.assertEqual(values[":status"], "SCORED")
        self.assertEqual(values[":matchedSkills"], ["aws", "docker", "linux", "python", "sql"])
        self.assertIsInstance(values[":skillScore"], Decimal)
        self.assertTrue(values[":textPreview"].startswith("Ananya Rao\nEXPERIENCE"))

        self.textract.start_document_text_detection.assert_called_once_with(
            DocumentLocation={"S3Object": {"Bucket": "resumerank-resumes-test", "Name": KEY}})
        self.sns.publish.assert_called_once()
        self.assertIn("Ananya Rao scored 100", self.sns.publish.call_args.kwargs["Subject"])
        metric = self.cw.put_metric_data.call_args.kwargs
        self.assertEqual(metric["Namespace"], "ResumeRank")
        self.assertEqual(metric["MetricData"][0]["MetricName"], "CandidateScore")

    def test_job_alert_threshold_overrides_default(self):
        self.jobs.items[0]["alertThreshold"] = Decimal(80)
        self.textract_returns(["Asha", "EXPERIENCE", "Engineer   Jul 2022 - Jun 2025", "Python, AWS, Docker, Linux"])
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["score"], 78)        # skills 48 (4/5) + exp 20 + edu 10 (no degree)
        self.sns.publish.assert_not_called()                    # 78 < 80 although it is above the default 75
        self.jobs.items[0]["alertThreshold"] = Decimal(70)
        self.textract_returns(["Asha", "EXPERIENCE", "Engineer   Jul 2022 - Jun 2025", "Python, AWS, Docker, Linux"])
        processor.lambda_handler(s3_event(), FakeContext())
        self.sns.publish.assert_called_once()
        self.assertIn("70-point", self.sns.publish.call_args.kwargs["Message"])

    def test_alert_threshold_falls_back_to_default(self):
        self.assertEqual(processor.alert_threshold({}), processor.SCORE_THRESHOLD)
        self.assertEqual(processor.alert_threshold({"alertThreshold": "bad"}), processor.SCORE_THRESHOLD)
        self.assertEqual(processor.alert_threshold({"alertThreshold": Decimal(60)}), 60)

    def test_superseded_before_processing_is_skipped(self):
        self.cands.items[0]["status"] = "SUPERSEDED"
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["status"], "SUPERSEDED")
        self.textract.start_document_text_detection.assert_not_called()
        self.assertEqual(self.cands.updates, [])

    def test_superseded_while_scoring_keeps_status_and_sends_nothing(self):
        self.textract_returns(STRONG_LINES)
        original = self.textract.get_document_text_detection.side_effect

        def supersede_mid_way(*args, **kwargs):     # the candidate re-applies while Textract runs
            self.cands.items[0]["status"] = "SUPERSEDED"
            return next(original)
        self.textract.get_document_text_detection.side_effect = supersede_mid_way
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["status"], "SUPERSEDED")
        self.assertEqual(self.cands.items[0]["status"], "SUPERSEDED")
        self.assertEqual(self.cands.updates, [])
        self.sns.publish.assert_not_called()
        self.cw.put_metric_data.assert_not_called()

    def test_job_weights_and_preferred_skills_are_used(self):
        self.jobs.items[0].update(weights={"skills": Decimal(40), "experience": Decimal(40), "education": Decimal(20)},
                                  preferredSkills={"terraform", "kubernetes"})
        self.textract_returns(STRONG_LINES + ["Terraform"])
        out = processor.lambda_handler(s3_event(), FakeContext())
        values = self.cands.updates[0]["ExpressionAttributeValues"]
        self.assertEqual(values[":weights"], {"skills": 40, "experience": 40, "education": 20})
        self.assertEqual(values[":matchedPreferred"], ["terraform"])
        self.assertEqual(values[":bonusScore"], Decimal("2.0"))
        self.assertEqual(values[":skillScore"], Decimal("40.0"))
        self.assertEqual(out["results"][0]["score"], 100)                     # 40 + 40 + 20 + 2, capped
        self.assertIn("bonus 2.0 / 10", self.sns.publish.call_args.kwargs["Message"])

    def test_full_text_stored_and_truncated(self):
        self.textract_returns(STRONG_LINES + ["x" * 30000])
        processor.lambda_handler(s3_event(), FakeContext())
        values = self.cands.updates[0]["ExpressionAttributeValues"]
        self.assertEqual(len(values[":fullText"]), processor.FULL_TEXT_CHARS)
        self.assertTrue(values[":fullText"].startswith("Ananya Rao"))
        self.assertEqual(len(values[":textPreview"]), processor.PREVIEW_CHARS)

    def test_rescoring_a_failed_candidate_overwrites_everything(self):
        self.cands.items[0].update(status="PENDING", failureReason="no text layer in the PDF (scanned image)")
        self.textract_returns(STRONG_LINES)
        processor.lambda_handler(s3_event(), FakeContext())
        upd = self.cands.updates[0]
        self.assertIn("REMOVE failureReason", upd["UpdateExpression"])
        written = {name.lstrip("#") for name in upd["ExpressionAttributeNames"]}
        for field in ("status", "score", "skillScore", "expScore", "eduScore", "bonusScore", "matchedSkills",
                      "missingSkills", "matchedPreferred", "weights", "yearsExperience", "textPreview",
                      "fullText", "processedAt"):
            self.assertIn(field, written)

    def test_low_score_does_not_alert(self):
        self.textract_returns(["Imran", "Python developer"], split=1)
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertLess(out["results"][0]["score"], 75)
        self.sns.publish.assert_not_called()
        self.cw.put_metric_data.assert_called_once()

    def test_textract_failure_marks_candidate_failed(self):
        self.textract.start_document_text_detection.return_value = {"JobId": "tx-1"}
        self.textract.get_document_text_detection.side_effect = [
            {"JobStatus": "FAILED", "StatusMessage": "unsupported document"}]
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["status"], "FAILED")
        values = self.cands.updates[0]["ExpressionAttributeValues"]
        self.assertEqual(values[":s"], "FAILED")
        self.assertIn("unsupported document", values[":r"])
        self.sns.publish.assert_not_called()

    def test_comprehend_failure_still_scores(self):
        self.textract_returns(STRONG_LINES)
        self.comprehend.detect_key_phrases.side_effect = RuntimeError("throttled")
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["status"], "SCORED")

    def test_unknown_job_fails(self):
        self.jobs.items = []
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["status"], "FAILED")
        self.textract.start_document_text_detection.assert_not_called()

    def test_foreign_key_ignored(self):
        out = processor.lambda_handler(s3_event("resumes/test.pdf"), FakeContext())
        self.assertEqual(out["results"][0]["status"], "IGNORED")
        self.assertEqual(self.cands.updates, [])

    def test_url_encoded_key(self):
        self.assertEqual(processor.parse_key("resumes/a-1/b-2.pdf"), ("a-1", "b-2"))
        self.textract_returns(STRONG_LINES)
        out = processor.lambda_handler(s3_event(KEY.replace("/", "%2F")), FakeContext())
        self.assertEqual(out["results"][0]["status"], "SCORED")

    def textract_not_subscribed(self, pdf_name):
        self.textract.start_document_text_detection.side_effect = processor.ClientError(
            {"Error": {"Code": "SubscriptionRequiredException",
                       "Message": "The AWS Access Key Id needs a subscription for the service"}},
            "StartDocumentTextDetection")
        with open(os.path.join(ROOT, "tests", "resumes", pdf_name), "rb") as f:
            data = f.read()
        self.s3.get_object.side_effect = lambda **kw: {"Body": mock.Mock(read=lambda: data)}

    def test_free_plan_falls_back_to_pdf_text_layer(self):
        self.textract_not_subscribed("R1.pdf")
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0], {"key": KEY, "status": "SCORED", "score": 100})
        self.s3.get_object.assert_called_once_with(Bucket="resumerank-resumes-test", Key=KEY)
        self.sns.publish.assert_called_once()

        # a warm container remembers and skips Textract next time
        processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(self.textract.start_document_text_detection.call_count, 1)

    def test_scanned_pdf_without_textract_fails_with_reason(self):
        self.textract_not_subscribed("R3.pdf")
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["status"], "FAILED")
        reason = self.cands.updates[0]["ExpressionAttributeValues"][":r"]
        self.assertIn("no text layer", reason)

    def test_comprehend_not_subscribed_scores_and_stops_calling(self):
        self.textract_returns(STRONG_LINES)
        self.comprehend.detect_key_phrases.side_effect = processor.ClientError(
            {"Error": {"Code": "SubscriptionRequiredException", "Message": "needs a subscription"}},
            "DetectKeyPhrases")
        out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["score"], 100)
        self.textract_returns(STRONG_LINES)
        processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(self.comprehend.detect_key_phrases.call_count, 1)

    def test_textract_only_mode_does_not_fall_back(self):
        self.textract_not_subscribed("R1.pdf")
        with mock.patch.object(processor, "TEXT_SOURCE", "textract"):
            out = processor.lambda_handler(s3_event(), FakeContext())
        self.assertEqual(out["results"][0]["status"], "FAILED")
        self.s3.get_object.assert_not_called()

    def test_sqs_message_is_processed(self):
        self.textract_returns(STRONG_LINES)
        out = processor.lambda_handler(sqs_event(json.dumps(s3_event())), FakeContext())
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(out["results"][0]["score"], 100)

    def test_sqs_s3_test_event_is_ignored(self):
        out = processor.lambda_handler(
            sqs_event(json.dumps({"Service": "Amazon S3", "Event": "s3:TestEvent", "Bucket": "b"})), FakeContext())
        self.assertEqual(out, {"batchItemFailures": [], "results": []})

    def test_sqs_transient_failure_is_retried_not_marked_failed(self):
        self.textract_returns(STRONG_LINES)
        with mock.patch.object(self.cands, "update_item", side_effect=RuntimeError("throttled")):
            out = processor.lambda_handler(
                sqs_event(json.dumps(s3_event()), "not json"), FakeContext())
        self.assertEqual(out["batchItemFailures"], [{"itemIdentifier": "m0"}, {"itemIdentifier": "m1"}])
        self.sns.publish.assert_not_called()

    def test_sqs_permanent_failure_marks_candidate_failed(self):
        self.jobs.items = []
        out = processor.lambda_handler(sqs_event(json.dumps(s3_event())), FakeContext())
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(out["results"][0]["status"], "FAILED")

    def test_chunks_respect_byte_limit_and_offsets(self):
        text = "".join(f"line {i} with ünïcode ✓\n" for i in range(800))
        chunks = processor.chunk_text(text, max_bytes=5000)
        self.assertGreater(len(chunks), 1)
        for offset, chunk in chunks:
            self.assertLessEqual(len(chunk.encode("utf-8")), 5000)
            self.assertEqual(text[offset:offset + len(chunk)], chunk)

if __name__ == "__main__":
    unittest.main()
