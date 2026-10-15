"""ResumeRank scoring (blueprint section 12).

Pure Python, no AWS calls, so it can be unit-tested locally.

    skill_score = (|matched| / |required|) * 60
    exp_score   = min(years / max(min_years, 1), 1.0) * 20
                  (fresher roles, min_years == 0: 20 if any internship/project dates found)
    edu_score   = 20 if a degree keyword is found else 10
    total       = round(skill_score + exp_score + edu_score)

Per-job options (INTERFACES.md): weights {skills, experience, education} summing to 100 replace
60/20/20 (no degree = half the education weight), and every preferred skill found adds 2 bonus
points up to 10. The total is capped at 100.
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
DEFAULT_WEIGHTS = {"skills": SKILL_WEIGHT, "experience": EXP_WEIGHT, "education": EDU_FULL}
BONUS_PER_PREFERRED = 2
MAX_BONUS = 10

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

# Section headings decide which dates count as work experience.
#   education – never counted (degree years are not experience)
#   work      – counted towards years of experience
#   activity  – projects, hackathons, club roles: dates earn the fresher credit but are not work years
#   neutral   – summary, skills, ... (and text before the first heading): counted, as before
SECTION_HEADINGS = {
    "education": (
        "education", "educational qualification", "educational qualifications", "academic", "academics",
        "academic qualification", "academic qualifications", "academic details", "qualification",
        "qualifications", "academic background", "education and training",
    ),
    "work": (
        "experience", "work experience", "professional experience", "employment", "employment history",
        "internship", "internships", "work history", "industry experience", "internship experience",
        "experience and internships", "relevant experience",
    ),
    "activity": (
        "projects", "academic projects", "personal projects", "key projects", "project", "achievements",
        "awards", "honours", "honors", "achievements and awards", "positions of responsibility",
        "achievements and positions of responsibility", "leadership", "leadership and activities",
        "activities", "extracurricular activities", "extra curricular activities", "co curricular activities",
        "hackathons", "volunteering", "certifications", "certificates", "publications", "training",
    ),
    "neutral": (
        "skills", "technical skills", "key skills", "core skills", "summary", "professional summary",
        "profile", "objective", "career objective", "languages", "hobbies", "interests", "declaration",
        "contact", "personal details",
    ),
}
_HEADING_KIND = {h: kind for kind, names in SECTION_HEADINGS.items() for h in names}
YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

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


def skills_in_order(text, dictionary=None):
    """Canonical skills found in a text (e.g. a job description), ordered by first mention."""
    dictionary = dictionary or load_skills()
    body = _normalise(text)
    first = {}
    for canonical, patterns in _search_terms(dictionary).items():
        hits = [m.start() for p in patterns for m in [p.search(body)] if m]
        if hits:
            first[canonical] = min(hits)
    return sorted(first, key=lambda s: (first[s], s))


def has_degree(text):
    return bool(DEGREE_RE.search(text or ""))


def _heading_of(line):
    cleaned = re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", line.lower().replace("&", " and "))).strip()
    if not cleaned or len(cleaned) > 50:
        return None
    return _HEADING_KIND.get(cleaned)


def section_spans(text):
    """[(start, end, kind)] covering the whole text; text before the first heading is 'neutral'."""
    spans, start, kind, pos = [], 0, "neutral", 0
    for line in (text or "").splitlines(keepends=True):
        heading = _heading_of(line)
        if heading:
            if pos > start:
                spans.append((start, pos, kind))
            start, kind = pos, heading
        pos += len(line)
    if pos > start:
        spans.append((start, pos, kind))
    return spans


def _kind_at(offset, spans):
    for a, b, kind in spans:
        if a <= offset < b:
            return kind
    return "neutral"


def education_spans(text):
    """Character spans of the EDUCATION section(s)."""
    return [(a, b) for a, b, kind in section_spans(text) if kind == "education"]


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

    years – the larger of (a) explicit "N years" / "N+ yrs" mentions and (b) date ranges
    ("2021 - 2023", "Jun 2022 - Present") from the text and from Comprehend DATE entities, merged so
    overlaps are not double-counted, capped at 15. Only work sections and unlabelled text count:
    education dates never do, and project / hackathon / club-role dates are not work years.

    has_dates – the resume shows dated work or activity outside education (a date range anywhere
    outside education, or a year in a projects / achievements style section). Used for the fresher
    credit when the job's minimum experience is 0.

    date_entities: dicts with "Text" and "BeginOffset" (offset into the full text).
    """
    now = now or datetime.now(timezone.utc)
    text = text or ""
    spans = section_spans(text)

    def counts(offset):
        return _kind_at(offset, spans) in ("work", "neutral")

    explicit = 0.0
    for m in EXPLICIT_YEARS_RE.finditer(text):
        if counts(m.start()):
            explicit = max(explicit, float(m.group(1)))

    work, activity = [], []
    for m in RANGE_RE.finditer(text):
        kind = _kind_at(m.start(), spans)
        if kind != "education":
            (work if kind in ("work", "neutral") else activity).extend(_ranges_in(m.group(0), now))

    outside = sorted(
        (e for e in date_entities if _kind_at(e.get("BeginOffset", -1), spans) in ("work", "neutral")),
        key=lambda e: e.get("BeginOffset", 0),
    )
    for i, ent in enumerate(outside):
        work.extend(_ranges_in(ent.get("Text", ""), now))
        # Comprehend often returns "Jun 2022" and "Present" as two entities joined by a dash
        if i + 1 < len(outside):
            nxt = outside[i + 1]
            a, b = ent.get("BeginOffset", 0), nxt.get("BeginOffset", 0) + len(nxt.get("Text", ""))
            if 0 <= a < b <= len(text) and b - a < 60:
                work.extend(_ranges_in(text[a:b], now))

    from_ranges = _merged_months(work) / 12.0
    years = min(max(explicit, from_ranges), MAX_YEARS)
    dated_activity = any(
        _kind_at(m.start(), spans) == "activity" and int(m.group(1)) <= now.year
        for m in YEAR_RE.finditer(text)
    )
    has_dates = bool(work) or bool(activity) or dated_activity
    return round(years, 1), has_dates


