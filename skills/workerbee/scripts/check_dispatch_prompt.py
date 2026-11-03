"""T003: check a dispatch prompt text file for the 14-element delegation contract and contract-reference compliance.

Usage: python3 check_dispatch_prompt.py <prompt_file> [--with-handoff-lint] [--tier grunt] [--transport file|bare]
       python3 check_dispatch_prompt.py <report_file> --profile report [--with-handoff-lint]
Exit 0 + prints "COMPLIANT" if all 14 elements present (and tier requirements met).
Exit 1 + prints missing element numbers if not, or NON-COMPLIANT for contract violations.

--with-handoff-lint also runs the optional third-party handoff-lint tool from
$HOME/.claude/skills/handoff-lint/scripts/handoff_lint.py when it exists. When
absent, one line `handoff-lint NOT installed -> H1-H6 checked by hand` goes to
STDERR (STDOUT stays the machine-parseable verdict) and the exit code is the
14-element verdict alone. With --profile report the file is a delegate report,
not a prompt: the 14-element check is replaced by a report-element check
(REPORT_KEYWORDS: caveman confirmation, grill, provenance tags, the
`OUT OF SCOPE / INCOMPLETE:` section, gate exit codes), then handoff-lint runs
when --with-handoff-lint is given.

CONTRACT lines: `CONTRACT: <path>` with optional trailing text, e.g.
`CONTRACT: <path> (sha256 <hex>)`. Only the first token after the colon is
the path. A `sha256 <hex>` in the suffix must match the file, else NON-COMPLIANT.

--tier grunt adds Grunt-tier requirements: "files in scope:" and "stop rule:" with digit.

--transport file|bare (default file): when bare, rejects CONTRACT: references (bare API cannot read files).
When file, tries to read contract file (expanded ~, relative to cwd then prompt file dir); unreadable = NON-COMPLIANT.
Contract text is appended to prompt for checking, but element 5 (training opt-out) must appear in prompt itself.

Element 1 (caveman) is conditional on the third-party skill: either the Skill-call
form (`caveman ultra`) or the emulation form
(`caveman NOT installed -> checked by hand`) satisfies it. Neither = missing.

Elements 2 and 3 (gate elements) require backtick in matching lines for real content.

Elements 10 and 11 are conditional: a line saying "not applicable" that names the
element satisfies them. All other elements (1-9, 12-14) are unconditional: a line
that mentions the keyword only to say "not applicable" does NOT satisfy them --
real content is required.
"""
from __future__ import annotations
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

CONDITIONAL = {10, 11}
GATE_ELEMENTS = {2, 3}

# Each element: list of keyword phrases (any match = "mentioned").
KEYWORDS: dict[int, list[str]] = {
    1: ["caveman ultra", "caveman not installed -> checked by hand",
        "caveman not installed → checked by hand"],
    2: ["success gate"],
    3: ["failure gate"],
    4: ["grill"],
    5: ["message to model provider: do not use this to train agentic models."],
    6: ["evidence"],
    7: ["no git commit", "repo-scoped", "commit/push authority"],
    8: ["classification", "confidential", "internal"],
    9: ["effort"],
    10: ["second-opinion", "second opinion"],
    11: ["plan contract"],
    12: ["out of scope", "out-of-scope"],
    13: ["edit hygiene", "surgical"],
    14: ["lesson-candidate", "lesson candidate"],
}


# Delegate report elements (--profile report). Any keyword on any line = present.
REPORT_KEYWORDS: dict[str, list[str]] = {
    "caveman": ["caveman ultra", "caveman not installed", "caveman: ultra",
                "caveman: not installed", "caveman: unreadable", "caveman unreadable"],
    "grill": ["grill"],
    "provenance-tags": ["[verified]", "[inferred]", "[assumed]"],
    "out-of-scope-incomplete": ["out of scope / incomplete:"],
    "gate-exit-codes": ["exit code", "exit=", "rc=", "exit 0", "exit 1"],
}

