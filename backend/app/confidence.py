import re

EXCEPTION_RE = re.compile(
    r"(exception|error|traceback|panic|segfault|fatal)",
    re.IGNORECASE,
)

LINE_QUOTE_RE = re.compile(
    r"`.+?`|\".+?\"",
)

def calculate_confidence(
    raw_log: str,
    llm_output: str,
) -> dict:
    """
    Returns a confidence score (0–100) and explanation.
    """

    score = 0
    reasons = []

    # ---- 1. Explicit failure signal in raw logs ----
    if EXCEPTION_RE.search(raw_log):
        score += 40
        reasons.append("Explicit error/exception detected in logs")

    # ---- 2. Stack trace present ----
    if "traceback" in raw_log.lower() or "at " in raw_log.lower():
        score += 20
        reasons.append("Stack trace or call chain detected")

    # ---- 3. LLM quoted exact lines ----
    if LINE_QUOTE_RE.search(llm_output):
        score += 20
        reasons.append("LLM referenced exact log lines")

    # ---- 4. LLM admitted uncertainty ----
    if "NO EXPLICIT ERROR FOUND" in llm_output:
        score = 0
        reasons = ["No explicit failure signal found in logs"]

    # ---- clamp ----
    score = min(score, 100)

    return {
        "score": score,
        "level": confidence_level(score),
        "reasons": reasons,
    }

def confidence_level(score: int) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "NONE"