def _round_half_up(x):
    return int(math.floor(x + 0.5))


def normalise_weights(weights):
    """Integers 0-100 for skills / experience / education that sum to 100, else the defaults."""
    if not weights:
        return dict(DEFAULT_WEIGHTS)
    try:
        out = {k: int(weights[k]) for k in DEFAULT_WEIGHTS}
    except (KeyError, TypeError, ValueError):
        return dict(DEFAULT_WEIGHTS)
    if any(v < 0 or v > 100 for v in out.values()) or sum(out.values()) != 100:
        return dict(DEFAULT_WEIGHTS)
    return out


def score_candidate(text, required_skills, min_years=0, key_phrases=(), date_entities=(),
                    dictionary=None, now=None, preferred_skills=(), weights=None):
    dictionary = dictionary or load_skills()
    required = sorted({canonicalise(s, dictionary) for s in required_skills if s and s.strip()})
    if not required:
        raise ValueError("job has no required skills")
    preferred = sorted({canonicalise(s, dictionary) for s in preferred_skills or () if s and s.strip()} - set(required))
    w = normalise_weights(weights)

    found = find_skills(text, key_phrases, dictionary, extra=required + preferred)
    matched = [s for s in required if s in found]
    missing = [s for s in required if s not in found]
    skill_score = len(matched) / len(required) * w["skills"]

    years, has_dates = estimate_experience(text, date_entities, now)
    min_years = int(min_years or 0)
    if min_years == 0:
        exp_score = float(w["experience"]) if (has_dates or years > 0) else 0.0
    else:
        exp_score = min(years / max(min_years, 1), 1.0) * w["experience"]

    edu_score = float(w["education"]) if has_degree(text) else w["education"] / 2

    matched_preferred = [s for s in preferred if s in found]
    bonus = float(min(BONUS_PER_PREFERRED * len(matched_preferred), MAX_BONUS))

    return {
        "score": min(100, _round_half_up(skill_score + exp_score + edu_score + bonus)),
        "skillScore": round(skill_score, 2),
        "expScore": round(exp_score, 2),
        "eduScore": round(edu_score, 2),
        "bonusScore": bonus,
        "matchedSkills": matched,
        "missingSkills": missing,
        "matchedPreferred": matched_preferred,
        "yearsExperience": years,
        "weights": w,
    }
