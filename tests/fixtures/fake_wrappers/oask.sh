#!/usr/bin/env bash
# Stub wrapper for tests (spec 037). Reads stdin, never calls a provider.
# FAKE_RC (default 0), FAKE_REPLY (stdout), FAKE_STDERR (stderr), FAKE_LOG (file: one JSON line per call).
input=$(cat)
if [[ -n "${FAKE_LOG:-}" ]]; then
  python3 - "$FAKE_LOG" "$input" "$@" <<'PY'
import json, os, sys
log, stdin, argv = sys.argv[1], sys.argv[2], sys.argv[3:]
with open(log, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"wrapper": os.environ.get("FAKE_NAME", "stub"), "argv": argv, "stdin": stdin,
                         "task": os.environ.get("TASK"), "model": os.environ.get("MODEL"),
                         "governance": os.environ.get("WORKERBEES_GOVERNANCE")}) + "\n")
PY
fi
[[ -n "${FAKE_STDERR:-}" ]] && printf '%s\n' "$FAKE_STDERR" >&2
printf '%s' "${FAKE_REPLY-stub reply}"
exit "${FAKE_RC:-0}"
