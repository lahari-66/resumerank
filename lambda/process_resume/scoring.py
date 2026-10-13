"""ResumeRank scoring (blueprint section 12).

Pure Python, no AWS calls, so it can be unit-tested locally.

    skill_score = (|matched| / |required|) * 60
    exp_score   = min(years / max(min_years, 1), 1.0) * 20
                  (fresher roles, min_years == 0: 20 if any internship/project dates found)
    edu_score   = 20 if a degree keyword is found else 10
    total       = round(skill_score + exp_score + edu_score)
"""

import json
import math
import os
import re
from datetime import datetime, timezone
from functools import lru_cache

SKILLS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills.json")

SKILL_WEIGHT = 60
EXP_WEIGHT = 20
EDU_FULL = 20
EDU_NONE = 10
MAX_YEARS = 15

DEGREE_PATTERNS = [
    r"b\.?\s?tech",
    r"b\.\s?e\.?",
    r"bachelor",
    r"m\.?\s?tech",
    r"m\.?\s?c\.?\s?a",
    r"b\.?\s?sc",
    r"m\.?\s?sc",
    r"ph\.?\s?d",
]
DEGREE_RE = re.compile(r"(?<![a-z])(?:" + "|".join(DEGREE_PATTERNS) + r")", re.IGNORECASE)

EXPLICIT_YEARS_RE = re.compile(r"(?<![\d.])(\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)(?![a-z])", re.IGNORECASE)

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTH = r"(?<![a-z])(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_POINT = (
    r"(?:(?P<{p}m>" + _MONTH + r")\s*,?\s*(?P<{p}y>(?:19|20)\d{{2}})(?!\d)"
    r"|(?<!\d)(?P<{p}n>\d{{1,2}})\s*/\s*(?P<{p}ny>(?:19|20)\d{{2}})(?!\d)"
    r"|(?<!\d)(?P<{p}o>(?:19|20)\d{{2}})(?!\d))"
)
_OPEN_END = r"(?P<now>present|current|now|till\s+date|to\s+date|ongoing|today)"
RANGE_RE = re.compile(
    _POINT.format(p="s") + r"\s*(?:-|–|—|to|till|until)\s*(?:" + _POINT.format(p="e") + "|" + _OPEN_END + ")",
    re.IGNORECASE,
)

EDUCATION_HEADINGS = (
    "education", "educational qualification", "educational qualifications", "academic",
    "academics", "academic qualification", "academic qualifications", "academic details",
    "qualification", "qualifications", "academic background", "education and training",
)
OTHER_HEADINGS = (
    "experience", "work experience", "professional experience", "employment", "employment history",
    "internship", "internships", "projects", "academic projects", "personal projects", "skills",
    "technical skills", "key skills", "core skills", "certifications", "certificates", "achievements",
    "awards", "summary", "professional summary", "profile", "objective", "career objective",
    "activities", "extracurricular activities", "publications", "languages", "hobbies", "interests",
    "declaration", "contact", "personal details", "training", "positions of responsibility",
)

