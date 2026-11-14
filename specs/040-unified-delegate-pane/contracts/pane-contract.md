<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-14 skill=speckit-plan repo=agents-inc session=91aeecb8 -->
# Contract: delegate-pane 0.6.0 surface

- Pane id `agents-inc-delegates`; title agents-inc; auto-opens once at session.start; `/delegate-pane` reopens.
- Run sub-pane id `run-<runDir>`.
- No other agents-inc mod registers an auto-open or a pane.
- Sections order: mission map, status line, feed, tree, new-agent form, message box. Under 34 cols: form + message box behind one toggle line.
- Starts: native `$.agent.spawn`; Codex `$.process.spawn agents-inc dispatch ...` with effort; free `agent.sh submit` with run-style dir (run.json kind free).
- Message: live agent `$.session.send`; finished run -> resume via dispatch; free run -> refusal note.
- Store: `session:<id>` shape unchanged.
- Installer: `PANE_MODS` = delegate-pane only; retired mods uninstalled when present; second run makes no CLI write calls.
