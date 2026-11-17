# Upstream issue drafts for DomI (spec 042, FR-033)

Drafts only. Nothing is filed. The operator approves each body before it goes to the DomI repository (task T005). Supporting rows come from `specs/042-measured-status/evidence.md`, section "Findings that belong upstream". Row ids are retrospective ids in the form `repo/file prefix/date`, all in 2026.

## session-resume prints "none open" when the GitHub call failed

### What happens

The `session-resume` script reports open issues at session start. When the GitHub call fails, it prints "none open". The report then reads as a measured result: no open issues. The call never returned a count.

### What was expected

A failed call should print that the check did not run, with the reason if known. "None open" should appear only when the call succeeded and returned zero issues.

### Evidence

Row 1 of "Findings that belong upstream": the retrospective `63ca3257/11-15` from the operator's site repository. The same behaviour was seen again in the review session of 2026-11-15, where 28 issues were open in agents-inc while the script said none.

### Smallest suggested fix

Check the exit status of the GitHub call. On failure, print one line such as "open issues: not checked (GitHub call failed)". Keep the existing wording for a successful call.

### Out of scope

Retry logic, caching of earlier results, and changes to how the script reads handoffs.

## Scripts continue after a failed mktemp -d and act on the repository root

### What happens

Some scripts create a scratch directory with `mktemp -d` and then use the result without checking it. When `mktemp -d` fails, the variable is empty. The next commands run against the repository root instead of a scratch directory. In one session this led to 112 files being committed.

### What was expected

A failed `mktemp -d` should stop the script before any write, copy, delete or commit. No later step should run with an empty scratch path.

### Evidence

Row 2 of "Findings that belong upstream": retrospectives `e185f7e2/11-11` (112 files committed), `bc9f3f00/11-12` and `40af3ecb/10-28`, all from the DomI repository.

### Smallest suggested fix

After each `mktemp -d`, test the result and exit non-zero with a clear message if the call failed or the value is empty. A shared helper that does this would let each script use one line.

### Out of scope

Rewriting the scripts, changing where scratch directories live, and cleaning up commits that already happened.

## run_introspection.sh writes under / when the root variable is empty

### What happens

`run_introspection.sh` builds output paths from a root variable. When that variable is empty, the paths start at `/`, so the script tries to write under the filesystem root.

### What was expected

An empty root variable should stop the script with an error before any write. The script should not build a path from an unset or empty value.

### Evidence

Row 3 of "Findings that belong upstream": retrospectives `3a04a867/11-11` from the ADMESH repository and `63ca3257/11-15` from the operator's site repository.

### Smallest suggested fix

Require the root variable to be set and non-empty, for example with `${ROOT:?root not set}`, before the first path is built.

### Out of scope

Redesigning where introspection records are stored and any change to the record format.

## protected_paths_guard matches text, not the paths a command acts on

### What happens

The delete guard `protected_paths_guard` matches protected paths as text inside the command line. Two cases were seen:

- A read-only `df` command that contains the string `/System` was blocked.
- A relative delete run from inside a protected working directory is judged by the text of the command, not by the path it resolves to.

The first case is a false block. The second shows that text matching and path resolution give different answers.

### What was expected

The guard should decide on the resolved path that a delete would touch, using the working directory for relative paths. A command that only mentions a protected path, such as `df`, should not be blocked.

### Evidence

Row 4 of "Findings that belong upstream": retrospective `7d87e7ab/11-12` from the DomI repository. The row names both cases. It does not give the exact commands, so this draft does not either.

### Smallest suggested fix

Limit the check to commands that delete or move files. Resolve each target against the working directory before comparing it with the protected list.

### Out of scope

Changing the protected list itself and any bypass or approval flow.

## safe_rm.py exits 1 after a successful delete when its log write fails

### What happens

`safe_rm.py` deletes the target and then writes a log entry. When the log write fails, the script exits with status 1. The delete had already succeeded, so the caller sees a failure for work that was done.

### What was expected

The exit status should say what happened to the delete. A failed log write should be reported as a separate warning. The exit code should still show that the delete succeeded, or use a distinct code that callers can tell apart.

### Evidence

Row 5 of "Findings that belong upstream": retrospective `40af3ecb/10-28` from the DomI repository.

### Smallest suggested fix

Catch the log write error after the delete, print a warning that names the log problem, and return a status that does not claim the delete failed. Document the chosen codes in the script header.

### Out of scope

Changing the log format or location, and any change to which paths `safe_rm.py` accepts.