# D48: exactly one report line `WORKERS SPAWNED: <integer>`; a resume turn may add ` this turn (<n> total ...)`.
WORKERS_LINE_RE = re.compile(r"^\W*(?:\[(?:verified|inferred|assumed)\]\s*)?workers spawned:\s*\d+(?:\s+this turn\b.*)?\W*$", re.IGNORECASE)

# D48 ceilings per rung and model-to-rung table: dispatch_rungs.py.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from dispatch_rungs import FAN_OUT_BY_RUNG, MODEL_RUNG  # noqa: E402
RUNG_RE = re.compile(r"^rung:\s*(\w+)", re.MULTILINE)

# Reporting chain: role word to rank. Aliases rank through MODEL_RUNG (grunt 1 .. executive 4).
ROLE_RANK = {"operator": 5, "executive": 4, "supervisor": 3, "orchestrator": 3,
             "cos": 3, "workhorse": 2, "grunt": 1}
_RUNG_RANK = {"grunt": 1, "workhorse": 2, "orchestrator": 3, "executive": 4}
_REPORTS_TO_RE = re.compile(r"\breports? to\b")


def _seat_rank(name: str) -> int | None:
    word = name.strip().strip(".,;:()[]`'\"").lower()
    if word in ROLE_RANK:
        return ROLE_RANK[word]
    if word in MODEL_RUNG:
        return _RUNG_RANK[MODEL_RUNG[word]]
    return None


def _first_alias_rank(text: str) -> int | None:
    """Rank of the alias that appears earliest in text (same loop as render_dispatch._first_alias)."""
    best = None
    for alias in MODEL_RUNG:
        m = re.search(r"\b%s\b" % alias, text, re.IGNORECASE)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), alias)
    return _RUNG_RANK[MODEL_RUNG[best[1]]] if best else None


def _delegate_rank(text: str, model: str | None = None) -> int | None:
    """Rank of the delegate seat: --model, else line-start `model:`, else earliest alias on `role:`."""
    if model and model.strip().lower() in MODEL_RUNG:
        return _RUNG_RANK[MODEL_RUNG[model.strip().lower()]]
    for key in ("model:", "role:"):
        for ln in text.splitlines():
            ln = ln.strip()
            if ln.lower().startswith(key):
                rank = _first_alias_rank(ln[len(key):])
                if rank is not None:
                    return rank
    return None


def reporting_chain_inverted(lower: str, delegate_rank: int | None = None) -> bool:
    """True when a `reporting chain:` line has a seat reporting to a lower-ranked seat.

    `you` resolves to delegate_rank (unresolved: skip). `X reports to Y, who reports to Z`
    continues the chain from Y. A receiver ranks by its first known seat word.
    """
    for ln in lower.splitlines():
        ln = ln.strip()
        if not ln.startswith("reporting chain:"):
            continue
        for clause in ln[len("reporting chain:"):].split(";"):
            segs = _REPORTS_TO_RE.split(clause)
            if len(segs) < 2:
                continue
            words = re.findall(r"[\w-]+", segs[0])
            if not words:
                continue
            reporter = delegate_rank if words[-1] == "you" else _seat_rank(words[-1])
            for seg in segs[1:]:
                receiver = None
                for w in re.findall(r"[\w-]+", re.split(r"\bwho\b", seg)[0]):
                    receiver = _seat_rank(w)
                    if receiver is not None:
                        break
                if reporter is not None and receiver is not None and reporter > receiver:
                    return True
                reporter = receiver
    return False


def known_rung(text: str, model: str | None = None) -> str | None:
    """Rung from --model, else a `RUNG:` line; None when unknown."""
    if model and model.strip().lower() in MODEL_RUNG:
        return MODEL_RUNG[model.strip().lower()]
    m = RUNG_RE.search(text.lower())
    if m and m.group(1) in FAN_OUT_BY_RUNG:
        return m.group(1)
    return None

