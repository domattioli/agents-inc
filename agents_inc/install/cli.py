"""Command line for user-scoped direct Codex installation."""
from __future__ import annotations
import argparse, datetime, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from .. import datafiles
from .bundle import activate, stage_bundle
from .discovery import install_skill_links, restore_skill_links
from .doctor import check_install, luna_line
from .host_wiring import install_alias_links, install_host_wiring, remove_host_wiring, unwire_hooks, HOSTS
from . import hook as host_hook
from .paths import InstallPaths
from .receipt import InstallReceipt, OwnedPath
from .runtime import resolve_executable, run_codex, run_codex_thread
from .transaction import LifecycleLock, TransactionJournal

def _paths(): return InstallPaths.for_home(Path.home())
def _efforts(release):
    models = json.loads((release / "agents_inc/models.json").read_text()).get("models", {})
    return {name: value["supported_efforts"] for name, value in models.items() if "supported_efforts" in value}
def _is_own_console_script(path: Path) -> bool:
    """True when `path` is the console script pip or pipx generated for this package (it imports our cli)."""
    try:
        if path.is_symlink() or not path.is_file(): return False
        with path.open("rb") as fh: head = fh.read(4096)
    except OSError: return False
    return b"agents_inc.install.cli" in head

def install_convenience_launcher(paths: InstallPaths, journal=None) -> OwnedPath:
    """Create only our stable user-bin link; preserve every foreign path."""
    desired = paths.current / "bin/agents-inc"
    paths.launcher.parent.mkdir(parents=True, exist_ok=True)
    if paths.launcher.exists() or paths.launcher.is_symlink():
        if paths.launcher.is_symlink() and paths.launcher.resolve() == desired.resolve():
            return OwnedPath(paths.launcher, "symlink", None, os.readlink(paths.launcher))
        if _is_own_console_script(paths.launcher):
            # `pip install --user` and pipx put the package's console script at this same path. It already
            # launches this package, so keep it; kind "external" means uninstall never touches it.
            return OwnedPath(paths.launcher, "external", None, None)
        raise RuntimeError(f"WB_CONFIG_CONFLICT: foreign launcher path {paths.launcher}")
    if journal: journal.apply("symlink", paths.launcher, None, str(desired), lambda: paths.launcher.symlink_to(desired))
    else: paths.launcher.symlink_to(desired)
    return OwnedPath(paths.launcher, "symlink", None, str(desired))

def _prior_owned(paths: InstallPaths) -> tuple:
    try: return InstallReceipt.load(paths.receipt).owned_paths if paths.receipt.exists() else ()
    except (OSError, ValueError): return ()

def _prior_receipt_copy(paths: InstallPaths) -> Path: return paths.state / "prior-receipt.json"

def _save_prior_receipt(paths: InstallPaths) -> bool:
    """Keep a verbatim copy of the receipt about to be replaced, for rollback."""
    copy = _prior_receipt_copy(paths)
    try: data = paths.receipt.read_bytes() if paths.receipt.is_file() else None
    except OSError: data = None
    if data is None: copy.unlink(missing_ok=True); return False
    paths.state.mkdir(parents=True, exist_ok=True)
    tmp = copy.with_name(copy.name + ".tmp"); tmp.write_bytes(data); os.chmod(tmp, 0o600); os.replace(tmp, copy); return True

def _restore_prior_receipt(paths: InstallPaths, prior_release: str) -> None:
    """Restore the saved prior receipt verbatim when it matches the release being restored, else synthesise."""
    receipt = InstallReceipt.load(paths.receipt)
    copy = _prior_receipt_copy(paths)
    try:
        data = copy.read_bytes()
        if InstallReceipt.load(copy).release_hash == Path(prior_release).name:
            tmp = paths.receipt.with_name(paths.receipt.name + ".rollback"); tmp.write_bytes(data); os.chmod(tmp, 0o600); os.replace(tmp, paths.receipt)
            return
    except (OSError, ValueError): pass
    InstallReceipt(Path(prior_release).name, receipt.python_path, receipt.codex_path, receipt.owned_paths, None, receipt.schema_version).save_atomic(paths.receipt)

PACKAGED_SOURCE = "packaged"  # source-checkout record when install ran from package data, not a checkout

