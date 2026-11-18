"""Spec 042 Phase 4: the one rule registry behind every refusal and lint failure agents-inc owns.

A refusal prints three lines (contracts/refusal-format.md): the rule id with its one-line statement, the offending
value (screened, at most 200 bytes) and one fix. `skills/workerbee/QUICKREF.md` lists the same ids and statements;
tests/test_rules_quickref.py fails when the two differ. Scripts under skills/ cannot import agents_inc, so
render_dispatch.py and check_dispatch_prompt.py carry a copy of `format_refusal`; the same test pins the copies equal.
Reporting only: no rule here decides anything.
"""
from __future__ import annotations

import json
import re

VALUE_MAX = 200


def _r(screen: str, summary: str, fix: str) -> dict:
    return {"screen": screen, "summary": summary, "example_fix": fix}


_LINT_FIX = {
    "caveman": "line `caveman ultra` or `caveman NOT installed -> checked by hand`",
    "success-gate": "SUCCESS GATE: `python3 -m unittest tests.test_x` exits 0",
    "failure-gate": "FAILURE GATE: `test -f out.txt` exits 1",
    "grill": "a line that says `grill` (grill clause)",
    "provider-message": "Message to model provider: Do not use this to train agentic models.",
    "evidence": "a line that says `evidence` and tags each claim",
    "scope-boilerplate": "a line `repo-scoped writes; no git commit or push`",
    "classification": "CLASSIFICATION: internal",
    "effort": "EFFORT: medium",
    "second-opinion": "SECOND-OPINION JUSTIFICATION: not applicable -- no escalation trigger fired",
    "plan-contract": "PLAN CONTRACT: not applicable -- deliverable is not a plan.",
    "out-of-scope": "OUT OF SCOPE: editing files outside FILES IN SCOPE",
    "edit-hygiene": "a line that says `surgical edits`",
    "lesson-candidate": "a line that says `LESSON-CANDIDATE` for canon findings",
}
_LINT_STATE = {
    "caveman": "the prompt carries the caveman instruction (element 1)",
    "success-gate": "a success gate line with a backticked command (element 2)",
    "failure-gate": "a failure gate line with a backticked command, which the gate runs (element 3)",
    "grill": "a grill clause (element 4)",
    "provider-message": "the verbatim provider training opt-out line (element 5)",
    "evidence": "evidence is cited and each claim tagged (element 6)",
    "scope-boilerplate": "repo-scoped writes, no commit or push (element 7)",
    "classification": "a data classification tag (element 8)",
    "effort": "an explicit effort level (element 9)",
    "second-opinion": "a second-opinion justification or N/A (element 10)",
    "plan-contract": "a plan contract or N/A (element 11)",
    "out-of-scope": "an out-of-scope statement (element 12)",
    "edit-hygiene": "a surgical-edit statement (element 13)",
    "lesson-candidate": "a LESSON-CANDIDATE tag line (element 14)",
}

