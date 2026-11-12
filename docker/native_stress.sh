#!/usr/bin/env bash
# Stress run for the stateless guest agent types (spec 038 T028), offline, against a fake Gemini server. No provider
# call, no Claude login, no key: the driver uses a temp HOME and a fake key. Scenarios tools, par and steps5, R runs each.
# Each run checks that session start sends 0 requests (SC-006), the reports, the ledger rows, events.jsonl and the usage sum.
#   docker run --rm --network none -e R=10 -v "$PWD:/src:ro" -v "$PWD/docker/native_stress.sh:/stress.sh:ro" agents-inc-ci bash /stress.sh
# On the Mac: bash docker/native_stress.sh (SRC defaults to this checkout).
# It does not run Claude Code or the mod's TS loop; docker/luna_stress.sh is the live, nested-Claude form for luna.
set -uo pipefail
SRC=${SRC:-$(cd "$(dirname "$0")/.." && pwd)}
[ -f "$SRC/tools/native_stress.py" ] || SRC=/src
cd "$SRC" && exec python3 tools/native_stress.py --src "$SRC" --r "${R:-10}" --scenarios "${SCENARIOS:-tools par steps5}"
