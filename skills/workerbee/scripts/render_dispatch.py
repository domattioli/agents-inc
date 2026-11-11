"""Render dispatch from slots JSON: fill template with slot values, append header or contract reference.

Usage: python3 render_dispatch.py --slots <json> [--contract-ref <path>] [--header <path>] [--template <path>] [--model <alias>]

--slots: path to JSON file with slot values, keyed by slot name (required).
--contract-ref: path to contract file; if given, output "CONTRACT: <path>" instead of pasted header text.
--header: path to header.md; default: skills/workerbee/header.md relative to script directory.
--template: path to slots.md; default: skills/workerbee/slots.md relative to script directory.
--model: delegate model alias; feeds the derived REPORTING CHAIN line (see derive_chain).

Output: filled template (slots substituted), blank line, then either pasted header text or
CONTRACT: reference line followed by training opt-out line. No {{ may remain.
Pasted header text starts at the CAVEMAN line: the markdown title and authoring
comment above it are stripped. NOTES defaults to "none"; STYLE may be empty.

Exit 0 on success, 2 if required slot missing or empty (stderr names it).
"""
from __future__ import annotations
import json
import os
import re
import shlex
import sys
from pathlib import Path



# D48 fan-out defaults per Lead rung and model-to-rung table: dispatch_rungs.py.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from dispatch_rungs import ALIAS_VENDOR, FAN_OUT_BY_RUNG, LADDER, MODEL_RUNG  # noqa: E402
import dispatch_schema  # noqa: E402  (#131: loaded from this directory, so a pinned copy is the one that runs)

# #131 (H7): one fixed line after CONSTRAINTS, so the stop-on-block clause never depends on the slot author.
STOP_ON_BLOCK_LINE = ("STOP ON BLOCK: if a hook, permission classifier or sandbox blocks a tool call that the task needs, "
                      "stop and hand back to the dispatcher with the work done so far; never switch to another tool to "
                      "route around the block. A denial of an incidental side effect, such as a cache write, is not a "
                      "block: ignore it and continue.")


# 026 US4 (#109): C0 controls except tab, LF and CR, DEL, and bidirectional controls never reach a prompt.
# The same pattern lives in agents_inc/install/dispatch.py (a pinned checkout copy of this script may predate it);
# tests/test_dispatch_slot_screens.py pins the two equal.
CONTROL_CHAR_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f؜‎‏‪-‮⁦-⁩]")


def _nested_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _nested_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _nested_strings(item)


def control_char_hit(slots) -> tuple[str, str, int] | None:
    """(top-level slot key, `U+XXXX`, code-point offset) of the first refused character, else None."""
    for key, value in (slots.items() if isinstance(slots, dict) else ()):
        for text in _nested_strings(value):
            match = CONTROL_CHAR_RE.search(text)
            if match:
                return key, f"U+{ord(match.group(0)):04X}", match.start()
    return None


_FREE_PREFIXES = ("gemini-", "ministral-", "codestral-")


def _is_free_slug(word: str) -> bool:
    """Shape of a free-model slug (spec 037): gemini-*, ministral-*, codestral-*, or an OpenRouter `vendor/name:free`.
    Shape only; dispatch holds the exact allowed-slug map (agents_inc/install/free_launch.py)."""
    return word.startswith(_FREE_PREFIXES) or ("/" in word and word.endswith(":free"))


def default_fan_out(slots: dict, model: str | None = None) -> str:
    """Return the D48 FAN_OUT line value from a RUNG or MODEL slot, else Orchestrator defaults."""
    rung = "orchestrator"
    for value in (model, slots.get("MODEL")):  # spec 037: a free-model slug never fans out
        if isinstance(value, str) and _is_free_slug(value.strip().lower()):
            return "width 0, total 0, depth 0"
    for key, value in (("RUNG", slots.get("RUNG")), ("MODEL", slots.get("MODEL")), ("--model", model)):
        if isinstance(value, str) and value.strip():
            word = value.strip().lower()
            if word in FAN_OUT_BY_RUNG:
                rung = word
                break
            hit = next((r for m, r in MODEL_RUNG.items() if m in word), None)
            if hit:
                rung = hit
                break
    width, total, depth = FAN_OUT_BY_RUNG[rung]
    return f"width {width}, total {total}, depth {depth}"

# Commands a delegate may never be granted or have dispatch run: pushes, commits, privilege, deletion, network.
DANGER_RE = re.compile(r"\bgit\b[^;&|]*\b(?:push|commit)\b|\bsudo\b|\brm\b(?=[^;&|]*\s-\w*r)(?=[^;&|]*\s-\w*f)"
                       r"|\brm\b[^;&|]*\s--recursive\b|\bcurl\b|\bssh\b", re.IGNORECASE)