def _packaged_source(tmp: Path) -> Path:
    """Build a bundle.py-layout source tree from the installed package (copies, not symlinks)."""
    package = Path(__file__).resolve().parents[1]
    shutil.copytree(package, tmp / "agents_inc", ignore=shutil.ignore_patterns("__pycache__", "_skills", "_docs"))
    for name in ("workerbee", "codex-bridge"):
        shutil.copytree(datafiles.repo_file(f"skills/{name}"), tmp / "skills" / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    schema = tmp / "docs/governance/SCHEMA-3NF.md"
    schema.parent.mkdir(parents=True)
    shutil.copy2(datafiles.repo_file("docs/governance/SCHEMA-3NF.md"), schema)
    shim = datafiles.repo_root() / "workerbees"
    if shim.is_dir():
        shutil.copytree(shim, tmp / "workerbees", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("agents-inc", *(m[0] for m in PANE_MODS)):
        mod = datafiles.repo_root() / "mods" / name
        if mod.is_dir():
            shutil.copytree(mod, tmp / "mods" / name, ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    return tmp

MOD_PLUGIN, MOD_MARKETPLACE = "agents-inc@agents-inc-local", "agents-inc-local"
# Pane mods (name, plugin, marketplace): a live pane per delegate model, and the agent tree. On by default with the install; each is skipped when the release does not ship it.
PANE_MODS = (("delegate-pane", "delegate-pane@delegate-pane-local", "delegate-pane-local"),
             ("agents-manager", "agents-manager@agents-manager-local", "agents-manager-local"))

def _claude(home: Path, *argv, timeout=60):
    """Run the Claude CLI quietly against the install's own HOME; returns the CompletedProcess, or None when it cannot run.
    HOME is explicit: an install into another home (tests, a temp HOME) must never register the mod in the caller's."""
    claude = shutil.which("claude")
    if not claude: return None
    env = dict(os.environ, HOME=str(home))
    try: return subprocess.run([claude, *argv], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, env=env)
    except (OSError, subprocess.SubprocessError): return None

def install_mod(paths: InstallPaths, notices: list) -> None:
    """Register the bundled mod with Claude Code (spec 027 FR-028). Never fails the install: a problem is a warning."""
    mod = paths.current / "mods/agents-inc"
    if not (mod / ".claude-plugin/plugin.json").is_file(): return
    listed = _claude(paths.home, "plugin", "list")
    if listed is None: return
    if MOD_PLUGIN in (listed.stdout or ""):
        # Spec 031 FR-014: refresh an installed plugin so a new manifest (mcpServers) reaches it. Warning only on failure.
        for argv in (("plugin", "marketplace", "update", MOD_MARKETPLACE), ("plugin", "update", MOD_PLUGIN)):
            done = _claude(paths.home, *argv, timeout=300)
            if done is None or done.returncode != 0:
                notices.append(f"warning: `claude {' '.join(argv)}` failed; the mod may be out of date")
                return
        return
    added = _claude(paths.home, "plugin", "marketplace", "add", str(mod.resolve()))
    done = _claude(paths.home, "plugin", "install", MOD_PLUGIN) if added is not None and added.returncode == 0 else added
    if done is None or done.returncode != 0:
        notices.append(f"warning: mod install failed ({'unavailable' if done is None else done.returncode}); the live view is off, delegation still works")

def install_pane_mods(paths: InstallPaths, notices: list) -> None:
    """Register the bundled pane mods. Same contract as install_mod: a problem is a warning, never a failed install."""
    listed = None
    for name, plugin, market in PANE_MODS:
        mod = paths.current / "mods" / name
        if not (mod / ".claude-plugin/plugin.json").is_file(): continue
        if listed is None:
            listed = _claude(paths.home, "plugin", "list")
            if listed is None: return
        if plugin in (listed.stdout or ""):
            for argv in (("plugin", "marketplace", "update", market), ("plugin", "update", plugin)):
                done = _claude(paths.home, *argv, timeout=300)
                if done is None or done.returncode != 0:
                    notices.append(f"warning: `claude {' '.join(argv)}` failed; the {name} pane may be out of date"); break
            continue
        added = _claude(paths.home, "plugin", "marketplace", "add", str(mod.resolve()))
        done = _claude(paths.home, "plugin", "install", plugin) if added is not None and added.returncode == 0 else added
        if done is None or done.returncode != 0:
            notices.append(f"warning: {name} pane install failed ({'unavailable' if done is None else done.returncode}); delegation still works")

MOD_UNINSTALL_ARGVS = (("plugin", "uninstall", MOD_PLUGIN), ("plugin", "marketplace", "remove", MOD_MARKETPLACE),
                       *[a for _, p, m in PANE_MODS for a in (("plugin", "uninstall", p), ("plugin", "marketplace", "remove", m))])

def uninstall_mod(paths: InstallPaths) -> list:
    notices = []
    for argv in MOD_UNINSTALL_ARGVS:
        done = _claude(paths.home, *argv)
        if done is not None and done.returncode != 0: notices.append(f"warning: `claude {' '.join(argv)}` failed ({done.returncode})")
    return notices

def install(args):
    """Install from --source, or from the installed package's own data when --source is omitted.
    A failure is loud (FAIL line, exit 1) and leaves a marker that doctor reports (#155)."""
    command = getattr(args, "command", None) or "install"
    paths = _paths()
    if not getattr(args, "no_host_wiring", False) and (paths.home / ".claude").is_dir():
        try: args.claude_settings = _settings_consent(args, paths, command)
        except (OSError, ValueError, RuntimeError) as exc:
            _report_install_failure(paths, command, exc); return 1
    try:
        if getattr(args, "source", None):
            code = _install(args, Path(args.source))
        else:
            tmp = Path(tempfile.mkdtemp(prefix="agents-inc-src-"))
            try:
                code = _install(args, _packaged_source(tmp))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:
        _report_install_failure(paths, command, exc)
        return 1
    if code == 0:
        try: (paths.state.joinpath(REPAIR_MARKER)).unlink(missing_ok=True)
        except OSError: pass
    return code

def _settings_consent(args, paths: InstallPaths, command: str, stdin=None) -> bool:
    """H (2026-11-11): print what install/repair adds to ~/.claude/settings.json; write only on --yes or a TTY yes.
    No change pending: True without asking. No TTY and no --yes: False, and print the command that applies it."""
    from .host_wiring import AT_ROUTE_NOTE, settings_plan
    exclude = not getattr(args, "no_sandbox_exclude", False)
    target, text, lines = settings_plan(paths, exclude)
    if text is None: return True
    print(f"agents-inc {command} will write these entries to {target} (backup kept; `agents-inc unwire` removes them):")
    for line in lines: print(f"  {line}")
    print(AT_ROUTE_NOTE)
    if getattr(args, "yes", False): return True
    stdin = sys.stdin if stdin is None else stdin
    if stdin.isatty():
        print(f"Write them to {target}? [y/N] ", end="", flush=True)
        if stdin.readline().strip().lower() in ("y", "yes"): return True
        print(f"not written: {target} left unchanged.")
        return False
    source = getattr(args, "source", None)
    flags = " ".join(([f"--source {Path(source).resolve()}"] if source else []) + ([] if exclude else ["--no-sandbox-exclude"]))
    print(f"no TTY and no --yes: {target} left unchanged. Apply with: agents-inc {command} --yes{(' ' + flags) if flags else ''}")
    return False

REPAIR_MARKER = "repair-failed.json"

def _report_install_failure(paths: InstallPaths, command: str, exc: Exception) -> None:
    detail = f"{exc.strerror} ({exc.filename})" if isinstance(exc, OSError) and exc.strerror else str(exc) or type(exc).__name__
    print(f"FAIL: agents-inc {command}: {detail}", file=sys.stderr)
    if isinstance(exc, OSError) and exc.errno in (1, 13):
        print("the file is not writable from here; inside the Claude Code sandbox run `agents-inc repair` from a normal terminal", file=sys.stderr)
    try:
        paths.state.mkdir(parents=True, exist_ok=True)
        marker = paths.state.joinpath(REPAIR_MARKER)
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        marker.write_text(json.dumps({"command": command, "at": stamp, "error": detail}) + "\n")
        marker.chmod(0o600)
    except OSError as err:
        print(f"FAIL: could not record the failure for doctor: {err}", file=sys.stderr)

def _install(args, source: Path):
    paths = _paths()
    notices = []
    with LifecycleLock(paths.lock):
        TransactionJournal.recover(paths.journal)
        journal = TransactionJournal(paths.journal).begin("install")
        try:
            staged = stage_bundle(source, paths)
            codex = None
            if not getattr(args, "without_codex", False):
                try: codex = resolve_executable("codex", os.environ.get("PATH"))
                except FileNotFoundError:
                    notices.append("NOTE: codex CLI not found -> Codex delegation unavailable; skills installed anyway. Re-run after installing codex, or pass --without-codex to silence.")
            # Carry prior ownership forward, or repair sees its own links as foreign paths.
            receipt = InstallReceipt(staged.digest, Path(sys.executable).resolve(), codex, _prior_owned(paths))
            receipt = activate(staged, paths, receipt, journal)
            receipt = install_skill_links(paths, staged.path, receipt, args.adopt_existing_workerbee, journal)
            launcher = install_convenience_launcher(paths, journal)
            owned = tuple(item for item in receipt.owned_paths if item.path != launcher.path) + (launcher,)
            receipt = InstallReceipt(receipt.release_hash, receipt.python_path, receipt.codex_path, owned, receipt.prior_release)
            if not getattr(args, "no_host_wiring", False):
                receipt = install_host_wiring(paths, receipt, journal, not getattr(args, "no_sandbox_exclude", False),
                                              getattr(args, "claude_settings", True))
                if (paths.home / ".claude").is_dir():
                    receipt, link_notices = install_alias_links(paths, receipt, journal); notices.extend(link_notices)
            paths.roster.parent.mkdir(parents=True, exist_ok=True)
            if not paths.roster.exists(): paths.roster.write_text("{}\n")  # empty, user-editable; never overwritten
            # Unowned cache for doctor's hook-drift check; not journaled, kept by uninstall.
            paths.state.mkdir(parents=True, exist_ok=True)
            (paths.state / "source-checkout").write_text((str(Path(args.source).resolve()) if getattr(args, "source", None) else PACKAGED_SOURCE) + "\n")
            # Receipt last: journal recovery of a "receipt" op unlinks the file, so any
            # failure before this point must leave the previous receipt in place.
            had_prior = _save_prior_receipt(paths)
            journal.apply("receipt", paths.receipt, str(_prior_receipt_copy(paths)) if had_prior else None, None, lambda: receipt.save_atomic(paths.receipt))
            # Verify before commit: a failure raises into recover(), which rolls the whole install back.
            verify_installed(paths)
            journal.commit()
            if getattr(args, "agent_gate", None): host_hook.write_agent_gate(paths, args.agent_gate)
            if not getattr(args, "no_host_wiring", False) and (paths.home / ".claude").is_dir() and getattr(args, "claude_settings", True): notices.append(host_hook.gate_notice(paths))
            if not getattr(args, "no_mod", False): install_mod(paths, notices); install_pane_mods(paths, notices)  # after commit: a mod problem never rolls the install back
            for line in notices: print(line)
            return 0
        except Exception:
            TransactionJournal.recover(paths.journal)
            raise

NOT_INSTALLED = "WB_NOT_INSTALLED: no install receipt at {}. Run: agents-inc install (add --source <agents-inc checkout> to install from a checkout), then: agents-inc doctor"

def verify_installed(paths: InstallPaths) -> None:
    """Post-install self-check (#35): fail loudly if the receipt or launcher is missing."""
    problems = []
    if not paths.receipt.is_file(): problems.append(f"receipt missing: {paths.receipt}")
    launcher_ok = (paths.launcher.is_symlink() and paths.launcher.resolve().is_file()) or _is_own_console_script(paths.launcher)
    if not launcher_ok: problems.append(f"launcher does not resolve: {paths.launcher}")
    if problems: raise RuntimeError("WB_INSTALL_UNVERIFIED: " + "; ".join(problems))

_RELEASE_HASH = re.compile(r"[0-9a-f]{64}")

def _is_release_hash(entry: Path) -> bool:
    """A content-addressed release dir: 64-hex name, a real directory, not a symlink."""
    return bool(_RELEASE_HASH.fullmatch(entry.name)) and entry.is_dir() and not entry.is_symlink()

def _link_unchanged(item: OwnedPath) -> bool:
    return item.target is not None and os.readlink(item.path) == item.target

def _current_is_ours(paths: InstallPaths, release: Path) -> bool:
    return paths.current.is_symlink() and (paths.current.parent / os.readlink(paths.current)).resolve() == release.resolve()

def _removable_releases(paths: InstallPaths, keep: Path | None) -> list[Path]:
    """Every hash-named release dir under `releases`, except the one `current` still resolves to."""
    if not paths.releases.is_dir(): return []
    return sorted(e for e in paths.releases.iterdir() if _is_release_hash(e) and (keep is None or e.resolve() != keep))

def plan_uninstall(paths: InstallPaths, receipt: InstallReceipt) -> tuple[list[Path], list[Path]]:
    """Read-only mirror of `uninstall`: (would_remove, would_retain). Takes no lock, writes nothing."""
    remove: list[Path] = []; retain: list[Path] = []
    for item in receipt.owned_paths:
        if item.kind != "symlink": continue
        if not item.path.is_symlink():
            if item.path.exists(): retain.append(item.path)
            continue
        if not _link_unchanged(item): retain.append(item.path)
        else: remove.append(item.path)  # a recorded predecessor is restored in place, never retained
    if retain:
        return remove, retain
    release = paths.releases / receipt.release_hash
    current_removed = _current_is_ours(paths, release)
    if current_removed: remove.append(paths.current)
    remove.append(paths.receipt)
    keep = paths.current.resolve() if paths.current.exists() and not current_removed else None
    remove.extend(_removable_releases(paths, keep))
    return remove, retain

def uninstall(paths: InstallPaths, receipt: InstallReceipt) -> set[Path]:
    """Remove only receipt-owned, byte-for-byte unchanged artifacts."""
    with LifecycleLock(paths.lock):
        TransactionJournal.recover(paths.journal)
        journal = TransactionJournal(paths.journal).begin("uninstall")
        restored: set[Path] = set()
        retained = restore_skill_links(paths, receipt, journal, restored)
        remove_host_wiring(paths, receipt, journal)
        for item in receipt.owned_paths:
            if item.kind != "symlink" or item.path in retained or item.path in restored or not item.path.is_symlink(): continue
            if not _link_unchanged(item):
                retained.add(item.path)
        if retained:
            # Receipt is evidence needed for a future conservative retry.
            journal.commit(); return retained
        # `current` is ours when it points at the receipt's release; a foreign link stays put.
        release = paths.releases / receipt.release_hash
        if _current_is_ours(paths, release):
            journal.apply("unlink", paths.current, os.readlink(paths.current), None, lambda: paths.current.unlink())
        journal.apply("receipt", paths.receipt, None, None, lambda: paths.receipt.unlink(missing_ok=True))
        journal.commit()
        # After commit: the release tree is content-addressed and reproducible, so its removal needs no journal.
        for stale in _removable_releases(paths, paths.current.resolve() if paths.current.exists() else None):
            shutil.rmtree(stale, ignore_errors=True)
        for empty in (paths.releases, paths.releases.parent):
            try: empty.rmdir()
            except OSError: break
        return retained
def main(argv=None):
    parser = argparse.ArgumentParser(prog="agents-inc")
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("install"); p.add_argument("--source"); p.add_argument("--yes", action="store_true", help="write ~/.claude/settings.json without asking"); p.add_argument("--no-sandbox-exclude", action="store_true", help="add no sandbox.excludedCommands entries"); p.add_argument("--adopt-existing-workerbee", action="store_true"); p.add_argument("--without-codex", action="store_true"); p.add_argument("--no-host-wiring", action="store_true"); p.add_argument("--no-mod", action="store_true"); p.add_argument("--agent-gate", choices=host_hook.AGENT_GATE_MODES)
    p = subs.add_parser("run"); p.add_argument("--model", required=True); p.add_argument("--effort", default="medium"); p.add_argument("--cwd", required=True); p.add_argument("--tools", action="store_true"); p.add_argument("--no-tools", action="store_true"); p.add_argument("--host-tools", action="store_true", help="tools off; the caller's host runs the tools the model names (the agents-inc:luna type)"); p.add_argument("--write", action="store_true"); p.add_argument("--network", action="store_true"); p.add_argument("--run-dir"); p.add_argument("--lead", metavar="RUN_DIR"); p.add_argument("--home-repo"); p.add_argument("--thread", metavar="FILE", help="keep one Codex thread in FILE: start it when missing or empty, resume it otherwise"); p.add_argument("--timeout", type=float, metavar="SECONDS", help="kill Codex after SECONDS and exit 124 (the agents-inc:luna step limit)")
    p = subs.add_parser("dispatch"); p.add_argument("--slots"); p.add_argument("--model"); p.add_argument("--effort"); p.add_argument("--cwd"); p.add_argument("--tier", choices=("grunt",)); p.add_argument("--run-dir"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--resume"); p.add_argument("--message"); p.add_argument("--home-repo"); p.add_argument("--serve", metavar="RUN_DIR"); p.add_argument("--poll-interval", type=float, default=1.0); p.add_argument("--idle-timeout", type=float, default=600.0); p.add_argument("--cancel", metavar="RUN_DIR"); p.add_argument("--wait", nargs=2, metavar=("RUN_DIR", "REQUEST_ID")); p.add_argument("--timeout", type=float, default=600.0)
    p = subs.add_parser("events", help="follow or redact live delegate events (spec 027)"); p.add_argument("verb", choices=("follow", "redact")); p.add_argument("run_dir", nargs="?")
    p = subs.add_parser("doctor"); p.add_argument("--json", action="store_true"); p.add_argument("--live-model"); p.add_argument("--probe", action="store_true", help="also run the tool-use probe for each free guest agent model (one free request each)")
    p = subs.add_parser("repair"); p.add_argument("--source"); p.add_argument("--yes", action="store_true", help="write ~/.claude/settings.json without asking"); p.add_argument("--no-sandbox-exclude", action="store_true", help="add no sandbox.excludedCommands entries"); p.add_argument("--adopt-existing-workerbee", action="store_true"); p.add_argument("--without-codex", action="store_true"); p.add_argument("--no-host-wiring", action="store_true"); p.add_argument("--no-mod", action="store_true"); p.add_argument("--agent-gate", choices=host_hook.AGENT_GATE_MODES)
    p = subs.add_parser("unwire"); p.add_argument("--host", choices=("claude",), default="claude")
    p = subs.add_parser("hook"); p.add_argument("event", choices=("session-start", "agent-nudge", "agent-done")); p.add_argument("--host", choices=("claude", "codex", "gemini"))
    p = subs.add_parser("ledger", add_help=False); p.add_argument("rest", nargs=argparse.REMAINDER)
    p = subs.add_parser("models"); p.add_argument("verb", nargs="?", choices=("bump", "chain", "probe")); p.add_argument("alias", nargs="?"); p.add_argument("slug", nargs="?"); p.add_argument("extra", nargs="*"); p.add_argument("--unpin", action="store_true"); p.add_argument("--clear", action="store_true")
    p = subs.add_parser("report", help="draft a bug report or feature request for agents-inc; --submit files it"); p.add_argument("kind", choices=("bug", "feature")); p.add_argument("--title", required=True); p.add_argument("--body", required=True, help="text, or - to read stdin"); p.add_argument("--submit", action="store_true")
    p = subs.add_parser("luna", help="the native agents-inc:luna subagent type (spec 028)"); p.add_argument("verb", choices=("status", "on", "off", "begin", "end")); p.add_argument("--json", action="store_true"); p.add_argument("--session"); p.add_argument("--agent"); p.add_argument("--cwd", default="."); p.add_argument("--outcome", choices=("done", "failed", "quota-paused", "aborted")); p.add_argument("--usage", help="JSON object of step usage sums (end)"); p.add_argument("--task", help="the Agent description (begin)"); p.add_argument("--all", action="store_true", help="status of every native type (the mod reads this once at session start)")
    p = subs.add_parser("native", help="guest agent types: native subagent types answered by a non-Claude model (spec 038)"); p.add_argument("verb", choices=("status", "on", "off", "allow", "begin", "end", "step")); p.add_argument("target", nargs="?", help="nickname or all (on|off); provider (allow)"); p.add_argument("--model"); p.add_argument("--provider"); p.add_argument("--workspace"); p.add_argument("--write-dir", action="append", help="a directory the free model may write (allow; repeatable; default .scratch)"); p.add_argument("--json", action="store_true"); p.add_argument("--session"); p.add_argument("--agent"); p.add_argument("--cwd", default="."); p.add_argument("--outcome", choices=("done", "failed", "quota-paused", "aborted")); p.add_argument("--usage"); p.add_argument("--task"); p.add_argument("--timeout", type=float, metavar="SECONDS", help="step: give up on the provider after SECONDS (exit 124)"); p.add_argument("--thread", metavar="FILE", help="step: accepted and ignored; stateless models resend the whole conversation")
    p = subs.add_parser("narrate", help="speak a short digest of each new Claude Code assistant message (prototype)"); p.add_argument("verb", choices=("on", "off", "status", "run")); p.add_argument("--summarizer", choices=("luna", "local"), default="luna"); p.add_argument("--voice", default="Samantha"); p.add_argument("--transcript"); p.add_argument("--decide-only", action="store_true"); p.add_argument("--once", action="store_true"); p.add_argument("--dry-run", action="store_true")
    subs.add_parser("rollback"); p = subs.add_parser("uninstall"); p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv); paths = _paths()
    try:
        if args.command == "install": return install(args)
        if args.command == "luna":
            from . import luna_native  # works before the receipt check: the mod asks at every session start
            if args.verb in ("begin", "end"):
                if not args.session or not args.agent: parser.error(f"luna {args.verb} needs --session and --agent")
                if args.verb == "end" and not args.outcome: parser.error("luna end needs --outcome")
                return luna_native.run_record(paths, args.verb, args.session, args.agent, args.cwd, args.outcome, args.usage, args.task)
            if args.verb == "status" and args.all:  # one read for every native type; files only, no provider request
                import json as _json
                from . import native
                print(_json.dumps(native.status_all(paths, args.cwd))); return 0
            return luna_native.run(paths, args.verb, args.json)
        if args.command == "native":
            from . import native  # works before the receipt check, like luna: the mod asks at every session start
            return native.run_cli(paths, args)
        if args.command == "narrate":
            from .. import narrate  # works before the receipt check: the flag file and watcher need no install receipt
            return narrate.run_cli(args, paths.home)
        if args.command == "dispatch":
            from . import dispatch  # works from a source checkout; Codex launch loads the receipt itself
            if args.cancel: return dispatch.cancel_run(args.cancel)
            if args.wait: return dispatch.wait(args.wait[0], args.wait[1], args.timeout)
            if args.serve: return dispatch.serve(args.serve, args.poll_interval, args.idle_timeout, args.home_repo)
            if not args.dry_run:  # a stale install stops every launch before it starts; --dry-run still renders
                from .doctor import stale_refusal
                refusal = stale_refusal(paths)
                if refusal: print(refusal, file=sys.stderr); return 1
            return dispatch.run(args)
        if args.command == "events":
            from .. import live_rows  # works before the receipt check, like dispatch
            if args.verb == "redact": sys.stdout.write(live_rows.redact(sys.stdin.read())); return 0
            if not args.run_dir: parser.error("events follow needs a run directory")
            return live_rows.follow(args.run_dir, sys.stdout)
        if args.command == "models" and args.verb == "probe":
            from . import native_probe  # spec 038 T026: one free request per model; target = nickname or all
            return native_probe.run(paths, args.alias)
        if args.command == "models":
            from . import models_cmd  # works from a source checkout, before the receipt check
            return models_cmd.run(args.verb, args.alias, args.slug, unpin=args.unpin, extra=args.extra, clear=args.clear)
        if args.command == "hook": return host_hook.run(paths, args.event, args.host)
        if args.command == "report":
            from . import report  # works without an install; doctor codes only when one exists
            try:
                codes = list(check_install(paths).codes) if paths.receipt.exists() else ["WB_NOT_INSTALLED"]
            except Exception:  # a broken install is itself worth reporting
                codes = ["DOCTOR_FAILED"]
            return report.run(args.kind, args.title, args.body, args.submit, codes)
        if args.command == "ledger":
            from .. import host_ledger  # lazy: hook events must not depend on the ledger import
            return host_ledger.cli(args.rest, paths.state)
        if args.command == "doctor":
            if args.probe:
                from . import native_probe
                native_probe.run(paths, None)
            report = check_install(paths, args.live_model)
            if args.json:
                print(json.dumps(report.as_dict()))
            else:
                print(" ".join(report.codes or ("READY",)))
                if "WB_REPAIR_FAILED" in report.codes:
                    try: info = json.loads(paths.state.joinpath(REPAIR_MARKER).read_text())
                    except (OSError, ValueError): info = {}
                    print(f"WB_REPAIR_FAILED: last {info.get('command', 'repair')} failed at {info.get('at', '?')}: {info.get('error', '?')}; run agents-inc repair from a normal terminal")
                print("agent gate: {} ({})".format(*host_hook.agent_gate_mode(paths)))
                line = luna_line(paths)
                if line: print(line)
                from . import native  # files only: one line per free guest agent model (US2 scenario 3)
                for nl in native.doctor_lines(paths): print(nl)
                for w in report.warnings: print(f"WARNING: {w}")
                if "WB_CLI_NOT_FOUND" not in (*report.codes, *report.warnings):
                    print("NOTE: Codex delegates have no network by default; a dispatch opts in with "
                          "`CODEX_NETWORK: yes` (needs CODEX_WRITE) or `agents-inc run --network` (D56).")
                from .update_check import notice
                update = notice(paths.state)
                if update: print(f"UPDATE: {update}")
            return 0 if report.ready else 1
        if args.command == "unwire":
            with LifecycleLock(paths.lock):
                removed = unwire_hooks(paths, args.host)
            target = paths.home / next(h.hooks_file for h in HOSTS if h.name == args.host)
            for line in removed: print(f"removed: {line}")
            if not removed: print(f"nothing to remove: no agents-inc hooks in {target}")
            else: print("`agents-inc repair` re-adds them; doctor reports WB_HOST_UNWIRED until then.")
            return 0
        if not paths.receipt.exists(): print(NOT_INSTALLED.format(paths.receipt), file=sys.stderr); return 1
        receipt = InstallReceipt.load(paths.receipt)
        if args.command == "run":
            from .dispatch import CLAUDE_MODELS  # lazy: dispatch imports from cli
            if args.model in CLAUDE_MODELS:
                print(f"Claude aliases go through: agents-inc dispatch --model {args.model} --effort {args.effort} --cwd {args.cwd}", file=sys.stderr)
                return 2
            if args.thread and args.lead:
                print("agents-inc run: --thread cannot be combined with --lead", file=sys.stderr)
                return 2
            if args.thread:
                return run_codex_thread(Path(args.thread), args.model, args.effort, Path(args.cwd), sys.stdin, receipt, _efforts(paths.current.resolve()), args.no_tools, args.write, args.tools, Path(args.run_dir).resolve() if args.run_dir else None, home_repo=args.home_repo, network=args.network, host_tools=args.host_tools, timeout_s=args.timeout)
            return run_codex(args.model, args.effort, Path(args.cwd), sys.stdin, receipt, _efforts(paths.current.resolve()), args.no_tools, args.write, args.tools, Path(args.run_dir).resolve() if args.run_dir else None, lead_dir=Path(args.lead).resolve() if args.lead else None, home_repo=args.home_repo, network=args.network, host_tools=args.host_tools, timeout_s=args.timeout)
        if args.command == "uninstall":
            if args.dry_run:
                would_remove, would_retain = plan_uninstall(paths, receipt)
                for argv in MOD_UNINSTALL_ARGVS: print(f"would run: claude {' '.join(argv)}")
                for path in would_remove: print(f"would remove: {path}")
                for path in would_retain: print(f"would retain: {path}")
                return 0
            retained = uninstall(paths, receipt)
            for line in uninstall_mod(paths): print(line)
            if retained: print("WB_CONFIG_CONFLICT: retained modified artifacts", file=sys.stderr); [print(p, file=sys.stderr) for p in sorted(retained)]; return 1
            return 0
        if args.command == "repair": return install(args)
        if args.command == "rollback":
            if not receipt.prior_release: raise RuntimeError("no predecessor release")
            if Path(receipt.prior_release).name == receipt.release_hash:
                raise RuntimeError(f"nothing to roll back: the predecessor is the current release {receipt.release_hash[:12]}")
            with LifecycleLock(paths.lock):
                TransactionJournal.recover(paths.journal); journal = TransactionJournal(paths.journal).begin("rollback")
                prior = os.readlink(paths.current) if paths.current.is_symlink() else None
                journal.apply("symlink", paths.current, prior, receipt.prior_release, lambda: (paths.current.unlink(missing_ok=True), paths.current.symlink_to(receipt.prior_release)))
                # Keep the receipt in step with `current`, or doctor reports WB_RELEASE_UNTRUSTED.
                journal.apply("receipt", paths.receipt, None, None, lambda: _restore_prior_receipt(paths, receipt.prior_release))
                journal.commit()
            return 0
    except (OSError, ValueError, RuntimeError) as exc: print(str(exc), file=sys.stderr); return 1
if __name__ == "__main__": raise SystemExit(main())
