<!-- provenance: author=domattioli model=claude-sonnet-5-5 effort=medium date=2026-11-09 skill=speckit-specify repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Feature Specification: Split agentic docs into public and private sets

**Feature Branch**: `035-split-agentic-docs` (spec dir only; no branch)
**Created**: 2026-11-09
**Status**: Draft
**Input**: User description: "Split the agentic instruction docs into a private operator-facing set and a public consumer/contributor-facing set. Public AGENTS.md keeps layout, setup/test/run, project rules that bind everyone, docs style; operator rules, DomI pointers, docker mandate move to private locations; optional public docs/CONTRIBUTING.md for docker dev flow."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Outside contributor reads one clean instruction file (Priority: P1)

A contributor or consumer opens the repo and reads `AGENTS.md`. They find what the repo contains, how to run the tests, and the rules that bind every contributor. They find nothing about the maintainer's machine, private governance repo, or personal session procedures.

**Why this priority**: the public file is the first thing agents and people read. Operator rules there confuse outsiders and expose private workflow.

**Independent Test**: read the public `AGENTS.md` cold and answer: how do I run the tests, where does code live, what must I not do. Search it for operator-only terms; none appear.

**Acceptance Scenarios**:

1. **Given** the public `AGENTS.md`, **When** searched for DomI paths, dated operator rulings, and machine-local paths, **Then** no match is found.
2. **Given** the public `AGENTS.md`, **When** a contributor follows its setup and test commands, **Then** the full suite runs without any private file.
3. **Given** the layout, setup, project rules and documentation style content that exist today, **When** compared with the split result, **Then** every item that binds contributors is still present in the public set.

---

### User Story 2 - Operator keeps every private rule, loaded where sessions read it (Priority: P1)

The operator's sessions still receive operator rules (DomI pointers, docker mandate, dated rulings, delegation procedure) from a private location that agent sessions in this repo read automatically.

**Why this priority**: moving rules must not silently drop them. Losing the docker mandate or the delegation rules breaks the operator's workflow.

**Independent Test**: list every rule removed from the public file; each one appears in a named private location. A new session in this repo still reports the docker and delegation rules.

**Acceptance Scenarios**:

1. **Given** the list of removed rules, **When** each is looked up, **Then** it exists in exactly one private location.
2. **Given** a fresh operator session in this repo, **When** it starts, **Then** it loads the private rules without manual steps.
3. **Given** the private location, **When** checked against git, **Then** it is not tracked or published with the public repo.

---

### User Story 3 - Contributor finds the docker dev flow (Priority: P2)

A contributor wants to develop and stress-test the way the maintainer does. A public `docs/CONTRIBUTING.md` explains the docker flow in contributor wording, with the exact commands.

**Why this priority**: the docker flow helps everyone, but today it sits inside an operator-rule section.

**Independent Test**: follow only `docs/CONTRIBUTING.md` on a clean machine with docker; the suite and stress run complete.

**Acceptance Scenarios**:

1. **Given** `docs/CONTRIBUTING.md`, **When** its commands are run, **Then** the suite and stress check pass.
2. **Given** the public `AGENTS.md`, **When** it mentions docker, **Then** it points to `docs/CONTRIBUTING.md` instead of repeating operator wording.

---

### Edge Cases

- A rule serves both audiences (for example no pushes to `main`): it stays public in neutral wording and the private copy only adds operator detail.
- A tool or hook reads a path in the current `AGENTS.md` (for example a lint that checks a section heading): it must still find what it needs or be updated.
- Other repos link to current `AGENTS.md` anchors: broken anchors are listed, not silently left.
- The machine-level `~/.claude/AGENTS.md` already holds some operator rules: no rule is duplicated into two private places.
- No `CLAUDE.md` is created at any level.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The public `AGENTS.md` MUST contain repository layout, setup/test/run, project rules that bind all contributors, documentation style, and project canon order.
- **FR-002**: The public `AGENTS.md` MUST NOT contain machine-local paths, dated operator rulings, private-repo (DomI) pointers, or session procedures that apply only to the operator.
- **FR-003**: Every rule removed from the public file MUST appear in a named private location, listed in a migration table in the plan.
- **FR-004**: The private location MUST be read automatically by operator sessions in this repo and MUST NOT be tracked in the public repository.
- **FR-005**: A public `docs/CONTRIBUTING.md` MUST describe the docker develop, test and stress flow with exact commands, in contributor wording.
- **FR-006**: The public `AGENTS.md` MUST link to `docs/CONTRIBUTING.md` for docker and MUST NOT repeat it.
- **FR-007**: Rules that serve both audiences MUST stay public in neutral wording.
- **FR-008**: The change MUST NOT create any `CLAUDE.md`.
- **FR-009**: The change MUST list every tool, test, hook or document that reads a moved section, and update each.
- **FR-010**: Public docs MUST follow the repo documentation style table (human readers: short prose; agent files: maximum compression).

### Key Entities

- **Public instruction set**: `AGENTS.md`, `docs/CONTRIBUTING.md`; tracked, read by anyone.
- **Private instruction set**: operator rules held outside the public tree; read by operator sessions only.
- **Migration table**: maps each moved rule to its new location.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A search of the public instruction set for operator-only terms returns zero matches.
- **SC-002**: 100% of removed rules appear in the migration table with a private destination.
- **SC-003**: A contributor completes setup and the test run using only the public set, in under 10 minutes of reading.
- **SC-004**: A fresh operator session shows the docker and delegation rules loaded with no manual step.
- **SC-005**: The full test suite passes after the change, with no test or hook left reading a removed section.

## Clarifications

### Session 2026-11-09

- Q: Where does the private operator rule set live? -> A: gitignored `AGENTS.local.md` in the repo root.
- Q: Does the docker flow stay public? -> A: yes, in public `docs/CONTRIBUTING.md`.
- Q: Lint the public set? -> A: yes, agentic-docs lint is a gate.

## Assumptions

- The private location is a gitignored `AGENTS.local.md` (clarified). Machine-level rules stay in `~/.claude/AGENTS.md`. Plan must verify sessions load the local file, for example through an `@AGENTS.local.md` import in a private place or a session-start hook.
- DomI stays the home for specs and handoffs; this feature does not change that.
- No history rewrite: removed text stays in git history.
- Public wording for the docker flow reuses the commands already verified in `docker/stress_check.sh` and `docker/Dockerfile.ci`.
- A lint or sweep for agentic docs (`agentic-docs`) may run on the result.