_GATE_KEYS = {"argv", "cwd", "timeout_s", "expect_rc", "network"}
# Filled when the slot is absent or blank, so a routine Worker dispatch needs only ROLE, TASK, CONSTRAINTS,
# OUT_OF_SCOPE, FILES_IN_SCOPE, STOP_RULE, SUCCESS_GATE and FAILURE_GATE (PRE_EXISTING_CHANGES defaults to the snapshot placeholder text; dispatch fills the path).
# Each default is the Worker case; a Lead, a confidential input or a plan deliverable sets the slot explicitly.
SLOT_DEFAULTS = {
    "ALLOWLIST": "none -- do all work yourself",
    "CLASSIFICATION": "internal (repo source, non-secret)",
    "EFFORT": "as set by the transport; medium when unset",
    "SECOND_OPINION": "not applicable -- routine code checked by a deterministic gate; the supervisor reviews",
    "PLAN_CONTRACT": "not applicable -- deliverable is not a plan.",
}
_BAD_PREFIX_CHARS = ("*", "(", ")", "`", "\0")


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_gates(value) -> tuple[list | None, str | None]:
    """Return (normalized gates, None), (None, None) when absent or empty, or (None, why). value: a list, or a
    JSON string that decodes to a list. Entry keys: argv (required), cwd (default "."), timeout_s (600), expect_rc (0), network (false)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None, "not valid JSON"
    if not isinstance(value, list):
        return None, "must be a list"
    if not value:
        return None, None
    out = []
    for n, g in enumerate(value, 1):
        who = f"entry {n}"
        if isinstance(g, str):  # #100: a plain command string is one gate; shlex splits it, no shell runs it
            g = {"argv": shlex.split(g)} if g.strip() else {}
        if not isinstance(g, dict) or not set(g) <= _GATE_KEYS:
            return None, f"{who} must be an object with keys from argv, cwd, timeout_s, expect_rc, network"
        argv = g.get("argv")
        if (not isinstance(argv, list) or not argv
                or not all(isinstance(a, str) and a and "\0" not in a and "\n" not in a for a in argv)):
            return None, f"{who} argv must be a non-empty list of non-empty strings without NUL or newline"
        cwd = g.get("cwd", ".")
        if (not isinstance(cwd, str) or not cwd or "\0" in cwd or cwd.startswith("/")
                or ".." in cwd.replace("\\", "/").split("/")):
            return None, f"{who} cwd must be a relative path without .."
        timeout = g.get("timeout_s", 600)
        if not _num(timeout) or not 0 < timeout <= 3600:
            return None, f"{who} timeout_s must be a number above 0 and at most 3600"
        expect = g.get("expect_rc", 0)
        if not isinstance(expect, int) or isinstance(expect, bool):
            return None, f"{who} expect_rc must be an integer"
        if DANGER_RE.search(" ".join(argv)):
            return None, f"{who} argv matches the danger list"
        network = g.get("network", False)  # gates run sandboxed with no network unless the gate opts in
        if not isinstance(network, bool):
            return None, f"{who} network must be true or false"
        entry = {"argv": list(argv), "cwd": cwd, "timeout_s": timeout, "expect_rc": expect}
        if network:
            entry["network"] = True
        out.append(entry)
    return out, None


def bash_allow_list(value) -> tuple[list, str | None]:
    """Return (command prefixes, None) or ([], why). value: a list of str, or one str with a prefix per line."""
    if value is None:
        return [], None
    lines = isinstance(value, str)
    if lines:
        value = value.splitlines()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return [], "must be a list of strings or one string with a prefix per line"
    out = []
    for raw in value:
        prefix = raw.strip()
        if not prefix:
            if lines:
                continue
            return [], "prefix must not be empty"
        if any(c in prefix for c in _BAD_PREFIX_CHARS) or "\n" in prefix:
            return [], f"prefix {prefix!r} holds a forbidden character (* ( ) backtick NUL newline)"
        if DANGER_RE.search(prefix):
            return [], f"prefix {prefix!r} matches the danger list"
        out.append(prefix)
    return out, None


def gate_text(gates: list) -> str:
    """One sentence for SUCCESS GATE: dispatch runs each command with no shell after the delegate exits."""
    parts = [f"`{shlex.join(g['argv'])}` in `{g['cwd']}` expecting exit code {g['expect_rc']}" for g in gates]
    return "After you exit, dispatch runs these commands with no shell: " + "; ".join(parts) + "."


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def default_pre_existing(files_in_scope) -> str:
    """#100: the PRE_EXISTING_CHANGES text when the slot is blank. `<snapshot>` is the placeholder dispatch
    replaces with the real path after capture; each bare path line under FILES IN SCOPE becomes an --allow."""
    allow = [ln.strip() for ln in _text(files_in_scope).splitlines()
             if ln.strip() and " " not in ln.strip() and not ln.strip().lower().startswith("none")]
    cmd = "python3 skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>" + "".join(f" --allow {a}" for a in allow)
    return f"snapshot <snapshot>; verify with `{cmd}`"


VERIFY_SCRIPT = "skills/workerbee/scripts/pre_dispatch_snapshot.py"
_GATE_META_RE = re.compile(r"&&|\|\||;|\||>|<|\$\(|`")


def verify_gate_ok(span: str) -> str | None:
    """#108: None when span is one plain snapshot verify command, else the reason it is not.
    Form: python3|python <...>/skills/workerbee/scripts/pre_dispatch_snapshot.py verify <snapshot>|<...>snapshot.json
    followed only by --allow <value> or --repo <value> pairs."""
    meta = _GATE_META_RE.search(span.replace("<snapshot>", ""))
    if meta:
        return f"shell metacharacter {meta.group(0)!r} in verify gate"
    try:
        argv = shlex.split(span)
    except ValueError as exc:
        return f"cannot parse verify gate: {exc}"
    if len(argv) < 4:
        return "verify gate needs python3 <script> verify <snapshot>"
    if not (argv[0] in ("python3", "python") or argv[0].endswith(("/python3", "/python"))):
        return f"verify gate must start with python3, not {argv[0]!r}"
    if (argv[1] != VERIFY_SCRIPT and not argv[1].endswith("/" + VERIFY_SCRIPT)) or ".." in Path(argv[1]).parts:
        return f"verify gate script must be {VERIFY_SCRIPT}, not {argv[1]!r}"
    if argv[2] != "verify":
        return f"verify gate subcommand must be verify, not {argv[2]!r}"
    if argv[3] != "<snapshot>" and not argv[3].endswith("snapshot.json"):
        return f"verify gate snapshot must be <snapshot> or a path ending snapshot.json, not {argv[3]!r}"
    rest = argv[4:]
    if len(rest) % 2:
        return "verify gate options must be --allow <value> or --repo <value> pairs"
    for flag in rest[::2]:
        if flag not in ("--allow", "--repo"):
            return f"verify gate option {flag!r} is not --allow or --repo"
    return None


def _first_alias(text: str) -> str | None:
    """Return the model alias that appears earliest in text, else None."""
    best = None
    for alias in MODEL_RUNG:
        m = re.search(r"\b%s\b" % alias, text, re.IGNORECASE)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), alias)
    return best[1] if best else None


def _alias_on_rung(vendor: str | None, rung: str) -> str | None:
    for alias, r in MODEL_RUNG.items():
        if r == rung and ALIAS_VENDOR.get(alias) == vendor:
            return alias
    return None


def derive_chain(slots: dict, model: str | None, settings: dict) -> dict:
    """Return DELEGATE, SUPERVISOR, EXECUTIVE plus a sources map (slot|setting|default).

    Precedence per seat: explicit slot, then setting chain.*, then the ladder default.
    DELEGATE: slot, then model argument, then MODEL slot, then the first alias named
    in ROLE (earliest position wins), else the word delegate. Pure: reads no files.
    """
    chain_cfg = settings.get("chain") if isinstance(settings, dict) else None
    chain_cfg = chain_cfg if isinstance(chain_cfg, dict) else {}
    sources = {}

    delegate = _text(slots.get("DELEGATE"))
    sources["DELEGATE"] = "slot"
    if not delegate:
        for cand in (model, slots.get("MODEL")):
            word = _text(cand).lower()
            if word:
                delegate = _first_alias(word) or word
                break
    if not delegate:
        delegate = _first_alias(_text(slots.get("ROLE"))) or "delegate"
        sources["DELEGATE"] = "default"

    key = delegate.lower()
    vendor = ALIAS_VENDOR.get(key)
    rung = MODEL_RUNG.get(key)

    supervisor = _text(slots.get("SUPERVISOR"))
    sources["SUPERVISOR"] = "slot"
    if not supervisor:
        if _text(chain_cfg.get("supervisor")):
            supervisor, sources["SUPERVISOR"] = _text(chain_cfg["supervisor"]), "setting"
        else:
            sources["SUPERVISOR"] = "default"
            above = None
            if rung == LADDER[-1]:
                above = "operator"
            elif rung in LADDER and LADDER.index(rung) + 1 < len(LADDER):
                above = _alias_on_rung(vendor, LADDER[LADDER.index(rung) + 1])
            supervisor = above or "CoS"

    executive = _text(slots.get("EXECUTIVE"))
    sources["EXECUTIVE"] = "slot"
    if not executive:
        if _text(chain_cfg.get("executive")):
            executive, sources["EXECUTIVE"] = _text(chain_cfg["executive"]), "setting"
        else:
            sources["EXECUTIVE"] = "default"
            top = _alias_on_rung(vendor, "executive")
            executive = top if top and top not in (key, supervisor.lower()) else supervisor
    return {"DELEGATE": delegate, "SUPERVISOR": supervisor, "EXECUTIVE": executive, "sources": sources}


def read_settings() -> dict:
    """Read ~/.config/agents-inc/settings.json via HOME; {} on any error. Never writes."""
    path = Path(os.environ.get("HOME", "~")).expanduser() / ".config/agents-inc/settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def extract_template(slots_path: Path) -> str:
    """Extract template from first ```text block in slots.md."""
    text = slots_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    in_block = False
    template_lines = []
    for line in lines:
        if line.strip().startswith("```text"):
            in_block = True
            continue
        if in_block and line.strip().startswith("```"):
            break
        if in_block:
            template_lines.append(line)
    return "".join(template_lines)


