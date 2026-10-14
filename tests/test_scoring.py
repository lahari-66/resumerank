"""Local tests for lambda/process_resume/scoring.py (blueprint T1.4).

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lambda", "process_resume"))

import scoring  # noqa: E402

NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)
JOB_SKILLS = ["python", "aws", "docker", "linux", "sql"]   # docs/test_matrix.md test job
JOB_MIN_YEARS = 2
RESUMES = os.path.join(ROOT, "tests", "resumes")


def score(text, skills=JOB_SKILLS, min_years=JOB_MIN_YEARS, **kw):
    return scoring.score_candidate(text, skills, min_years, now=NOW, **kw)


class ThreeSampleTexts(unittest.TestCase):
    """The three pasted texts from the Day 1 Hr 6 plan: strong, partial, none."""

    STRONG = """Priya S
    EXPERIENCE
    Backend Developer, Acme Corp   2021 - 2024
    Built REST APIs in Flask on Amazon Web Services, containerised with Docker on Ubuntu.
    Wrote SQL against PostgreSQL. Python every day.
    EDUCATION
    B.E. Computer Science 2017 - 2021"""

    PARTIAL = """Karthik M
    Fresher. Internship at Beta Labs, Jun 2025 - Aug 2025: Python scripts and SQL reports."""

    NONE = """Meera T
    Accountant with 4 yrs experience in Tally and GST filing. B.Com 2015."""

    def test_strong(self):
        r = score(self.STRONG)
        self.assertEqual(r["matchedSkills"], sorted(JOB_SKILLS))
        self.assertEqual(r["missingSkills"], [])
        self.assertEqual(r["yearsExperience"], 3.0)
        self.assertEqual(r["eduScore"], 20)
        self.assertEqual(r["score"], 100)

    def test_partial(self):
        r = score(self.PARTIAL, min_years=0)
        self.assertEqual(r["matchedSkills"], ["python", "sql"])
        self.assertEqual(r["skillScore"], 24.0)
        self.assertEqual(r["expScore"], 20.0)        # fresher role, internship dates found
        self.assertEqual(r["eduScore"], 10)
        self.assertEqual(r["score"], 54)

    def test_none(self):
        r = score(self.NONE)
        self.assertEqual(r["matchedSkills"], [])
        self.assertEqual(r["yearsExperience"], 4.0)
        self.assertEqual(r["eduScore"], 10)          # B.Com is not in the degree list
        self.assertEqual(r["score"], 30)


class SkillMatching(unittest.TestCase):
    def test_aliases(self):
        found = scoring.find_skills("JS, Amazon Web Services, k8s, Postgres")
        self.assertTrue({"javascript", "aws", "kubernetes", "postgresql"} <= found)

    def test_word_boundaries(self):
        found = scoring.find_skills("I enjoy javascripting, prosql and awsome teams")
        self.assertNotIn("aws", found)
        self.assertNotIn("sql", found)

    def test_key_phrase_pass(self):
        found = scoring.find_skills("", key_phrases=["deployed on Amazon Web Services"])
        self.assertIn("aws", found)

    def test_ambiguous_words_need_alias(self):
        found = scoring.find_skills("Ready to go. Spring 2023 batch. Excel at teamwork.")
        self.assertFalse({"go", "spring", "excel"} & found)
        self.assertIn("go", scoring.find_skills("Golang microservices"))

    def test_required_alias_is_canonicalised(self):
        r = score("Strong JavaScript developer", skills=["JS"], min_years=0)
        self.assertEqual(r["matchedSkills"], ["javascript"])

    def test_unknown_required_skill_matches_its_own_name(self):
        r = score("Experience with Pulumi and Python", skills=["pulumi", "python"], min_years=0)
        self.assertEqual(r["matchedSkills"], ["pulumi", "python"])


class Experience(unittest.TestCase):
    def test_present_and_overlap(self):
        text = "EXPERIENCE\nA  Jan 2024 - Present\nB  Jun 2024 - Dec 2024\n"
        years, _ = scoring.estimate_experience(text, now=NOW)
        self.assertEqual(years, 2.8)                  # Jan 2024 -> Oct 2026, overlap counted once

    def test_education_dates_ignored(self):
        text = "EDUCATION\nB.Tech 2018 - 2022\nSKILLS\nPython\n"
        self.assertEqual(scoring.estimate_experience(text, now=NOW), (0.0, False))

    def test_comprehend_date_entities_paired(self):
        text = "Worked at X from March 2020 until now"
        ents = [{"Text": "March 2020", "BeginOffset": text.index("March")},
                {"Text": "now", "BeginOffset": text.index("now")}]
        years, has_dates = scoring.estimate_experience(text, ents, now=NOW)
        self.assertEqual(years, 6.6)
        self.assertTrue(has_dates)

    def test_cap(self):
        years, _ = scoring.estimate_experience("40 years of experience", now=NOW)
        self.assertEqual(years, 15)

    def test_proportional_exp_score(self):
        r = score("Python developer, 1 year", min_years=2)
        self.assertEqual(r["expScore"], 10.0)


class Education(unittest.TestCase):
    def test_degrees(self):
        for text in ["B.Tech CSE", "B.E. Mechanical", "Bachelor of Science", "M.Tech",
                     "MCA", "BSc Physics", "M.Sc", "Ph.D in Chemistry"]:
            self.assertTrue(scoring.has_degree(text), text)

    def test_non_degrees(self):
        for text in ["Diploma in Computer Engineering", "Higher Secondary", "B.Com", "I will be there"]:
            self.assertFalse(scoring.has_degree(text), text)


class SectionAwareExperience(unittest.TestCase):
    """Only work sections count as years; project and club-role dates earn the fresher credit only."""

    FRESHER = """Asha K
    B.Tech CSE · 2023 – 2027
    Education
    Lakeview University 2023 – Expected 2027
    Sunrise Junior College 2021 – 2023
    Projects
    Bus Tracker | Next.js · Express GitHub 2026
    Achievements and Positions of Responsibility
    • Head – Coding Club (Jan 2025 – Present)
    """

    def test_club_role_and_projects_are_not_work_years(self):
        years, has_dates = scoring.estimate_experience(self.FRESHER, now=NOW)
        self.assertEqual(years, 0)
        self.assertTrue(has_dates)

    def test_fresher_credit_when_min_years_is_zero(self):
        self.assertEqual(score(self.FRESHER, min_years=0)["expScore"], 20)
        self.assertEqual(score(self.FRESHER, min_years=2)["expScore"], 0)

    def test_no_dates_no_fresher_credit(self):
        self.assertEqual(score("Asha K\nSkills\nPython, SQL", min_years=0)["expScore"], 0)

    def test_education_ranges_never_count(self):
        text = "Education\nB.Tech, Riverside 2015 – 2019\nM.Tech, Riverside 2019 – 2021\nSkills\nPython"
        self.assertEqual(scoring.estimate_experience(text, now=NOW), (0, False))

    def test_work_section_after_projects_counts(self):
        text = "Projects\nTracker 2022 – 2024\nExperience\nIntern, Acme   Jun 2025 – Jun 2026"
        self.assertEqual(scoring.estimate_experience(text, now=NOW)[0], 1.0)

    def test_heading_variants(self):
        for heading in ("WORK EXPERIENCE", "Internships", "Achievements & Positions of Responsibility"):
            self.assertIsNotNone(scoring._heading_of(heading), heading)


class RealCvSkills(unittest.TestCase):
    def test_skills_inside_parentheses(self):
        found = scoring.find_skills("Cloud: AWS (Lambda, API Gateway, DynamoDB, S3, Cognito), Docker")
        self.assertTrue({"aws", "lambda", "api gateway", "dynamodb", "s3", "cognito", "docker"} <= found)

    def test_web_stack(self):
        found = scoring.find_skills(
            "Next.js · TypeScript · Express · MongoDB · Razorpay; JWT Authentication, Zod, bcrypt; "
            "Vitest/Supertest tests; deployed on Vercel with Supabase and AWS Amplify; Tailwind CSS, React")
        for skill in ("next.js", "typescript", "express", "mongodb", "razorpay", "jwt", "zod", "bcrypt", "vitest",
                      "supertest", "vercel", "supabase", "amplify", "tailwind", "react"):
            self.assertIn(skill, found)

    def test_ml_stack(self):
        found = scoring.find_skills(
            "PyTorch, TensorFlow/Keras, scikit-learn, Pandas, NumPy, OpenCV, LoRA; FastAPI, Streamlit; "
            "PySpark, Kafka, Spark Structured Streaming, MLlib; WebRTC, Twilio, Gemini 2.0 Flash; pytest, GitHub Actions")
        for skill in ("pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy", "opencv", "lora", "fastapi",
                      "streamlit", "pyspark", "spark", "kafka", "mllib", "webrtc", "twilio", "gemini", "pytest",
                      "github actions"):
            self.assertIn(skill, found)

    def test_postgresql_is_not_sql(self):
        self.assertNotIn("sql", scoring.find_skills("Databases: PostgreSQL, MongoDB"))

    def test_common_words_do_not_match(self):
        self.assertNotIn("next.js", scoring.find_skills("Next steps: build the next release"))


class TestResumes(unittest.TestCase):
    """Expected scores and bands from docs/test_matrix.md, scored on the source text (no OCR)."""

    EXPECTED = {   # id: (exact expected score, band low, band high, matched skills)
        "R1": (100, 90, 100, {"python", "aws", "docker", "linux", "sql"}),
        "R2": (90, 85, 95, {"python", "aws", "docker", "linux", "sql"}),
        "R3": (100, 85, 100, {"python", "aws", "docker", "linux", "sql"}),
        "R4": (44, 40, 55, {"python", "sql"}),
        "R5": (40, 30, 40, set()),
        "R6": (100, 95, 100, {"python", "aws", "docker", "linux", "sql"}),
        "R7": (32, 25, 40, {"aws"}),
        "R8": (78, 70, 85, {"python", "aws", "docker", "sql"}),
    }

    def read(self, rid):
        with open(os.path.join(RESUMES, f"{rid}.txt"), encoding="utf-8") as f:
            return f.read()

    def test_expected_scores_and_bands(self):
        for rid, (expected, lo, hi, matched) in self.EXPECTED.items():
            with self.subTest(rid):
                r = score(self.read(rid))
                self.assertEqual(r["score"], expected)
                self.assertTrue(lo <= r["score"] <= hi)
                self.assertEqual(set(r["matchedSkills"]), matched)

    def test_r6_matches_r1(self):
        self.assertLessEqual(abs(score(self.read("R6"))["score"] - score(self.read("R1"))["score"]), 5)

    def test_r2_uses_aliases_only(self):
        lowered = self.read("R2").lower()
        for bare in ("python ", "python,", " aws", "docker ", "linux"):
            self.assertNotIn(bare, lowered)

    def test_r7_fresher_and_r8_internship(self):
        self.assertEqual(score(self.read("R7"))["yearsExperience"], 0)
        self.assertEqual(score(self.read("R7"), min_years=0)["expScore"], 20)
        self.assertEqual(score(self.read("R8"))["yearsExperience"], 1.0)

    def test_pdf_text_layer_scores_like_source(self):
        try:
            import pypdf
        except ImportError:
            self.skipTest("pypdf not installed")
        for rid in self.EXPECTED:
            with self.subTest(rid):
                reader = pypdf.PdfReader(os.path.join(RESUMES, f"{rid}.pdf"))
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
                if rid == "R3":
                    self.assertEqual(text.strip(), "")   # image-only scan
                    continue
                self.assertEqual(score(text)["score"], self.EXPECTED[rid][0])
                if rid == "R6":
                    self.assertEqual(len(reader.pages), 2)


if __name__ == "__main__":
    unittest.main()
