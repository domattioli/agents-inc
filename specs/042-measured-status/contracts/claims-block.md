<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Contract: the delegate claims block (machine-readable end of the delegate's hand-back)

The delegate ends its hand-back with one fenced block. The prompt header (`skills/workerbee/header.md`) and `skills/workerbee/slots.md` tell it how. `skills/workerbee/scripts/check_claims.py` parses it. This is #131 step C.

## Form

````text
```claims
files_changed: path/one.py, path/two.md
gates: g1=0; g2=0
tests: g1=42
stopped: none
```
````

| Key | Required | Value |
|---|---|---|
| `files_changed` | yes | Comma-separated repo-relative paths, or `none`. |
| `gates` | yes | `;`-separated `<gate id>=<exit code>` pairs, one for every gate id of the run (FR-012c, FR-012d), or `none` when the run has no gates. Gate ids `g1`, `g2`, ... come from the dispatcher (order of the gates in the slots file) and are printed in the prompt beside each gate. |
| `tests` | no | `;`-separated `<gate id>=<count>` pairs: the test count the delegate claims for that gate (FR-012b). Omitted when no count is claimed. |
| `stopped` | yes | `none`, or the id `s1` or the full declared STOP RULE text the delegate stopped at; a partial or substring match is unsupported (FR-012e). The STOP RULE slot is one rule with the single id `s1`; several sentences in the slot are still one rule, and there are no per-clause ids. |

Rules: exactly one block fenced with `claims` is allowed. Two or more blocks give claim check result `unsupported`, reason `multiple-claims-blocks`, and nothing in either block is compared (FR-012a); there is no "last block wins". Unknown keys are ignored (a claims fence is never control text: the report-control parsers for WORKERS SPAWNED, verdict and gates read the report with every claims fence removed). A duplicate recognised key, or a recognised value that breaks its grammar (files: comma list with no empty token; gates and tests: `;`-separated `id=digits` pairs; any empty value; `none` is the explicit empty), gives `claims=not-checked reason=claims-block-malformed` and selects no outcome. A nested or unclosed claims fence is also malformed. Size caps: report 1 MB, block 64 KB; over a cap gives `claims-too-large`. The fence scan is one pass. A claimed `files_changed` path whose final bytes were unreadable, or that is git-ignored with no baseline, is listed in `not_checked` (`observed` `unreadable` or `unbaselined`), never as supported or unsupported. a missing required key makes the whole block unreadable (`claims=not-checked`, FR-014). The block is data: it never grants anything and never sets the outcome, except that a `stopped` value other than `none` selects `unverified delegate-stopped` only at step 3 of the first-match order in `data-model.md` "Run outcome". A launch-level red (quota-paused, blocked, timeout, a launch failure and the other step 1 reasons) and a failed gate (step 2) both outrank a declared stop.

## Checks (FR-012)

| Claim | Compared with | Unsupported when |
|---|---|---|
| each `files_changed` path | baseline-to-final content hashes: the pre-launch snapshot hash of the path compared with its hash after the run (the snapshot verify prints `CHANGED` for in-scope paths whose hash differs and `OUTSIDE` for others) | the path did not change during the run. A final `git status --porcelain` alone is never evidence, because it cannot tell a file that was already dirty before launch from one changed in this run |
| a changed path not in `files_changed` | same | listed as `unclaimed-change` (warning) |
| each `gates` entry | `gate_results` by gate id (never by argv; two gates with the same argv have two ids) | no gate with that id was recorded, or the recorded exit code differs from the claimed one. A claim that matches a recorded failed gate (same command, same nonzero exit code) is supported; a claim of success for a recorded failed or not-checked gate is unsupported |
| an "all gates passed" phrase in prose | `gate_results` | any gate failed or was not checked |
| each `tests` entry | the excerpt of the named gate only, integers matching `Ran (\d+) tests?` or `(\d+) passed` | the named gate's excerpt does not contain that count, or the id names no recorded gate. An integer in another gate's output never supports the claim |
| gate coverage | the set of gate ids of the run | a gate id with no `gates` entry is reported `omitted` (advisory; also in the return row) |
| `stopped` other than `none` | the run's declared STOP RULE: the id `s1` or the full rule text | the value is neither `s1` nor the full rule text (whitespace and case normalised); a part of the text is unsupported |
| a `tests` count of 0, or a gate claimed passed whose excerpt shows zero tests collected (`Ran 0 tests`, `collected 0 items`, `no tests ran`) | the named gate's excerpt | flagged `weak` (advisory), not `unsupported` |

Output goes to `claims.json` in the run directory. No model call (FR-016).

Not checked here (stay with the reviewer): a cosmetic edit counted as a change, a gate that tests nothing meaningful, an in-scope test or helper rewritten to pass, and false prose outside the block. See spec.md "Not catchable by the claim check".