def header_body(header_text: str) -> str:
    """Drop the authoring wrapper (title, HTML comment); keep text from the CAVEMAN line."""
    lines = header_text.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        if line.startswith("CAVEMAN:"):
            return "".join(lines[idx:])
    raise ValueError("header has no CAVEMAN: line")


def main() -> int:
    # Parse arguments
    slots_path = None
    contract_ref = None
    header_path = None
    template_path = None
    model = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--slots" and i + 1 < len(args):
            slots_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--contract-ref" and i + 1 < len(args):
            contract_ref = args[i + 1]
            i += 2
        elif args[i] == "--header" and i + 1 < len(args):
            header_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--template" and i + 1 < len(args):
            template_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        else:
            print(f"Unknown argument: {args[i]}", file=sys.stderr)
            return 2
            i += 1

    if not slots_path:
        print("--slots is required", file=sys.stderr)
        return 2

    # Load slots JSON
    try:
        slots_data = json.loads(slots_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Failed to load slots file: {e}", file=sys.stderr)
        return 2

    hit = control_char_hit(slots_data)
    if hit:
        print(f"render: slot {hit[0]} has control character {hit[1]} at offset {hit[2]}", file=sys.stderr)
        return 2

    # #131: dispatch_record.v1. Old string forms are converted for the check only; the text that renders is unchanged.
    checked, converted = dispatch_schema.normalize(slots_data)
    errors = dispatch_schema.validate_record(checked, model=model)
    if errors:
        for err in errors:
            print(f"dispatch_record.v1 invalid: {err}", file=sys.stderr)
        return 2
    for name in ("FILES_IN_SCOPE", "ALLOWLIST", "FAN_OUT"):
        if name in slots_data and not isinstance(slots_data[name], str):
            slots_data[name] = dispatch_schema.slot_text(name, slots_data[name])
    slots_data.pop("schema_version", None)

    # Determine default paths relative to script directory
    script_dir = Path(__file__).resolve().parent.parent
    if header_path is None:
        header_path = script_dir / "header.md"
    if template_path is None:
        template_path = script_dir / "slots.md"

    # Load template
    try:
        template = extract_template(template_path)
    except FileNotFoundError as e:
        print(f"Template file not found: {e}", file=sys.stderr)
        return 2

    # Check required slots
    required_slots = {
        "ROLE", "TASK", "CONSTRAINTS", "OUT_OF_SCOPE", "FILES_IN_SCOPE", "STOP_RULE", "SUCCESS_GATE", "FAILURE_GATE",
        "PRE_EXISTING_CHANGES", "ALLOWLIST", "CLASSIFICATION", "EFFORT", "SECOND_OPINION",
        "PLAN_CONTRACT"
    }

    gates, why = parse_gates(slots_data.get("GATES"))
    if why:
        print(f"GATES invalid: {why}", file=sys.stderr)
        return 2
    _, why = bash_allow_list(slots_data.get("BASH_ALLOW"))
    if why:
        print(f"BASH_ALLOW invalid: {why}", file=sys.stderr)
        return 2
    if gates:
        slots_data["SUCCESS_GATE"] = (_text(slots_data.get("SUCCESS_GATE")) + " " + gate_text(gates)).strip()

    if not (isinstance(slots_data.get("FAN_OUT"), str) and slots_data["FAN_OUT"].strip()):
        slots_data["FAN_OUT"] = default_fan_out(slots_data, model)

    if not (isinstance(slots_data.get("NOTES"), str) and slots_data["NOTES"].strip()):
        slots_data["NOTES"] = "none"
    slots_data.setdefault("STYLE", "")

    chain = derive_chain(slots_data, model, read_settings())
    src = chain.pop("sources")
    slots_data.update(chain)
    print("chain: %s < %s < %s (%s, %s, %s)" % (
        chain["DELEGATE"], chain["SUPERVISOR"], chain["EXECUTIVE"],
        src["DELEGATE"], src["SUPERVISOR"], src["EXECUTIVE"]), file=sys.stderr)

    filled = []
    if not _text(slots_data.get("PRE_EXISTING_CHANGES")):
        slots_data["PRE_EXISTING_CHANGES"] = default_pre_existing(slots_data.get("FILES_IN_SCOPE"))
        filled.append("PRE_EXISTING_CHANGES")
    # #92: verify reads the repo from the snapshot, so the gate needs no `cd`; a compound command matches no grant.
    # #108: a span that names the script or a `verify` word is parsed by argv position.
    for span in re.findall(r"`([^`]*)`", slots_data["PRE_EXISTING_CHANGES"]):
        if "pre_dispatch_snapshot.py" in span or "verify" in span.split():
            err = verify_gate_ok(span)
            if err:
                print(f"PRE_EXISTING_CHANGES invalid: {err}; write the verify gate as one plain command",
                      file=sys.stderr)
                return 2
    for slot, value in SLOT_DEFAULTS.items():
        if not (isinstance(slots_data.get(slot), str) and slots_data[slot].strip()):
            slots_data[slot] = value
            filled.append(slot)
    if filled:
        print("defaults filled: " + ", ".join(filled), file=sys.stderr)
    if converted:
        print("normalized: " + ", ".join(converted), file=sys.stderr)

    missing = []
    for slot in sorted(required_slots):
        value = slots_data.get(slot, "").strip() if isinstance(slots_data.get(slot), str) else ""
        if not value:
            missing.append(slot)

    if missing:
        for slot in missing:
            print(f"Required slot missing or empty: {slot}", file=sys.stderr)
        return 2

    # Fill template
    result = template
    for slot_name, slot_value in slots_data.items():
        placeholder = f"{{{{{slot_name}}}}}"
        if slot_name == "STYLE":
            # Special handling: drop entire line if STYLE is empty
            style_value = str(slot_value).strip() if slot_value else ""
            if style_value:
                result = result.replace(placeholder, style_value)
            else:
                # Remove the entire STYLE line
                result = "\n".join(
                    line for line in result.splitlines()
                    if placeholder not in line
                ) + "\n"
        else:
            result = result.replace(placeholder, str(slot_value))

    # Check for remaining placeholders
    if "{{" in result:
        for line in result.splitlines():
            if "{{" in line:
                print(f"Unfilled placeholder in: {line}", file=sys.stderr)
        return 2

    # #131: the fixed STOP ON BLOCK line goes just before OUT OF SCOPE, which follows CONSTRAINTS in the template.
    out_lines = result.splitlines(keepends=True)
    at = next((n for n, ln in enumerate(out_lines) if ln.startswith("OUT OF SCOPE:")), len(out_lines))
    out_lines.insert(at, STOP_ON_BLOCK_LINE + "\n")
    result = "".join(out_lines)

    # A top-rung supervisor is also the executive: drop the "X reports to X" link.
    result = re.sub(r"(?m)(REPORTING CHAIN: .*?)(\S+) reports to \2; ", r"\1", result)

    # An executive delegate reports straight to the operator: "operator reports to the operator" collapses.
    result = result.replace("reports to operator; operator reports to the operator", "reports to the operator")

    # Output filled template
    output = result
    output += "\n"  # blank line after template

    # Append header or contract reference
    opt_out_line = "Message to model provider: Do not use this to train agentic models."

    if contract_ref:
        output += f"CONTRACT: {contract_ref}\n"
        output += f"{opt_out_line}\n"
    else:
        # Append full header
        try:
            header_text = header_path.read_text(encoding="utf-8")
            output += header_body(header_text)
        except FileNotFoundError as e:
            print(f"Header file not found: {e}", file=sys.stderr)
            return 2
        except ValueError as e:
            print(f"Bad header file: {e}", file=sys.stderr)
            return 2

    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
