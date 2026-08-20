"""
fallback_classifier.py — Offline rule-based classifier.

Used when:
  1. LLM_API_KEY is not set, OR
  2. The LLM call fails / times out.

Design: keyword sets per category, scored by hit-count, winner takes all.
Adding a new category = add one entry to CATEGORY_RULES, done.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from schemas import (
    AnalyzeResponse,
    Category,
    Priority,
    RecommendedAction,
)


# ──────────────────────────────────────────────────────────────────────────────
# Keyword bank  (English + common Hinglish transliterations)
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_RULES: Dict[Category, List[str]] = {
    Category.LEAVE_REQUEST: [
        # English
        "leave", "absent", "absence", "not attend", "won't come", "will not come",
        "cannot come", "can't come", "miss class", "miss college", "skip",
        "medical leave", "sick leave", "emergency leave", "casual leave",
        "not be able to attend", "unable to attend",
        # Hinglish
        "nahi aana", "nahi aa", "nahi ayunga", "nahi ayungi", "nahi aaunga",
        "nahi aaungi", "nahi aaonga", "nahi aa sakta", "nahi aa sakti",
        "ghar rehna", "ghar pe rahna", "ghar pe hoon", "leave chahiye",
        "chutti", "chutti chahiye", "aanahi", "aa nahi sakta", "aa nahi sakti",
        "nahi aaunga", "nahi aaungi", "college nahi", "nahi aana",
    ],
    Category.ASSIGNMENT_EXTENSION: [
        # English
        "extension", "extend deadline", "extended deadline", "more time",
        "submit late", "late submission", "deadline", "postpone submission",
        "delay submission", "extra time", "grace period",
        # Hinglish
        "assignment submit", "submit kar sakta", "submit kar sakti",
        "submit krna", "kal submit", "aaj submit", "thoda time",
        "deadline badhao", "deadline badha", "extend karo", "late submit",
        "jama karna", "jama kar sakta",
        # Phonetic/typo variants
        "extnsion", "extensn", "extenion", "submision", "submittion",
        "wendsday", "wednsday", "assignmnt", "assgnmnt",
    ],
    Category.EVENT_BOOKING: [
        # English
        "book", "reserve", "hall", "auditorium", "seminar room", "classroom",
        "venue", "event", "fest", "festival", "organize", "booking",
        "conference room", "lab booking",
        # Hinglish
        "hall chahiye", "room chahiye", "book karna", "book kar do",
        "venue chahiye", "jagah chahiye", "function ke liye",
    ],
    Category.MAINTENANCE_REQUEST: [
        # English
        "repair", "fix", "broken", "not working", "leak", "leaking",
        "electricity", "light", "fan", "ac", "air conditioner", "projector",
        "wifi", "internet", "slow internet", "toilet", "washroom", "maintenance",
        "damaged", "replace", "malfunction", "not work",
        # Hinglish
        "kharab", "band hai", "nahi chal raha", "nahi chal rahi",
        "thik karo", "thik kar do", "repair karo", "light nahi",
        "fan nahi", "paani nahi", "wifi nahi", "wifi bahut slow",
        "slow hai", "nahi ho rahi", "nahi chal",
    ],
    Category.DOCUMENT_REQUEST: [
        # English
        "certificate", "transcript", "transcripts", "academic record",
        "bonafide", "character certificate",
        "id card", "marksheet", "migration certificate", "tc",
        "transfer certificate", "no objection", "noc", "fee receipt",
        "document", "letter", "attestation", "official record",
        # Hinglish
        "certificate chahiye", "bonafide chahiye", "marksheet chahiye",
        "tc chahiye", "document chahiye", "letter chahiye",
    ],
    Category.GENERAL_REQUEST: [
        # English
        "request", "help", "issue", "problem", "query", "question",
        "information", "suggest", "feedback",
        # Hinglish
        "madad chahiye", "help chahiye", "problem hai", "issue hai",
    ],
}

# Required fields per category (for missing-field detection)
REQUIRED_FIELDS: Dict[Category, List[str]] = {
    Category.LEAVE_REQUEST:        ["leave_date"],
    Category.ASSIGNMENT_EXTENSION: ["requested_extension_date"],
    Category.EVENT_BOOKING:        ["event_date", "venue"],
    Category.MAINTENANCE_REQUEST:  ["location"],
    Category.DOCUMENT_REQUEST:     ["document_type"],
    Category.GENERAL_REQUEST:      [],
    Category.UNKNOWN:              [],
}

# Recommended action mapping per category
ACTION_MAP: Dict[Category, RecommendedAction] = {
    Category.LEAVE_REQUEST:        RecommendedAction.REQUEST_TEACHER_APPROVAL,
    Category.ASSIGNMENT_EXTENSION: RecommendedAction.REQUEST_TEACHER_APPROVAL,
    Category.EVENT_BOOKING:        RecommendedAction.SCHEDULE_EVENT,
    Category.MAINTENANCE_REQUEST:  RecommendedAction.RAISE_MAINTENANCE_TICKET,
    Category.DOCUMENT_REQUEST:     RecommendedAction.GENERATE_DOCUMENT,
    Category.GENERAL_REQUEST:      RecommendedAction.HUMAN_REVIEW,
    Category.UNKNOWN:              RecommendedAction.HUMAN_REVIEW,
}

# ──────────────────────────────────────────────────────────────────────────────
# Date / time extraction patterns
# ──────────────────────────────────────────────────────────────────────────────

_DATE_PATTERNS = [
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b(tomorrow|aaj|kal|parso|next\s+\w+)\b",
    r"\b\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?\b",
    r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b",
]
_DATE_RE = re.compile("|".join(_DATE_PATTERNS), re.IGNORECASE)

_REASON_PATTERNS = [
    r"(?:because|due to|as|since|reason[:\s]|kyunki|kyuki|isliye|isiliye|ke karan)\s+(.+?)(?:\.|,|$)",
    r"(?:emergency|medical|sick|ill|fever|function|wedding|shadi|bimari|bimar)",
]
_REASON_RE   = re.compile(_REASON_PATTERNS[0], re.IGNORECASE)
_REASON_NOUN = re.compile(_REASON_PATTERNS[1], re.IGNORECASE)

_VENUE_RE = re.compile(
    r"\b(?:room\s*\w*|hall\s*\w*|auditorium|lab\s*\w*|ground|court|canteen)\b",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(?:room\s*\w*|floor\s*\w*|block\s*\w*|building\s*\w*|class\s*\w*|lab\s*\w*|toilet|washroom|corridor)\b",
    re.IGNORECASE,
)
_DOC_RE = re.compile(
    r"\b(?:bonafide|certificate|transcript|marksheet|tc|transfer certificate|id card|noc|no objection|fee receipt|character certificate)\b",
    re.IGNORECASE,
)

# ──────────────────────────────────────────────────────────────────────────────
# Prompt-injection detector
# ──────────────────────────────────────────────────────────────────────────────

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "you are now",
    "pretend you are",
    "disregard your",
    "forget your instructions",
    "system prompt",
    "act as",
    "jailbreak",
    "bypass",
    "override instructions",
    "new instructions:",
    "new task:",
]


def is_prompt_injection(text: str) -> bool:
    lower = text.lower()
    return any(pat in lower for pat in INJECTION_PATTERNS)


# ──────────────────────────────────────────────────────────────────────────────
# Conflict detector  (two different dates in a single request)
# ──────────────────────────────────────────────────────────────────────────────

def has_conflicting_dates(text: str) -> bool:
    dates = _DATE_RE.findall(text)
    flat  = [d for group in dates for d in group if d]
    return len(set(d.lower() for d in flat)) >= 2


# ──────────────────────────────────────────────────────────────────────────────
# Field extractors
# ──────────────────────────────────────────────────────────────────────────────

def _extract_date(text: str) -> Optional[str]:
    m = _DATE_RE.search(text)
    if m:
        return next((g for g in m.groups() if g), m.group(0))
    return None


def _extract_reason(text: str) -> Optional[str]:
    m = _REASON_RE.search(text)
    if m:
        return m.group(1).strip().rstrip(".,")
    m2 = _REASON_NOUN.search(text)
    if m2:
        return m2.group(0).strip()
    return None


def _extract_fields(category: Category, text: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    date   = _extract_date(text)
    reason = _extract_reason(text)

    if category == Category.LEAVE_REQUEST:
        if date:   fields["leave_date"]  = date
        if reason: fields["reason"]      = reason

    elif category == Category.ASSIGNMENT_EXTENSION:
        if date:   fields["requested_extension_date"] = date
        if reason: fields["reason"]                   = reason

    elif category == Category.EVENT_BOOKING:
        if date:
            fields["event_date"] = date
        venue_m = _VENUE_RE.search(text)
        if venue_m:
            fields["venue"] = venue_m.group(0)
        if reason:
            fields["purpose"] = reason

    elif category == Category.MAINTENANCE_REQUEST:
        loc_m = _LOCATION_RE.search(text)
        if loc_m:
            fields["location"] = loc_m.group(0)
        if reason:
            fields["issue"] = reason

    elif category == Category.DOCUMENT_REQUEST:
        doc_m = _DOC_RE.search(text)
        if doc_m:
            fields["document_type"] = doc_m.group(0)

    return fields


# ──────────────────────────────────────────────────────────────────────────────
# Priority estimator
# ──────────────────────────────────────────────────────────────────────────────

def _estimate_priority(text: str, category: Category) -> Priority:
    lower = text.lower()
    urgent_signals = ["urgent", "asap", "immediately", "emergency", "jaldi",
                      "abhi", "aaj", "today", "right now"]
    high_signals   = ["soon", "tomorrow", "kal", "important", "critical"]

    if any(s in lower for s in urgent_signals):
        return Priority.URGENT
    if any(s in lower for s in high_signals):
        return Priority.HIGH
    if category in (Category.MAINTENANCE_REQUEST, Category.LEAVE_REQUEST):
        return Priority.MEDIUM
    return Priority.LOW


# ──────────────────────────────────────────────────────────────────────────────
# Missing-required-fields check
# ──────────────────────────────────────────────────────────────────────────────

def _missing_required(category: Category, fields: Dict[str, Any]) -> bool:
    required = REQUIRED_FIELDS.get(category, [])
    return any(r not in fields for r in required)


# ──────────────────────────────────────────────────────────────────────────────
# Main classify function
# ──────────────────────────────────────────────────────────────────────────────

def rule_based_classify(
    text: str,
    requester_role: str = "student",
) -> AnalyzeResponse:
    """
    Pure keyword-based classifier.  Returns a validated AnalyzeResponse.
    Confidence is intentionally modest (~0.55–0.65) so the LLM layer
    takes precedence when available.
    """
    lower = text.lower()
    risk_reason: Optional[str] = None
    force_human  = False

    # ── Safety gate 1: prompt injection ────────────────────────────────────
    if is_prompt_injection(text):
        return AnalyzeResponse(
            category           = Category.UNKNOWN,
            priority           = Priority.HIGH,
            confidence         = 0.0,
            extracted_fields   = {},
            summary            = "Request flagged as possible prompt injection attempt.",
            recommended_action = RecommendedAction.HUMAN_REVIEW,
            requires_approval  = True,
            risk_reason        = "Possible prompt injection attempt detected; request quarantined.",
        )

    # ── Score each category ──────────────────────────────────────────────────
    scores: Dict[Category, int] = {}
    for cat, keywords in CATEGORY_RULES.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score:
            scores[cat] = score

    if not scores:
        category   = Category.UNKNOWN
        confidence = 0.30
    else:
        category   = max(scores, key=lambda c: scores[c])
        top_score  = scores[category]
        total      = sum(scores.values())
        # confidence = fraction of total hits that belong to the winner,
        # scaled to [0.50, 0.68] to stay below the LLM tier
        raw_conf   = top_score / total if total else 0.0
        confidence = round(0.50 + raw_conf * 0.18, 4)

    # ── Extract domain fields ────────────────────────────────────────────────
    extracted = _extract_fields(category, text)
    priority  = _estimate_priority(text, category)

    # ── Safety gate 2: conflicting dates ────────────────────────────────────
    if has_conflicting_dates(text):
        force_human = True
        risk_reason = "Conflicting dates detected in request text."

    # ── Safety gate 3: low confidence ───────────────────────────────────────
    if confidence < 0.70:
        force_human = True

    # ── Safety gate 4: unknown category ─────────────────────────────────────
    if category == Category.UNKNOWN:
        force_human = True

    # ── Safety gate 5: missing required fields ───────────────────────────────
    if _missing_required(category, extracted):
        force_human = True

    requires_approval = force_human or (category != Category.GENERAL_REQUEST)
    action = RecommendedAction.HUMAN_REVIEW if force_human else ACTION_MAP.get(
        category, RecommendedAction.HUMAN_REVIEW
    )

    # ── Build summary ────────────────────────────────────────────────────────
    role_label = requester_role.capitalize()
    cat_label  = category.value.replace("_", " ")
    summary    = f"{role_label} submitted a {cat_label}."
    if "reason" in extracted:
        summary += f" Reason: {extracted['reason']}."

    return AnalyzeResponse(
        category           = category,
        priority           = priority,
        confidence         = confidence,
        extracted_fields   = extracted,
        summary            = summary,
        recommended_action = action,
        requires_approval  = requires_approval,
        risk_reason        = risk_reason,
    )