@lru_cache(maxsize=4)
def load_skills(path=SKILLS_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _normalise(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _alias_pattern(alias):
    return re.compile(r"(?<![a-z0-9])" + re.escape(alias.lower()) + r"(?![a-z0-9+#])")


def _alias_map(dictionary):
    """alias -> canonical, including each canonical name mapped to itself."""
    mapping = {}
    for canonical, aliases in dictionary["skills"].items():
        mapping[canonical.lower()] = canonical
        for alias in aliases:
            mapping.setdefault(alias.lower(), canonical)
    return mapping


def canonicalise(skill, dictionary=None):
    dictionary = dictionary or load_skills()
    key = _normalise(skill)
    return _alias_map(dictionary).get(key, key)


def _search_terms(dictionary, extra=()):
    """canonical -> list of compiled patterns. Unknown required skills match on their own name."""
    no_bare = set(dictionary.get("noBareMatch", []))
    terms = {}
    for canonical, aliases in dictionary["skills"].items():
        names = list(aliases) if canonical in no_bare else [canonical] + list(aliases)
        terms[canonical] = [_alias_pattern(a) for a in names if a]
    for skill in extra:
        if skill not in terms:
            terms[skill] = [_alias_pattern(skill)]
    return terms


def find_skills(text, key_phrases=(), dictionary=None, extra=()):
    """Two passes: alias search over the OCR text, then over Comprehend key phrases."""
    dictionary = dictionary or load_skills()
    terms = _search_terms(dictionary, extra)
    found = set()

    body = _normalise(text)
    for canonical, patterns in terms.items():
        if any(p.search(body) for p in patterns):
            found.add(canonical)

    for phrase in key_phrases:
        phrase = _normalise(phrase)
        if not phrase:
            continue
        for canonical, patterns in terms.items():
            if canonical not in found and any(p.search(phrase) for p in patterns):
                found.add(canonical)
    return found


def has_degree(text):
    return bool(DEGREE_RE.search(text or ""))


def _heading_of(line):
    cleaned = re.sub(r"[^a-z &]", "", line.lower()).strip()
    if not cleaned or len(cleaned) > 40:
        return None
    if cleaned in EDUCATION_HEADINGS:
        return "education"
    if cleaned in OTHER_HEADINGS:
        return "other"
    return None


def education_spans(text):
    """Character spans of the EDUCATION section, so degree years are not counted as experience."""
    spans, start, pos = [], None, 0
    for line in (text or "").splitlines(keepends=True):
        heading = _heading_of(line)
        if heading == "education" and start is None:
            start = pos
        elif heading == "other" and start is not None:
            spans.append((start, pos))
            start = None
        pos += len(line)
    if start is not None:
        spans.append((start, pos))
    return spans


def _in_spans(offset, spans):
    return any(a <= offset < b for a, b in spans)


def _month_index(match, prefix):
    if match.group(prefix + "m"):
        month = _MONTHS.index(match.group(prefix + "m")[:3].lower())
        return int(match.group(prefix + "y")) * 12 + month
    if match.group(prefix + "n"):
        month = min(max(int(match.group(prefix + "n")), 1), 12) - 1
        return int(match.group(prefix + "ny")) * 12 + month
    if match.group(prefix + "o"):
        return int(match.group(prefix + "o")) * 12
    return None


def _ranges_in(fragment, now):
    now_index = now.year * 12 + now.month - 1
    out = []
    for m in RANGE_RE.finditer(fragment):
        start = _month_index(m, "s")
        end = now_index if m.group("now") else _month_index(m, "e")
        if start is None or end is None or end <= start or end > now_index + 1:
            continue
        out.append((start, end))
    return out


def _merged_months(intervals):
    total, cur_start, cur_end = 0, None, None
    for start, end in sorted(intervals):
        if cur_end is None or start > cur_end:
            if cur_end is not None:
                total += cur_end - cur_start
            cur_start, cur_end = start, end
        else:
            cur_end = max(cur_end, end)
    if cur_end is not None:
        total += cur_end - cur_start
    return total


def estimate_experience(text, date_entities=(), now=None):
    """Return (years, has_dates).

    (a) explicit "N years" / "N+ yrs" mentions;
    (b) date ranges ("2021 - 2023", "Jun 2022 - Present") from the text and from Comprehend
        DATE entities, outside the education section, merged so overlaps are not double-counted.
    The larger of (a) and (b) is taken and capped at 15.

    date_entities: dicts with "Text" and "BeginOffset" (offset into the full text).
    """
    now = now or datetime.now(timezone.utc)
    text = text or ""
    edu = education_spans(text)

    explicit = 0.0
    for m in EXPLICIT_YEARS_RE.finditer(text):
        if not _in_spans(m.start(), edu):
            explicit = max(explicit, float(m.group(1)))

    intervals = []
    for m in RANGE_RE.finditer(text):
        if not _in_spans(m.start(), edu):
            intervals.extend(_ranges_in(m.group(0), now))

    outside = sorted(
        (e for e in date_entities if not _in_spans(e.get("BeginOffset", -1), edu)),
        key=lambda e: e.get("BeginOffset", 0),
    )
    for i, ent in enumerate(outside):
        intervals.extend(_ranges_in(ent.get("Text", ""), now))
        # Comprehend often returns "Jun 2022" and "Present" as two entities joined by a dash
        if i + 1 < len(outside):
            nxt = outside[i + 1]
            a, b = ent.get("BeginOffset", 0), nxt.get("BeginOffset", 0) + len(nxt.get("Text", ""))
            if 0 <= a < b <= len(text) and b - a < 60:
                intervals.extend(_ranges_in(text[a:b], now))

    from_ranges = _merged_months(intervals) / 12.0
    years = min(max(explicit, from_ranges), MAX_YEARS)
    has_dates = bool(intervals) or any(re.search(r"(?:19|20)\d{2}", e.get("Text", "")) for e in outside)
    return round(years, 1), has_dates


def _round_half_up(x):
    return int(math.floor(x + 0.5))


def score_candidate(text, required_skills, min_years=0, key_phrases=(), date_entities=(),
                    dictionary=None, now=None):
    dictionary = dictionary or load_skills()
    required = sorted({canonicalise(s, dictionary) for s in required_skills if s and s.strip()})
    if not required:
        raise ValueError("job has no required skills")

    found = find_skills(text, key_phrases, dictionary, extra=required)
    matched = [s for s in required if s in found]
    missing = [s for s in required if s not in found]
    skill_score = len(matched) / len(required) * SKILL_WEIGHT

    years, has_dates = estimate_experience(text, date_entities, now)
    min_years = int(min_years or 0)
    if min_years == 0:
        exp_score = float(EXP_WEIGHT) if (has_dates or years > 0) else 0.0
    else:
        exp_score = min(years / max(min_years, 1), 1.0) * EXP_WEIGHT

    edu_score = float(EDU_FULL if has_degree(text) else EDU_NONE)

    return {
        "score": _round_half_up(skill_score + exp_score + edu_score),
        "skillScore": round(skill_score, 2),
        "expScore": round(exp_score, 2),
        "eduScore": edu_score,
        "matchedSkills": matched,
        "missingSkills": missing,
        "yearsExperience": years,
    }