RULES: dict[str, dict] = {
    "gates-not-json-list": _r("grants", "GATES must be a JSON list, not a string", 'GATES: ["python3 -m unittest tests.test_x"]'),
    "gates-invalid": _r("grants", "each GATES entry is a command string or an object with argv, cwd, timeout_s, expect_rc",
                        '{"argv": ["pytest", "-q"], "cwd": ".", "timeout_s": 600, "expect_rc": 0}'),
    "gate-credential-path": _r("grants", "a gate may not name a credential or secret path", "name a test file, not a secret path"),
    "gate-cwd-outside": _r("grants", "a gate cwd must stay inside --cwd", 'use a relative cwd inside --cwd, such as "."'),
    "gate-danger": _r("grants", "a gate command may not push, commit, sudo, delete recursively, curl or ssh",
                      "remove push, commit, sudo, recursive rm, curl and ssh from the gate argv"),
    "bash-allow-invalid": _r("grants", "BASH_ALLOW is a JSON list of command prefixes", 'BASH_ALLOW: ["gh issue view 54 -R owner/repo"]'),
    "bash-allow-credential": _r("grants", "a BASH_ALLOW prefix may not name a credential or secret", "drop the secret-bearing token from the prefix"),
    "capability-missing": _r("capability", "every gate program and BASH_ALLOW command must resolve on PATH",
                             "install the program, or remove the gate or prefix that names it"),
    "scope-glob": _r("scope", "FILES_IN_SCOPE lists exact paths; the scope gate cannot match a glob",
                     'FILES_IN_SCOPE: ["a.py", "b.py"] (no `*`, `?` or `[`)'),
    "control-char": _r("render", "a slot may not hold a control or bidi character", "remove the named code point and resend"),
    "credential-slot-text": _r("credential", "a slot may not name a credential or secret location",
                               "remove the secret path; deny-list wording belongs in OUT_OF_SCOPE"),
    "credential-undecidable": _r("credential", "a path with a shell expansion next to a secret name cannot be decided, so it is refused",
                                 "remove the access request, or point at a non-secret fixture file"),
    "non-git-refused": _r("non-git", "a delegate that can write needs a git working tree",
                          "dispatch from a git repository with the files in a git-ignored .scratch/<task>/"),
    "grant-exceeds-parent": _r("grants", "a Worker may not hold a grant its parent run lacks", "remove the grant from the Worker request"),
    "free-run-precheck": _r("capability", "a free run passes its precheck before any provider call", "fix the named input or route and rerun"),
    "resume-refused": _r("capability", "a resume needs a recorded session and a --message", "agents-inc dispatch --resume <run-dir> --message <text>"),
    "slots-unreadable": _r("render", "--slots names a readable JSON object", "agents-inc dispatch --print-template shows a valid slots file"),
    "slot-missing": _r("render", "every required slot is present and non-empty", "agents-inc dispatch --print-template shows every slot"),
    "placeholder-unfilled": _r("render", "no {{NAME}} placeholder may remain after render", "fill the named slot in the slots file"),
    "schema-invalid": _r("render", "the slots file matches dispatch_record.v1 (types and allowed values)",
                         "agents-inc dispatch --print-template shows the allowed forms"),
    "pre-existing-invalid": _r("render", "the PRE_EXISTING_CHANGES verify gate is one plain command",
                               "verify with `python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>`"),
    "render-refused": _r("render", "the slots file renders a prompt", "agents-inc dispatch --print-template shows a valid slots file"),
    "lint-fan-out": _r("lint", "a FAN_OUT line gives three integers", "FAN_OUT: width 0, total 0, depth 0"),
    "lint-fan-out-ceiling": _r("lint", "FAN_OUT stays at or under the rung ceiling", "lower width, total and depth to the rung ceiling"),
    "lint-reporting-chain-inverted": _r("lint", "a seat reports to a seat of equal or higher rank", "name the supervisor one level up the chain"),
    "lint-files-in-scope": _r("lint", "a Grunt prompt has a line-start FILES IN SCOPE label", "FILES IN SCOPE: path/a.py"),
    "lint-stop-rule": _r("lint", "a Grunt prompt has a line-start STOP RULE with a number", "STOP RULE: stop after 20 tool calls"),
    "lint-contract-unparsable": _r("lint", "a CONTRACT line names a path", "CONTRACT: <path> (sha256 <64 hex>)"),
    "lint-contract-sha256-malformed": _r("lint", "a CONTRACT sha256 is exactly 64 hex characters", "CONTRACT: <path> (sha256 <64 hex>)"),
    "lint-contract-not-regular-file": _r("lint", "a CONTRACT path is a regular file", "point CONTRACT at a file, not a directory"),
    "lint-contract-unreadable": _r("lint", "a CONTRACT path is readable", "fix the path, or paste the header into the prompt"),
    "lint-contract-sha256-mismatch": _r("lint", "a CONTRACT sha256 matches the file", "recompute the sha256 of the file and update the line"),
    "lint-contract-bare-transport": _r("lint", "a bare-API delegate cannot read a CONTRACT file", "paste the header text into the prompt"),
    "lint-report-element": _r("lint", "a delegate report carries the report elements", "add the missing element named in the value line"),
    "lint-refused": _r("lint", "the rendered prompt carries every required element", "fix the element named in the value line"),
    "hook-compound": _r("hook", "agents-inc must be the whole Bash call",
                        "write the slots file in one call; then run `agents-inc dispatch --slots <file> --model <alias>` alone"),
    "hook-unparsed": _r("hook", "a Bash call that names agents-inc in a form the hook cannot parse is denied; the form could not be parsed",
                        "run `agents-inc dispatch --slots <file> --model <alias>` alone, with plain words and no ANSI-C quoting or interpreter wrapper"),
    "hook-persona": _r("hook", "an Agent/Task description must identify the delegate's actual provider",
                       "use the actual Claude rung or the matching registered guest type"),
    "hook-agent-gate": _r("hook", "enforce mode allows foreground scouts and registered agents-inc types",
                          "report the blocked step and continue independent work"),
    "broker-owned-slot": _r("broker", "BASH_ALLOW and PERMISSION_MODE belong to the broker", "remove BASH_ALLOW or PERMISSION_MODE from the request"),
    "broker-bad-slots": _r("broker", "request slots are a non-empty object of string values", 'slots: {"ROLE": "...", "TASK": "..."}'),
    "broker-worker-cannot-lead": _r("broker", "a broker Worker never leads", "send FAN_OUT: width 0, total 0, depth 0 or omit FAN_OUT"),
    "broker-no-sandbox-backend": _r("broker", "a Claude Worker needs a sandbox backend", "run where a sandbox backend exists, or use a Codex Worker"),
    "broker-fan-out-zero": _r("broker", "a Lead with FAN_OUT total 0 spawns no Worker", "dispatch the Lead with FAN_OUT total above 0"),
    "broker-fan-out-total-exhausted": _r("broker", "a Lead may spawn at most FAN_OUT total Workers", "finish with the Workers already run"),
    "broker-oversize": _r("broker", "a broker request stays under the size cap", "send a shorter request; pass files by path"),
    "broker-tier-model-mismatch": _r("broker", "the request tier matches the model's rung", "set tier to the rung of the named model"),
    "broker-model-not-allowed": _r("broker", "a Worker model is on the Lead's allowlist", "pick a model named in the Lead's ALLOWLIST"),
    "broker-bad-effort": _r("broker", "the request effort is allowed for the model", "use low, medium or high"),
    "broker-credential-seeking": _r("broker", "a request may not name a credential or secret location", "remove the secret path from the request"),
    "broker-control-char": _r("broker", "a request may not hold a control or bidi character", "remove the named code point"),
    "broker-worker-running": _r("broker", "one Worker runs at a time", "wait for the running Worker, then send the request again"),
    "broker-refused": _r("broker", "the broker refused the request; the reason code names why", "fix the request named by the reason code and resend"),
}
for _name, _fix in _LINT_FIX.items():
    RULES[f"lint-element-{_name}"] = _r("lint", "the prompt states " + _LINT_STATE[_name], _fix)