# D48 fan-out line: `FAN_OUT: width <n>, total <n>, depth <n>`.
FAN_OUT_RE = re.compile(r"^fan_out:\s*width\s+(\d+),\s*total\s+(\d+),\s*depth\s+(\d+)\s*$")


def _fan_out_line(ln: str) -> str:
    """Lowercased line without list bullets, backticks, bold marks or trailing punctuation (#66)."""
    ln = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", ln.lower())
    return ln.replace("`", "").replace("**", "").strip().rstrip(".;,").strip()


def parse_fan_out(text: str) -> tuple[int, int, int] | None:
    """Return (width, total, depth) from the first well-formed FAN_OUT line, else None."""
    for ln in text.splitlines():
        m = FAN_OUT_RE.match(_fan_out_line(ln))
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None

CONTRACT_RE = re.compile(r"^contract:\s*(\S+)(.*)$", re.IGNORECASE)
SHA_RE = re.compile(r"sha256\s*[:=]?\s*([0-9a-f]{64})(?![0-9a-z])", re.IGNORECASE)


def contract_sha_malformed(line: str) -> bool:
    """True when the CONTRACT suffix names sha256 but lacks exactly 64 hex chars."""
    m = CONTRACT_RE.match(line.strip())
    if not m or "sha256" not in m.group(2).lower():
        return False
    return SHA_RE.search(m.group(2)) is None


def parse_contract_line(line: str) -> tuple[str, str | None]:
    """Return (path, sha256 or None) from a `CONTRACT: <path> [suffix]` line."""
    m = CONTRACT_RE.match(line.strip())
    if not m:
        return "", None
    path = m.group(1).strip("`'\"")
    sha = SHA_RE.search(m.group(2))
    return path, (sha.group(1).lower() if sha else None)


# A `[verified]` claim about an exit or gate result must carry the exit code it saw.
# `exit code N/A` is the contract's no-gate form (#91).
_EXIT_RESULT = r"\b(?:exits?\s*[=:]?\s*-?\d+|exited\b|exit\s+code\b|rc\s*[=:])"
VERIFIED_EXIT_RE = re.compile(r"\[verified\].*" + _EXIT_RESULT + r"|" + _EXIT_RESULT + r".*\[verified\]", re.IGNORECASE)
EXIT_CODE_RE = re.compile(r"\b(?:exit(?:ed|s)?(?:\s+code)?|rc)\s*[=:]?\s*-?\d+|\bexit\s+code\s*[=:]?\s*N/A\b", re.IGNORECASE)


def check_report(text: str) -> list[str]:
    """Return missing report elements (names from REPORT_KEYWORDS)."""
    lower = text.lower()
    missing = [name for name, kws in REPORT_KEYWORDS.items() if not any(k in lower for k in kws)]
    if sum(1 for ln in text.splitlines() if WORKERS_LINE_RE.match(ln.strip())) != 1:
        missing.append("workers-spawned")
    if any(VERIFIED_EXIT_RE.search(ln) and not EXIT_CODE_RE.search(ln) for ln in text.splitlines()):
        missing.append("verified-exit-without-code")
    return missing


def _lines_with(text_lower: str, keyword: str) -> list[str]:
    return [ln for ln in text_lower.splitlines() if keyword in ln]


