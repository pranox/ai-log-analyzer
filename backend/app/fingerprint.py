import re
import hashlib

def normalize_text(text: str) -> str:
    """
    Remove noise that changes per run:
    - file paths
    - line numbers
    - memory addresses
    - numbers
    """
    text = text.lower()

    # remove file paths
    text = re.sub(r"[a-zA-Z]:\\\\[^\\s]+", "<path>", text)
    text = re.sub(r"/[^\\s]+", "<path>", text)

    # remove line numbers
    text = re.sub(r"line \\d+", "line <n>", text)
    text = re.sub(r":\\d+", ":<n>", text)

    # remove numbers
    text = re.sub(r"\\d+", "<n>", text)

    return text.strip()
def extract_failure_signature(
    log_text: str,
    language: str,
) -> dict:
    """
    Extract minimal semantic signal for fingerprinting.
    Works across all languages.
    """

    exception = None
    failing_line = None

    lines = log_text.splitlines()

    for line in lines:
        if not exception and re.search(r"(exception|error|failed|fatal)", line, re.IGNORECASE):
            exception = line.strip()

        if exception and ("line" in line.lower() or "at " in line.lower()):
            failing_line = line.strip()
            break

    signature_text = f"""
language={language}
exception={exception or "none"}
line={failing_line or "none"}
"""

    normalized = normalize_text(signature_text)

    fingerprint = hashlib.sha256(normalized.encode()).hexdigest()

    return {
        "fingerprint": fingerprint,
        "exception": exception,
        "failing_line": failing_line,
    }
