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


class TestResumes(unittest.TestCase):
    """Expected bands from docs/test_matrix.md, scored on the source text (no OCR)."""

    BANDS = {"R1": (90, 100), "R2": (85, 95), "R3": (85, 100), "R4": (40, 55), "R5": (30, 40), "R6": (90, 100)}

    def test_bands(self):
        scores = {}
        for rid, (lo, hi) in self.BANDS.items():
            with open(os.path.join(RESUMES, f"{rid}.txt"), encoding="utf-8") as f:
                scores[rid] = score(f.read())["score"]
            self.assertTrue(lo <= scores[rid] <= hi, f"{rid} scored {scores[rid]}, expected {lo}-{hi}")
        self.assertLessEqual(abs(scores["R6"] - scores["R1"]), 5)


if __name__ == "__main__":
    unittest.main()
