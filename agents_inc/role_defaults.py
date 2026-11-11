"""Shipped role and dispatch-gate defaults (D78, operator rulings of 2026-11-11).

This module is the one named place for these defaults. The installer-managed block (`install/host_wiring.py`) and
the hook texts (`install/hook.py`) read them from here, so a later user-settings loader replaces values here and
nowhere else. Routing data (`routing.json`) names models per rung; this module names what each rung is for.
"""
from __future__ import annotations

# R1: role meaning per rung. The same meaning holds on the Claude and the Codex column.
RUNG_ROLES = {
    "executive": "judgment only",
    "orchestrator": "design or scope judgment, review, gates",
    "workhorse": "anything that writes: code, docs, git and PR mechanics",
    "grunt": "read-only: scouts, summaries, triage; writes no code",
}
# R1: the default rung for any task that writes. A code edit never defaults to the grunt rung.
WRITE_RUNG = "workhorse"
# R3: the model a Claude Code session gives a small edit through the native Agent tool.
NATIVE_EDIT_MODEL = "sonnet"
# R3: the tool-call count at or below which a task is small.
SMALL_TASK_CALLS = 3

ROUTE_LINE = "Route all delegation through agents-inc; never call another vendor's CLI or API directly; no paid API fallback."
EXECUTIVE_LINE = ("Executive (fable, astra; talks to the operator): judgment only (dialogue, decisions, briefs, "
                  "verification, acceptance); delegate all writing and anything a briefed orchestrator or workhorse can do.")
ROLES_LINE = ("Rungs: workhorse (sonnet, terra) writes code, docs, git and PRs; orchestrator (opus, sol) does design or "
              "scope judgment, review, gates; grunt (haiku, luna) is read-only: scouts, summaries, triage.")
GATE_LINE = (f"Gate: {SMALL_TASK_CALLS} or fewer tool calls, no writes: do it yourself; {SMALL_TASK_CALLS} or fewer "
             f"with edits: native workhorse subagent (Claude Code: Agent, model {NATIVE_EDIT_MODEL}; Codex: native "
             "subagent), short brief, then one check yourself; larger: `agents-inc dispatch`.")
