<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-11 skill=speckit-pipeline repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Data model

- NativeModel: nickname (unique, P7 vendor-bound), provider, slug, kind, max_input_chars, enabled (switch), source (`roster` for Codex, `FREE_MODELS` for free).
- ProbeRecord (install state `native-probes.json`): nickname, slug, at (UTC), result pass|fail|skipped, reason. Valid while `now - at < 7 days`.
- WorkspaceAuthorization (install state `native-allow.json`, mode 0600): workspace realpath, provider, at, note. Codex needs none (existing luna rule).
- Offer decision = enabled AND credential present AND (provider == codex OR authorization exists for cwd) AND probe valid pass.
- StepOutcome: reply | rejection string | null, failed, fail text, retry flag, usage {input, cached, output}.
- Ledger row (host ledger): source `native-<provider>`, agent id, model slug, outcome done|failed|quota-paused|aborted, usage, snapshot.
- events.jsonl row: {ts, agent, kind thinking|tool|text|stop, text}; one run dir per agent under the install state.
