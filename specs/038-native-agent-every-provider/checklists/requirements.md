<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-11 skill=speckit-pipeline repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Requirements quality checklist: 038

- [x] CHK001 Every FR is testable (FR-001..FR-020 map to tasks T010-T053).
- [x] CHK002 $0 rule stated (FR-013) and paid OpenAI API excluded (Q4).
- [x] CHK003 Key handling stated with a test (FR-011, SC-005, T023).
- [x] CHK004 Confidential/workspace authorization stated (FR-012, Q2).
- [x] CHK005 No DomI dependency at run time (plan constraints).
- [x] CHK006 Docker dev/test named (tasks header, T001, T028, T053).
- [x] CHK007 First slice shippable alone without new types (Phase 2).
- [ ] CHK008 Operator rulings Q1-Q5 recorded as D-entries (open, T020, T052).
- [ ] CHK009 Sandbox position of mod spawns measured (open, T030).
- [ ] CHK010 Mod API registration count verified (open, T031).
- [x] CHK011 Out-of-scope items listed.