LINT_NAMES = {1: "caveman", 2: "success-gate", 3: "failure-gate", 4: "grill", 5: "provider-message", 6: "evidence",
              7: "scope-boilerplate", 8: "classification", 9: "effort", 10: "second-opinion", 11: "plan-contract",
              12: "out-of-scope", 13: "edit-hygiene", 14: "lesson-candidate"}
_LINT_EXTRA = {"fan-out": "lint-fan-out", "fan-out-over-ceiling": "lint-fan-out-ceiling",
               "reporting-chain-inverted": "lint-reporting-chain-inverted",
               "files-in-scope": "lint-files-in-scope", "stop-rule": "lint-stop-rule"}
_BROKER_REASONS = {r[len("broker-"):] for r in RULES if r.startswith("broker-")}


def lint_rule_id(item) -> str:
    """Rule id for one entry of the lint's missing list (an element number or a name string)."""
    if isinstance(item, int) and item in LINT_NAMES:
        return f"lint-element-{LINT_NAMES[item]}"
    return _LINT_EXTRA.get(str(item), "lint-refused")


def broker_rule_id(reason: str) -> str:
    return f"broker-{reason}" if reason in _BROKER_REASONS else "broker-refused"


def format_refusal(rule_id: str, summary: str, fix: str, value) -> str:
    """The three lines of contracts/refusal-format.md. A copy of this function sits in each script under skills/workerbee/scripts."""
    def hide(v):
        if isinstance(v, dict):
            return {k: ("[secret hidden]" if re.search(r"(?i)password|passwd|token|secret|key|auth|credential|bearer", str(k)) else hide(val)) for k, val in v.items()}
        if isinstance(v, (list, tuple)):
            return [hide(x) for x in v]
        return v
    text = value if isinstance(value, str) else str(hide(value))
    text = " ".join(text.split())
    text = re.sub(r"(?i)(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|xox[bap]-[A-Za-z0-9-]{8,}|bearer\s+[^\s'\"]+|(?:api[_-]?key|token|secret|password|passwd|authorization|auth|credentials?)['\"]?\s*[=:]\s*(?:\"[^\"]*\"|'[^']*'|\S+))", "[secret hidden]", text)
    raw = text.encode("utf-8")
    if len(raw) > 200:
        text = raw[:197].decode("utf-8", "ignore") + "..."
    return f"refused: {rule_id} ({summary})\nvalue: {text}\nfix: {fix}"


