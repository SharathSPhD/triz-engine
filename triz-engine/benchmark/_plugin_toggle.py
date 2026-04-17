"""Shared helper for temporarily disabling the installed TRIZ plugin.

User-scoped Claude Code plugins stay enabled for every `claude -p` invocation,
even ones that are supposed to be a plain, un-augmented baseline. The plugin's
auto-activating skill then fires on the vanilla run and inflates (or distorts)
the output, which shows up as "Vanilla Claude" calling the
`triz-engine:analyze` skill in the live-demo traces.

This module exposes a context manager that disables the plugin via
`claude plugin disable <slug>` on entry and re-enables it on exit. It must wrap
every vanilla invocation — internal TRIZBENCH, external MacGyver, CresOWLve,
Applied, etc.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys

PLUGIN_SLUG = os.environ.get("TRIZ_PLUGIN_SLUG", "triz-engine@triz-arena")


def _cli(*args: str) -> None:
    try:
        subprocess.run(
            ["claude", *args],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


@contextlib.contextmanager
def plugin_disabled(slug: str = PLUGIN_SLUG, announce: bool = True):
    """Temporarily disable the TRIZ plugin so vanilla runs are plugin-free."""
    if announce:
        print(f"    (disabling {slug} for vanilla run)", file=sys.stderr, flush=True)
    _cli("plugin", "disable", slug)
    try:
        yield
    finally:
        if announce:
            print(f"    (re-enabling {slug})", file=sys.stderr, flush=True)
        _cli("plugin", "enable", slug)
