"""
llm.py

Handles communication with a remote Ollama LLM server
with retries and timeouts for network resilience.
"""

import os
import time
import requests

# Load from environment (DO NOT hardcode)
LLM_URL = os.getenv("LLM_URL")  # e.g. http://100.x.x.x:11434/api/generate
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")

if not LLM_URL:
    raise RuntimeError("LLM_URL is not set. Add it to your environment or .env file.")


def run_llm(
    prompt: str,
    retries: int = 2,
    timeout: int = 120,
    backoff_seconds: int = 2,
) -> str:
    """
    Send prompt to remote LLM with retry & timeout.

    retries: number of retry attempts (in addition to first try)
    timeout: seconds to wait for LLM response per attempt
    backoff_seconds: wait time between retries
    """
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    last_error = None

    for attempt in range(1, retries + 2):
        try:
            response = requests.post(
                LLM_URL,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()

            # Ollama returns {"response": "..."}
            return response.json().get("response", "").strip()

        except requests.exceptions.RequestException as e:
            last_error = e

            # If we still have retries left, wait and retry
            if attempt <= retries:
                time.sleep(backoff_seconds)
            else:
                break

    # Graceful failure (backend still returns JSON)
    return (
        "[LLM ERROR] Unable to get response from remote LLM "
        f"after {retries + 1} attempts. Last error: {last_error}"
    )
