import re
from typing import Optional

# High-signal error patterns across languages & CI tools
ERROR_PATTERNS = [
    # Python
    r"Traceback \(most recent call last\):",
    r"\b[A-Za-z]+Error:",
    r"\bException\b",

    # Java / JVM
    r"Exception in thread",
    r"Caused by:",

    # Node.js
    r"UnhandledPromiseRejection",
    r"Error:.*",

    # C / C++
    r"Segmentation fault",
    r"core dumped",

    # CI / Shell
    r"exit code \d+",
    r"returned non-zero",
    r"command failed",
    r"FAILED",
    r"ERROR",
]

MAX_CONTEXT_BEFORE = 5
MAX_CONTEXT_AFTER = 20


def extract_failure_block(log_text: str) -> Optional[str]:
    """
    Extracts high-signal failure blocks from noisy CI logs.
    Returns None if no failure signal is found.
    """

    if not log_text or not isinstance(log_text, str):
        return None

    lines = log_text.splitlines()
    matches = []

    for idx, line in enumerate(lines):
        for pattern in ERROR_PATTERNS:
            if re.search(pattern, line):
                start = max(idx - MAX_CONTEXT_BEFORE, 0)
                end = min(idx + MAX_CONTEXT_AFTER, len(lines))

                block = "\n".join(lines[start:end])
                matches.append(block)
                break

    if not matches:
        return None

    # Deduplicate overlapping blocks
    unique_blocks = list(dict.fromkeys(matches))

    return "\n\n---\n\n".join(unique_blocks)
def extract_failure_signature(raw_text: str, language: str) -> dict:
    """
    Minimal, safe failure signature extractor.
    No guessing. No language assumptions.
    """

    exception = None
    failing_line = None

    for line in raw_text.splitlines():
        if "Error" in line or "Exception" in line:
            exception = line.strip()
            failing_line = line.strip()
            break

    fingerprint = f"{language}:{exception}" if exception else f"{language}:NO_EXCEPTION"

    return {
        "fingerprint": fingerprint,
        "exception": exception or "UNKNOWN",
        "failing_line": failing_line or "UNKNOWN",
    }
