"""Google Gemini runner for TRIZBENCH.

Requires GOOGLE_API_KEY environment variable. Skips gracefully if unavailable.
"""

from __future__ import annotations

import json
import os
import sys

_HAS_GENAI = False
try:
    import google.generativeai as genai
    _HAS_GENAI = True
except ImportError:
    pass


def is_available() -> bool:
    return _HAS_GENAI and bool(os.environ.get("GOOGLE_API_KEY"))


def invoke(prompt: str, system_prompt: str | None = None) -> str:
    if not is_available():
        raise RuntimeError(
            "Gemini runner unavailable: install google-generativeai and set GOOGLE_API_KEY"
        )

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(
        "gemini-1.5-pro",
        system_instruction=system_prompt if system_prompt else None,
    )
    response = model.generate_content(prompt)
    return response.text or ""


if __name__ == "__main__":
    if not is_available():
        print("Gemini runner not available (missing key or package)", file=sys.stderr)
        sys.exit(1)
    print("Gemini runner ready")
