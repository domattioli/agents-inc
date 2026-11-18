#!/usr/bin/env python3
import json
import sys
import subprocess
import os
import re

# All 4 seats by default (luna, terra, sol, astra), slugs from agents_inc/routing.json (the single alias source, D-pin rule);
# the luna literal is the fallback. Roster / env-map overrides still replace a slug or add an alias.
ROUTING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "agents_inc", "routing.json")
SEAT_TIERS = {"luna": "grunt", "terra": "workhorse", "sol": "orchestrator", "astra": "executive"}
TIMEOUT_BY_EFFORT = {"high": 900, "xhigh": 1800}
DEFAULT_TIMEOUT = 300
EFFORTS = ["low", "medium", "high", "xhigh"]


def _pinned_seats(path=ROUTING, fallback="gpt-6-luna"):
    try:
        with open(path) as fh:
            tiers = json.load(fh)["tiers"]
    except (OSError, ValueError, KeyError, TypeError):
        return {"luna": fallback}
    seats = {}
    for alias, tier in SEAT_TIERS.items():
        try:
            slug = tiers[tier]["codex"]
        except (KeyError, TypeError):
            continue
        if isinstance(slug, str) and slug:
            seats[alias] = slug
    seats.setdefault("luna", fallback)
    return seats


def _pinned_luna(path=ROUTING, fallback="gpt-6-luna"):
    return _pinned_seats(path, fallback)["luna"]


DEFAULT_MODEL_MAP = _pinned_seats()


def _read_map(raw):
    raw = raw.strip()
    text = raw if raw.startswith("{") else open(os.path.expanduser(raw)).read()
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("models"), dict):
        data = data["models"]
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) and v for k, v in data.items()):
        raise ValueError("model map must be a JSON object of alias -> slug strings")
    return data


def load_model_map():
    """Defaults < ~/.config/agents-inc/roster.json < AGENTS_INC_MODEL_MAP < CODEXAGENT_MODEL_MAP.

    Env values are a JSON object string (starts with "{") or a path to a JSON file.
    Malformed override: warn on stderr, keep the rest, never raise.
    """
    merged = dict(DEFAULT_MODEL_MAP)
    roster = os.path.join(os.environ.get("HOME", ""), ".config/agents-inc/roster.json")
    sources = [("roster", roster if os.path.isfile(roster) else None)]
    sources += [(n, os.environ.get(n)) for n in ("AGENTS_INC_MODEL_MAP", "CODEXAGENT_MODEL_MAP")]
    for label, raw in sources:
        if not raw:
            continue
        try:
            merged.update(_read_map(raw))
        except (OSError, ValueError) as exc:
            sys.stderr.write("WARN: ignoring malformed model map from %s: %s; using defaults\n" % (label, exc))
    return merged


def send_response(obj):
    """Send JSON-RPC response to stdout."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def handle_initialize(req_id):
    """Handle initialize method."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "delegate-agent-mcp",
                "version": "0.1.0"
            }
        }
    }

def handle_tools_list(req_id):
    """Handle tools/list method."""
    model_map = load_model_map()
    models = sorted(model_map)
    default_model = "luna" if "luna" in model_map else models[0]
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": [
                {
                    "name": "DelegateAgent",
                    "description": ("Delegate a task to an agent (Codex models: %s). Runs in the Codex read-only sandbox: "
                                    "reads files and runs read-only commands under cwd, but writes no files, has no network "
                                    "and cannot run `agents-inc dispatch` or nested codex; ask for file content in the reply, "
                                    "or use `agents-inc dispatch` for write work. Time limit: %ds by default and for "
                                    "low/medium, %ds high, %ds xhigh; after a timeout, resume with conversation_id."
                                    % (", ".join(models), DEFAULT_TIMEOUT, TIMEOUT_BY_EFFORT["high"],
                                       TIMEOUT_BY_EFFORT["xhigh"])),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string"
                            },
                            "model": {
                                "type": "string",
                                "enum": models,
                                "default": default_model
                            },
                            "cwd": {
                                "type": "string"
                            },
                            "effort": {
                                "type": "string",
                                "enum": EFFORTS
                            },
                            "conversation_id": {
                                "type": "string",
                                "description": "Thread id from a previous call; resumes that conversation"
                            }
                        },
                        "required": ["prompt"]
                    }
                }
            ]
        }
    }

AUTH_RE = re.compile(r"refresh|401|unauthorized|login|token", re.IGNORECASE)
# Lines from MCP servers inside Codex (rmcp client, e.g. a GitHub server's AuthRequired) are not Codex login failures.
# Anchored to the real noise shapes (spec 047 G5): a Codex auth line that only mentions "mcp" in a URL keeps its hint.
MCP_NOISE_RE = re.compile(r"\brmcp::|AuthRequired\(")
TIMEOUT_EXIT = 124
# Spec 047 FR-007: the provider refused the model for this client. The "Model metadata ... not found" warning alone is
# not a rejection: Codex prints it before runs that then succeed on fallback metadata.
MODEL_REJECT_RE = re.compile(r"model_not_found|is not supported when using Codex")
MODEL_REJECT_HINT = (". Model not supported by this Codex client; update the CLI (npm install -g @openai/codex@latest) "
                     "or change the pin (agents-inc models)")


