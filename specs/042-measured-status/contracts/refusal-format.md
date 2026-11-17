<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-15 skill=speckit-pipeline repo=agents-inc session=b437620e -->
# Contract: refusal message format and rule list

## Format (FR-022, FR-024)

Every refusal or lint failure from an agents-inc screen prints these three lines on stderr (the hook puts them in `permissionDecisionReason`, joined by spaces):

```text
refused: <rule-id> (<one-line rule summary>)
value: <offending text, screened, at most 200 bytes>
fix: <one corrected example, or the next command to run>
```

A message never shows only a number. A pointer to a template or reference names a command: `agents-inc dispatch --print-template` (prints the `slots.md` worked example) or `agents-inc dispatch --rules` (prints this rule list). It never names a path under `~/.claude/skills` or `~/.local/share/agents-inc`.

## Rules found in code (2026-11-15)

One entry per rule. "Where" is the current refusal site. The rule ids are the proposed stable names for `agents_inc/install/rules.py`.

| Rule id | Screen | Where | Fix line |
|---|---|---|---|
| `gates-not-json-list` | grants | `dispatch.py:1608-1609` | `GATES: ["python3 -m unittest tests.test_x"]` |
| `gates-invalid` | grants | `dispatch.py:1610-1612` (`render_dispatch.parse_gates`) | `{"argv": ["pytest", "-q"], "cwd": ".", "timeout_s": 600, "expect_rc": 0}` |
| `gate-credential-path` | grants | `dispatch.py:1615-1618` | name a test file, not a secret path |
| `gate-cwd-outside` | grants | `dispatch.py:1619-1620` | use a relative cwd inside `--cwd`, such as `"."` |
| `gate-danger` | grants | `render_dispatch.DANGER_RE`, re-screen `dispatch.py:1318-1320` | remove push, commit, sudo, recursive rm, curl, ssh |
| `bash-allow-invalid` | grants | `dispatch.py:1621-1623` | `BASH_ALLOW: ["gh issue view 54 -R owner/repo"]` |
| `bash-allow-credential` | grants | `dispatch.py:1624-1626` | drop the secret-bearing token |
| `broker-owned-slot` | broker | `dispatch.py:2496-2497` | remove BASH_ALLOW or PERMISSION_MODE from the request |
| `capability-missing` | capability | `dispatch.py:1919-1925` (D72 item 3) | install the gate program or remove the gate |
| `schema-invalid` | render | `dispatch_schema.validate_record`, `render_dispatch.py:398-401` | per field: allowed values listed |
| `classification-value` | render | `dispatch_schema.py:135` | `CLASSIFICATION: internal` (public, internal, confidential) |
| `effort-value` | render | `dispatch_schema.py:142` | `EFFORT: medium` |
| `schema-version` | render | `dispatch_schema.py:125` | omit `schema_version` or set 1 |
| `slot-list-type` | render | `dispatch_schema.py:84-92` | `FILES_IN_SCOPE: ["a.py", "b.py"]` |
| `fan-out-shape` | render | `dispatch_schema.py:95-107` | `FAN_OUT: {"width": 2, "total": 4, "depth": 1}` |
| `slot-missing` | render | `render_dispatch.py:483` | `agents-inc dispatch --print-template` |
| `placeholder-unfilled` | render | `render_dispatch.py:508` | fill the named slot |
| `control-char` | render / broker | `render_dispatch.py:392`; `dispatch.py:2502-2503` | remove the named code point |
| `scope-glob` | scope | `dispatch.py:1909-1910` | list exact paths, no `*`, `?` or `[` |
| `lint-element-<n>` (14 rules, one per element name) | lint | `check_dispatch_prompt.py:229-234`, `479-483` | per element; element 3: ``FAILURE GATE: `test -f out.txt` exits 1`` |
| `lint-fan-out` | lint | `check_dispatch_prompt.py:241-242` | `FAN_OUT: width 0, total 0, depth 0` |
| `lint-fan-out-ceiling` | lint | `check_dispatch_prompt.py:470-474` | reduce to the rung ceiling |
| `lint-reporting-chain-inverted` | lint | `check_dispatch_prompt.py:130`, `312` | name the supervisor one level up the chain |
| `lint-files-in-scope` | lint | `check_dispatch_prompt.py:319` | `FILES IN SCOPE: path/a.py` |
| `lint-stop-rule` | lint | `check_dispatch_prompt.py:328` | `STOP RULE: stop after 20 tool calls` |
| `lint-contract-*` (unparsable, sha256-malformed, not-regular-file, unreadable, sha256-mismatch, reference-on-bare-transport) | lint | `check_dispatch_prompt.py:421-460` | per rule |
| `credential-slot-text` | credential | `dispatch.py:1710-1713`, `2306-2316` | remove the secret path; deny-list wording belongs in OUT_OF_SCOPE |
| `credential-secret-var-print` | credential | `dispatch.py:2280-2282` | do not print a secret variable |
| `non-git-refused` | non-git | `dispatch.py:1560-1565` | dispatch from a git repository with files in `.scratch/<task>/` |
| `grants-refused` | grants | `dispatch.py:1943-1947` | per detail |
| `install-stale` | install | `doctor.py:75-86` | `agents-inc repair --source <checkout>` |
| `caller-sandboxed` | install | `dispatch.py` `SANDBOX_FIX` (D71 F1), exit 69 | one plain command, or allow `api.anthropic.com` |
| `broker-tier-model-mismatch`, `broker-bad-slots`, `broker-worker-cannot-lead`, `broker-no-sandbox-backend`, `broker-fan-out-zero`, `broker-fan-out-total-exhausted`, `broker-oversize` | broker | `dispatch.py:2490-2510`, `2582-2588`; `mcp_broker.py:211-212` | per rule |
| `hook-compound` | hook | `hook.py:131-134`, `359-370` | `agents-inc dispatch --slots <file> --model <alias>` as the whole call |
| `hook-unparsed` | hook | new (FR-028) | same as `hook-compound` |
| `hook-persona` | hook | `hook.py:388-389` | per message (UNVERIFIED: text not read) |
| `hook-agent-gate` | hook | `hook.py:468-471` | per message (UNVERIFIED: text not read) |
| `credential-undecidable` | credential | new (FR-026) | write the path literally so the screen can judge it |

The coverage test (FR-023) collects rule ids from `rules.py`, asserts every refusal site raises one of them (by grepping for the `refuse(` helper), and asserts each id has one line in `skills/workerbee/QUICKREF.md`.