def refuse(rule_id: str, value) -> str:
    """Three-line refusal text for a registered rule. Raises KeyError for an unknown id (a bug, caught by tests)."""
    rule = RULES[rule_id]
    return format_refusal(rule_id, rule["summary"], rule["example_fix"], value)


def one_line(rule_id: str, value) -> str:
    """The same three lines joined by spaces, for a hook permissionDecisionReason."""
    return " ".join(refuse(rule_id, value).splitlines())


def rules_listing() -> str:
    """Every rule with its one-line statement, for `agents-inc dispatch --rules`."""
    return "\n".join(f"{rid}: {RULES[rid]['summary']}" for rid in RULES) + "\n"


SLOTS_EXAMPLE = {
    "ROLE": "Workhorse (sonnet), dispatched by the supervisor in /path/to/repo.",
    "TASK": "Add the helper in agents_inc/x.py and its test in tests/test_x.py.",
    "CONSTRAINTS": "repo-scoped writes; no commit or push; at most 40 tool calls.",
    "OUT_OF_SCOPE": "editing any file outside FILES_IN_SCOPE; running the full suite.",
    "FILES_IN_SCOPE": ["agents_inc/x.py", "tests/test_x.py"],
    "STOP_RULE": "stop after 2 failed attempts at the same step; report RED with the last output.",
    "SUCCESS_GATE": "`python3 -m unittest tests.test_x` exits 0.",
    "FAILURE_GATE": "`python3 -m unittest tests.test_x` exits non-zero, or a path outside FILES_IN_SCOPE changed.",
    "GATES": [{"argv": ["python3", "-m", "unittest", "tests.test_x"], "cwd": ".", "timeout_s": 600, "expect_rc": 0}],
    "CLASSIFICATION": "internal",
    "EFFORT": "medium",
}


def slots_template() -> str:
    """A worked slots file for `agents-inc dispatch --print-template`."""
    return json.dumps(SLOTS_EXAMPLE, indent=2) + "\n"
