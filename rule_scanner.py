"""
rule_scanner.py
Deterministic rule-based keyword, HTTP status, and requested-phrase scanner
for strict regression checks alongside LLM verification.
"""

import re
from typing import Any, Dict, List, Optional

DEFAULT_ERROR_PATTERNS: List[str] = [
    "out of memory",
    "oom",
    "internal server error",
    "unhandled exception",
    "runtimeerror",
    "traceback",
    "connection refused",
    "validation error",
    "invalid number",
    "out of range",
    "404",
    "500",
    "502",
    "503",
    "fatal error",
    "critical error",
]

NEGATED_ERROR_PHRASES: List[str] = [
    "zero errors detected",
    "zero error detected",
    "no error detected",
    "no errors detected",
    "no error found",
    "no errors found",
    "no error",
    "no errors",
    "0 errors",
    "0 error",
]


def extract_requested_phrases(user_query: str) -> List[str]:
    """Pull quoted phrases or common error terms mentioned in the user prompt."""
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', user_query)
    phrases: List[str] = []
    for q1, q2 in quoted:
        val = (q1 or q2).strip()
        if val and val.lower() not in {p.lower() for p in phrases}:
            phrases.append(val)

    if "out of memory" in user_query.lower() and not any(
        p.lower() == "out of memory" for p in phrases
    ):
        phrases.append("Out of memory")

    return phrases


def _strip_negated_phrases(text: str) -> str:
    """Remove negated error statements (like 'Zero errors detected') before generic checks."""
    cleaned = text
    for neg in NEGATED_ERROR_PHRASES:
        cleaned = re.sub(rf"\b{re.escape(neg)}\b", " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def scan_page_rules(
    extracted_text: str,
    http_status: Optional[int],
    user_query: str,
    custom_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run deterministic substring and status rules against rendered page text."""
    text = extracted_text or ""
    lower_text = text.lower()
    non_negated_text = _strip_negated_phrases(text)
    lower_non_negated = non_negated_text.lower()

    patterns = custom_patterns if custom_patterns is not None else DEFAULT_ERROR_PATTERNS
    has_negated_phrase = any(neg in lower_text for neg in NEGATED_ERROR_PHRASES)

    matched_rules: List[str] = []
    for pat in patterns:
        p_clean = pat.strip()
        if not p_clean:
            continue
        if p_clean.isdigit():
            if re.search(rf"\b{re.escape(p_clean)}\b", non_negated_text):
                matched_rules.append(p_clean)
        else:
            if p_clean.lower() in lower_non_negated:
                matched_rules.append(p_clean)

    requested_phrases = extract_requested_phrases(user_query)
    phrase_matches: Dict[str, bool] = {
        phrase: (phrase.lower() in lower_text) for phrase in requested_phrases
    }

    http_error = http_status is not None and http_status >= 400
    has_error = bool(matched_rules) or http_error

    if requested_phrases:
        regression_passed = all(phrase_matches.values())
    else:
        regression_passed = not has_error

    return {
        "has_error": has_error,
        "http_error": http_error,
        "http_status": http_status,
        "matched_rules": matched_rules,
        "requested_phrases": phrase_matches,
        "has_negated_phrase": has_negated_phrase,
        "regression_passed": regression_passed,
    }


def format_rule_scan_summary(scan: Dict[str, Any]) -> str:
    """Format scan results into a concise string for prompts and logs."""
    rules = ", ".join(scan.get("matched_rules") or []) or "None"
    phrases = scan.get("requested_phrases") or {}
    phrase_str = (
        ", ".join(f'"{k}" -> {"FOUND" if v else "NOT FOUND"}' for k, v in phrases.items())
        if phrases
        else "None specified"
    )
    negated = "Yes" if scan.get("has_negated_phrase") else "No"
    return (
        f"HTTP Status: {scan.get('http_status') if scan.get('http_status') is not None else 'N/A'} | "
        f"Any Error Detected: {scan.get('has_error')} | "
        f"Matched Error Rules: {rules} | "
        f"Negated Error Phrase Present: {negated} | "
        f"Requested Phrases: {phrase_str} | "
        f"Rule Check Passed: {scan.get('regression_passed')}"
    )