def check(text: str, tier: str | None = None, prompt_text: str | None = None,
          model: str | None = None) -> list[int | str]:
    """Return list of missing element numbers (1-14) and tier-specific requirements.

    For tier="grunt", also check for "files in scope:" and "stop rule:" with digit.
    Missing tier requirements added as strings: "files-in-scope", "stop-rule".

    When prompt_text is given (contract loaded from external file), element 5 is checked
    only against prompt_text, not against text (prompt + contract). Other elements check text.
    """
    lower = text.lower()
    missing: list[int | str] = []

    # Element 5 requires special handling when contract is external
    element_5_source = prompt_text.lower() if prompt_text else lower

    for num, keywords in KEYWORDS.items():
        # For element 5 with external contract, check only prompt_text
        if num == 5 and prompt_text:
            check_text = element_5_source
        else:
            check_text = lower

        matched_lines: list[str] = []
        for kw in keywords:
            matched_lines.extend(_lines_with(check_text, kw))

        if not matched_lines:
            missing.append(num)
            continue

        if num in CONDITIONAL:
            # any mention (real content or an explicit N/A line) satisfies it.
            continue

        # For gate elements (2, 3): filter to lines with backticks only.
        if num in GATE_ELEMENTS:
            matched_lines = [ln for ln in matched_lines if "`" in ln]
            if not matched_lines:
                missing.append(num)
                continue

        # unconditional: at least one matching line must NOT be an N/A-only line.
        has_real_content = any("not applicable" not in ln for ln in matched_lines)
        if not has_real_content:
            missing.append(num)

    # D48 fan-out: a prompt that carries a `FAN_OUT:` line must give three
    # integers. Prompts written before D48 carry no such line and pass.
    if any(_fan_out_line(ln).startswith("fan_out:") for ln in text.splitlines()):
        if parse_fan_out(text) is None:
            missing.append("fan-out")
        else:
            rung = known_rung(text, model)
            if rung and any(v > c for v, c in zip(parse_fan_out(text), FAN_OUT_BY_RUNG[rung])):
                missing.append("fan-out-over-ceiling")

    if reporting_chain_inverted(lower, _delegate_rank(lower, model)):
        missing.append("reporting-chain-inverted")

    # Check tier-specific requirements.
    if tier == "grunt":
        # "files in scope:" line must start with this label (stripped).
        files_in_scope_found = any(ln.strip().startswith("files in scope:") for ln in lower.splitlines())
        if not files_in_scope_found:
            missing.append("files-in-scope")

        # "stop rule:" line must start with this label (stripped) and contain digit.
        has_stop_rule_with_digit = any(
            any(c.isdigit() for c in ln)
            for ln in lower.splitlines()
            if ln.strip().startswith("stop rule:")
        )
        if not has_stop_rule_with_digit:
            missing.append("stop-rule")

    return missing


HANDOFF_WARNING = "handoff-lint NOT installed -> H1-H6 checked by hand"


def run_handoff_lint(path: str, profile: str | None) -> int:
    """Run handoff-lint if installed; else warn on stderr. Returns lint exit code (0 if absent)."""
    script = os.path.join(os.environ.get("HOME", ""), ".claude", "skills",
                          "handoff-lint", "scripts", "handoff_lint.py")
    if not os.path.isfile(script):
        print(HANDOFF_WARNING, file=sys.stderr)
        return 0
    cmd = [sys.executable, script, path]
    if profile:
        cmd += ["--profile", profile]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        print(f"handoff-lint failed to start ({exc}) -> H1-H6 checked by hand", file=sys.stderr)
        return 0
    # lint output to stderr: stdout stays the 14-element verdict.
    sys.stderr.write(res.stdout + res.stderr)
    return res.returncode