def _codex_model_rejected(returncode, stderr):
    return returncode not in (0, TIMEOUT_EXIT) and bool(MODEL_REJECT_RE.search(stderr or ""))


def _codex_auth_failed(stderr):
    return any(AUTH_RE.search(ln) and not MCP_NOISE_RE.search(ln) for ln in (stderr or "").splitlines()
               if not ln.startswith("CONVERSATION_ID="))


def _thread_id(stderr):
    for ln in (stderr or "").splitlines():
        if ln.startswith("CONVERSATION_ID="):
            return ln.split("=", 1)[1].strip()
    return ""


def _timeout_msg(limit, effort, thread_id=""):
    msg = "Error: Codex timed out after %ds (effort %s)" % (limit, effort or "default")
    if thread_id:
        return msg + "; resume with conversation_id %s" % thread_id
    return msg + "; the conversation can be resumed with conversation_id if its thread id is known"


def _last_line(text):
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip() and not ln.startswith("CONVERSATION_ID=")]
    return lines[-1] if lines else ""


def _result(req_id, text, is_error=False):
    res = {"content": [{"type": "text", "text": text}]}
    if is_error:
        res["isError"] = True
    return {"jsonrpc": "2.0", "id": req_id, "result": res}


def handle_tools_call(req_id, params):
    """Handle tools/call method."""
    if params.get("name") != "DelegateAgent":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": "Method not found"
            }
        }

    args = params.get("arguments", {})
    prompt = args.get("prompt")
    model = args.get("model", "luna")
    cwd = args.get("cwd")
    effort = args.get("effort")
    conversation_id = args.get("conversation_id")

    if not prompt:
        return _result(req_id, "Error: prompt required", True)

    # Resolve script path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "..", "scripts", "codexagent.sh")

    cmd = [script_path, "--model", model]
    if effort:
        cmd += ["--effort", str(effort)]
    if conversation_id:
        cmd += ["--resume", str(conversation_id)]
    cmd.append(prompt)

    limit = TIMEOUT_BY_EFFORT.get(effort, DEFAULT_TIMEOUT)
    env = dict(os.environ, CODEXAGENT_TIMEOUT=str(limit))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=limit + 30,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired:
        return _result(req_id, _timeout_msg(limit, effort), True)
    except Exception as e:
        return _result(req_id, f"Error: {str(e)}", True)

    stderr = result.stderr or ""
    last = _last_line(stderr)
    if result.returncode == TIMEOUT_EXIT:
        return _result(req_id, _timeout_msg(limit, effort, _thread_id(stderr)), True)
    if result.returncode != 0 or not (result.stdout or "").strip():
        if result.returncode != 0:
            msg = "Error: codex exited %d" % result.returncode
        else:
            msg = "Error: empty result from codex (exit 0)"
        if last:
            msg += ": " + last
        if _codex_model_rejected(result.returncode, stderr):
            msg += MODEL_REJECT_HINT
        elif _codex_auth_failed(stderr):
            msg += ". Codex login failed; run `codex login` in a terminal"
        return _result(req_id, msg, True)

    content = [{"type": "text", "text": result.stdout}]
    for line in stderr.splitlines():
        if line.startswith("CONVERSATION_ID="):
            content.append({"type": "text", "text": "conversation_id: " + line.split("=", 1)[1].strip()})
    return {"jsonrpc": "2.0", "id": req_id, "result": {"content": content}}


def main():
    """Main JSON-RPC server loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            # Silently skip malformed JSON
            continue

        method = req.get("method")
        req_id = req.get("id")
        params = req.get("params", {})

        # Notifications have no id
        if req_id is None and method == "notifications/initialized":
            # Notification: no response
            continue

        # Methods with id
        if method == "initialize":
            response = handle_initialize(req_id)
            send_response(response)

        elif method == "tools/list":
            response = handle_tools_list(req_id)
            send_response(response)

        elif method == "tools/call":
            response = handle_tools_call(req_id, params)
            send_response(response)

        else:
            # Unknown method
            if req_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": "Method not found"
                    }
                })

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--resolve-model":
        # Used by scripts/codexagent.sh: print slug for alias, exit 1 if unknown.
        _slug = load_model_map().get(sys.argv[2])
        if not _slug:
            sys.exit(1)
        print(_slug)
    elif len(sys.argv) == 2 and sys.argv[1] == "--list-models":
        print(" ".join(sorted(load_model_map())))
    else:
        main()
