import re

LANGUAGE_PATTERNS = {
    "python": [
        r"Traceback \(most recent call last\):",
        r"ZeroDivisionError",
        r"ModuleNotFoundError",
        r"ImportError",
        r"\.py\"",
    ],
    "nodejs": [
        r"TypeError:",
        r"ReferenceError:",
        r"SyntaxError:",
        r"at .*\.js",
        r"node_modules",
    ],
    "java": [
        r"Exception in thread",
        r"java\.lang\.",
        r"\.java:\d+",
        r"Caused by:",
    ],
    "dotnet": [
        r"System\.",
        r"Unhandled Exception",
        r"\.cs:\d+",
    ],
    "powershell": [
        r"At line:\d+ char:\d+",
        r"CategoryInfo",
        r"FullyQualifiedErrorId",
        r"PS>",
        r"System.Management.Automation",
    ],
}

def detect_language(log_text: str) -> str:
    scores = {lang: 0 for lang in LANGUAGE_PATTERNS}

    for lang, patterns in LANGUAGE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, log_text, re.IGNORECASE):
                scores[lang] += 1

    detected = max(scores, key=scores.get)

    if scores[detected] == 0:
        return "unknown"

    return detected
