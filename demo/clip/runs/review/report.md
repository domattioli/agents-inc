caveman: not installed -> by hand
caveman NOT installed -> checked by hand. No Skill tool in the grants, so I applied the rules myself. [verified: ALLOWED = Read, Glob, Grep]
GRILL: (1) Plan mode is on and says to write a plan file and call ExitPlanMode, but the grants don't include Write or ExitPlanMode and the task is read-only. I did no plan file and no ExitPlanMode, and this report is the only output. (2) The gate says to use `grep -F` and the verify uses `python3`, but Bash is denied. I used the Grep tool with escaped regex instead, and did not run verify. (3) The dispatch doesn't say whether an added sentence with no source counts as "differs". I didn't count it and list it below.

FINDING 1: Overview: The garden has 12 raised beds and two shared tool sheds. | source says: The garden has 21 raised beds and two shared tool sheds.
FINDING 2: Rules: Hoses may not be used before 9 am. | source says: City water rule: hoses may be used only before 9 am.

Evidence:
- F1: The count is wrong (12 instead of 21). formatted.md:4 vs source_notes.md:3 [verified]
- F2: The meaning is reversed. The source allows hoses only before 9 am; formatted.md bans them before 9 am. formatted.md:12 vs source_notes.md:7 [verified]
- Both errors were already in draft.md at lines 4 and 12, so the formatting step carried them over rather than adding them. [verified]
- Every other line matches the source in meaning: Schedule lines 7-9 match source 4-6, Rules lines 13-14 match source 8-9, Contacts lines 17-18 match source 10-11. [verified]

Action log:
```
Read source_notes.md -> 12 lines, ok
Read draft.md -> 19 lines, ok
Read out/formatted.md -> 19 lines, ok
Grep formatted.md (both quotes) -> 4:..., 12:... matched
Grep source_notes.md (both quotes) -> 3:..., 7:... matched
```

OUT OF SCOPE / INCOMPLETE:
(a) formatted.md:4 adds "This guide explains who waters, when, and how." It isn't in the source, but it doesn't contradict it, so it's not a finding. The supervisor should decide. [verified]
(a) I did not run the `grep -F` gate or the snapshot verify because Bash is denied. I checked the quotes with the Grep tool instead (regex with `.` escaped), and both matched. [verified] The supervisor needs to run g1 and g2.
(b) I assumed Grep with escaped regex is equivalent to `grep -F` for these strings. That held. [inferred]
(c) No files created or edited, and no plan file written (no Write grant).
(d) Gate commands run: none, exit code N/A.
WORKERS SPAWNED: 0

```claims
files_changed: none
gates: g1=N/A; g2=N/A
stopped: none
```