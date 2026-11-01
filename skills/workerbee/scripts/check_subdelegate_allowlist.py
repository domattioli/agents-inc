"""Mechanical check (upstream-tracked issue, tag dropped): did a delegate's nested sub-delegation actually
land on an allowlisted free/cheap model, and did it echo the required
confirm-and-echo line?

Root cause this closes (upstream issue): "use a free/cheap model" as bare prose is
unenforceable -- observed a nested `Agent` call run on `claude-opus-5` despite
that exact instruction. Prose alone can't catch a repeat; this script can,
cheaply, by grepping the dispatch transcript after the fact.

Usage: python3 check_subdelegate_allowlist.py <transcript_file>
Exit 0 + "COMPLIANT" if every nested-call model line found is allowlisted AND
carries a matching confirm-echo line. Exit 1 + violation detail otherwise.
Exit 0 + "NO NESTED CALLS FOUND" if the transcript has no nested dispatch at
all -- nothing to check, not a violation.

This is a transcript-side lint, not a live hook -- this repo has no
PreToolUse/hook mechanism (`scripts/hooks/` does not exist here, `.claude/
settings.json` is absent; confirmed 2026-09-12). It cannot block a nested
call before it fires. It CAN be run on a saved transcript/output file after a
dispatch to catch the violation instead of trusting the prose alone.
"""
from __future__ import annotations
import re
import sys

# Substrings that mark an allowlisted (free/cheap) sub-delegate model slug.
ALLOWLIST = [
    "gpt-5.4-mini",
    "openrouter",
    "gemini",
    "mistral",
    "ministral",
    "codestral",
]

# Substrings that mark a forbidden (paid/full-tier) model slug.
FORBIDDEN = [
    "opus", "sonnet", "haiku", "fable",
    "gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-6.1-terra", "gpt-5.6-luna",
    "astra", "sol", "terra", "luna",
]

MODEL_FIELD_RE = re.compile(r'"model"\s*:\s*"([a-z0-9.\-]+)"', re.IGNORECASE)
CONFIRM_RE = re.compile(
    r"sub-delegate model:\s*([a-z0-9.\-]+)\s*[—-]\s*allowlist match:\s*yes",
    re.IGNORECASE,
)


def check(text: str) -> list[str]:
    """Return list of violation strings. Empty list == compliant."""
    lower = text.lower()
    violations: list[str] = []

    nested_models = sorted(set(MODEL_FIELD_RE.findall(lower)))
    confirmed_models = sorted(set(CONFIRM_RE.findall(lower)))

    if not nested_models:
        return []  # nothing to check -- caller reports NO NESTED CALLS FOUND

    for model in nested_models:
        is_allowed = any(a in model for a in ALLOWLIST)
        is_forbidden = any(f in model for f in FORBIDDEN)
        if is_forbidden and not is_allowed:
            violations.append(
                f"forbidden model dispatched as nested sub-delegate: {model!r}"
            )
        if model not in confirmed_models:
            violations.append(
                f"no 'SUB-DELEGATE MODEL: {model} — allowlist match: yes' "
                f"confirm-echo line found for nested call to {model!r}"
            )

    return violations


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_subdelegate_allowlist.py <transcript_file>", file=sys.stderr)
        return 2
    text = open(sys.argv[1], encoding="utf-8").read()
    lower = text.lower()
    if not MODEL_FIELD_RE.search(lower):
        print("NO NESTED CALLS FOUND")
        return 0
    violations = check(text)
    if not violations:
        print("COMPLIANT")
        return 0
    print("NON-COMPLIANT:")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
