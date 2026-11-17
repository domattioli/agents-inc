<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-14 skill=speckit-plan repo=agents-inc session=91aeecb8 -->
# Quickstart: verify spec 040

Dev and tests in docker (docs/CONTRIBUTING.md); Mac only installs.

1. Tests: mod tests in mods/delegate-pane/hooks (count >= the T001 baseline sum (113), all pass); `python3 -m unittest tests.test_mod_install tests.test_delegate_pane_rungs`; full suite `python3 -m unittest discover -s tests -p 'test_*.py'`.
2. SC-005: `git grep -n agents-manager -- . ':!CHANGELOG.md' ':!docs/DECISIONS.md' ':!specs'` shows only installer retired list and its test.
3. Install on Mac: run agents-inc installer; `claude plugin list` shows delegate-pane 0.6.0, no agents-manager, no luna-pane. Run again: no changes, no warnings.
4. Fresh session x5: one pane opens; empty state reads "Nothing is running." and tree "no delegates yet".
5. From the form: start one native, one Codex, one free delegate; each appears once in tree and once on map; click rows; message native; cancel Codex; free shows no message/cancel.
6. Narrow pane (<34 cols): toggle line expands form and message box.
7. Worktree: `git log fix/dispatch-non-git-cwd --not development main` report commits and diff only; operator decides; no unlock or remove (T022).