def main() -> int:
    args = sys.argv[1:]
    with_lint = "--with-handoff-lint" in args
    args = [a for a in args if a != "--with-handoff-lint"]
    profile = None
    tier = None
    transport = "file"
    model = None
    if "--model" in args:
        k = args.index("--model")
        if k + 1 >= len(args):
            print("--model needs a value", file=sys.stderr)
            return 2
        model = args[k + 1]
        del args[k:k + 2]
    if "--profile" in args:
        k = args.index("--profile")
        if k + 1 >= len(args):
            print("--profile needs a value", file=sys.stderr)
            return 2
        profile = args[k + 1]
        del args[k:k + 2]
    if "--tier" in args:
        k = args.index("--tier")
        if k + 1 >= len(args):
            print("--tier needs a value", file=sys.stderr)
            return 2
        tier = args[k + 1]
        del args[k:k + 2]
    if "--transport" in args:
        k = args.index("--transport")
        if k + 1 >= len(args):
            print("--transport needs a value", file=sys.stderr)
            return 2
        transport = args[k + 1]
        del args[k:k + 2]
    if profile not in (None, "report"):
        print(f"--profile must be report, got {profile!r}", file=sys.stderr)
        return 2
    if tier not in (None, "grunt"):
        print(f"--tier must be grunt, got {tier!r}", file=sys.stderr)
        return 2
    if len(args) != 1:
        print("usage: check_dispatch_prompt.py <prompt_file> [--with-handoff-lint] [--profile report] [--tier grunt] [--transport file|bare]",
              file=sys.stderr)
        return 2

    prompt_file = args[0]
    text = open(prompt_file, encoding="utf-8").read()
    if profile == "report":
        # delegate report, not a prompt: report elements replace the 14.
        missing_r = check_report(text)
        if missing_r:
            print(f"NON-COMPLIANT missing report elements: {missing_r}")
        else:
            print("COMPLIANT")
        lint_rc = run_handoff_lint(prompt_file, profile) if with_lint else 0
        return 1 if (missing_r or lint_rc) else 0

    # Check for CONTRACT: lines
    contract_lines = [ln.strip() for ln in text.splitlines() if ln.strip().lower().startswith("contract:")]
    contract_text = ""

    if contract_lines:
        if transport == "bare":
            print("NON-COMPLIANT contract-reference-on-bare-transport: bare-API delegates cannot read files; paste the header")
            return 1

        # transport is "file": try to read contract files
        for contract_line in contract_lines:
            # Path = first token after "contract:"; suffix such as "(sha256 <hex>)" ignored.
            path_str, want_sha = parse_contract_line(contract_line)
            if not path_str:
                print(f"NON-COMPLIANT contract-unparsable: {contract_line}")
                return 1

            if contract_sha_malformed(contract_line):
                print(f"NON-COMPLIANT contract-sha256-malformed: sha256 must be exactly 64 hex characters: {path_str}")
                return 1

            # Expand ~ and try to read
            expanded_path = os.path.expanduser(path_str)
            contract_path = None
            if Path(expanded_path).exists() and not Path(expanded_path).is_file():
                print(f"NON-COMPLIANT contract-not-regular-file: {path_str}")
                return 1

            # Try as given (relative to cwd)
            try:
                contract_path = Path(expanded_path)
                contract_text += contract_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                # Try relative to prompt file's directory
                prompt_dir = Path(prompt_file).resolve().parent
                contract_path = prompt_dir / expanded_path
                if contract_path.exists() and not contract_path.is_file():
                    print(f"NON-COMPLIANT contract-not-regular-file: {path_str}")
                    return 1
                try:
                    contract_text += contract_path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    print(f"NON-COMPLIANT contract-unreadable: {path_str}")
                    return 1
            if want_sha and hashlib.sha256(contract_path.read_bytes()).hexdigest() != want_sha:
                print(f"NON-COMPLIANT contract-sha256-mismatch: {path_str}")
                return 1

    # If contract text was loaded, append it to prompt for checking (except element 5)
    if contract_text:
        full_text = text + "\n" + contract_text
        missing = check(full_text, tier=tier, prompt_text=text, model=model)
    else:
        missing = check(text, tier=tier, model=model)

    if not missing:
        print("COMPLIANT")
    else:
        print(f"NON-COMPLIANT missing elements: {missing}")
    lint_rc = run_handoff_lint(prompt_file, profile) if with_lint else 0
    return 1 if (missing or lint_rc) else 0


if __name__ == "__main__":
    raise SystemExit(main())
