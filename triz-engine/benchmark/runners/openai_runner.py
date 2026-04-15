"""OpenAI GPT-4o runner for TRIZBENCH.

Requires OPENAI_API_KEY environment variable. Skips gracefully if unavailable.
"""

from __future__ import annotations

import json
import os
import sys

_HAS_OPENAI = False
try:
    import openai
    _HAS_OPENAI = True
except ImportError:
    pass


def is_available() -> bool:
    return _HAS_OPENAI and bool(os.environ.get("OPENAI_API_KEY"))


def invoke(prompt: str, system_prompt: str | None = None) -> str:
    if not is_available():
        raise RuntimeError(
            "OpenAI runner unavailable: install openai package and set OPENAI_API_KEY"
        )

    client = openai.OpenAI()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=4096,
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    if not is_available():
        print("OpenAI runner not available (missing key or package)", file=sys.stderr)
        sys.exit(1)
    print("OpenAI runner ready")
