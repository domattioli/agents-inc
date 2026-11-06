"""Tests for wrapper script integration (spec 012, T006, T009)."""
import os
import subprocess
from pathlib import Path
from tests._free012 import fixture, hermetic, parametrize, suite  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[1]



@fixture
def wrapper_env(hermetic, tmp_path, monkeypatch):
    """Set up environment for wrapper script execution."""
    # Create shimdir with curl shim
    shimdir = tmp_path / "shimdir"
    shimdir.mkdir()

    # Create curl shim
    curl_shim = shimdir / "curl"
    curl_shim.write_text("""#!/bin/bash
set -euo pipefail

# Curl shim for testing wrappers
# Parses -o FILE and -w FMT; writes body to file; appends status to stdout if -w has http_code

output_file=""
write_format=""
data=""

# Parse arguments
i=1
while [[ $i -le $# ]]; do
    arg="${!i}"

    case "$arg" in
        -o)
            i=$((i+1))
            output_file="${!i}"
            ;;
        -w)
            i=$((i+1))
            write_format="${!i}"
            ;;
        -d)
            i=$((i+1))
            data="${!i}"
            ;;
        --data*)
            i=$((i+1))
            data="${!i}"
            ;;
        @*)
            file="${arg#@}"
            if [[ -f "$file" ]]; then
                data=$(cat "$file")
            fi
            ;;
    esac
    i=$((i+1))
done

# Log the call
log_file="$HOME/.codex-bridge/curl_calls.log"
mkdir -p "$(dirname "$log_file")"
{
    echo "=== CURL CALL ==="
    for arg in "$@"; do
        echo "$arg"
    done
    if [[ -n "$data" ]]; then
        echo "=== DATA ==="
        echo "$data"
    fi
} >> "$log_file"

# Record the last request payload separately so tests can parse it exactly.
if [[ -n "$data" ]]; then
    echo -n "$data" > "$HOME/.codex-bridge/last_curl_payload.json"
fi

# Get status and body from environment
status="${SHIM_STATUS:-200}"
if [[ -n "${SHIM_BODY_FILE:-}" ]] && [[ -f "$SHIM_BODY_FILE" ]]; then
    body=$(cat "$SHIM_BODY_FILE")
else
    body='{"choices":[{"message":{"content":"test response"}}],"usage":{"prompt_tokens":10,"completion_tokens":5}}'
fi

# Write body to output file
if [[ -n "$output_file" ]]; then
    mkdir -p "$(dirname "$output_file")"
    echo -n "$body" > "$output_file"
fi

# Write status code if -w format requested
if [[ -n "$write_format" ]] && [[ "$write_format" == *"http_code"* ]]; then
    echo "$status"
fi
""")
    curl_shim.chmod(0o755)

    # Set up environment
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    existing_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{shimdir}:{existing_path}")
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))

    # Set dummy API keys
    monkeypatch.setenv("OPEN_ROUTER_API_KEY", "x" * 30)
    monkeypatch.setenv("GEMINI_API_KEY", "x" * 30)
    monkeypatch.setenv("MISTRAL_API_KEY", "x" * 30)

    # Ensure MODEL is not set unless test sets it
    monkeypatch.delenv("MODEL", raising=False)

    # Ensure WORKERBEES_GOVERNANCE is not set
    monkeypatch.delenv("WORKERBEES_GOVERNANCE", raising=False)

    # Create .codex-bridge directory and key files
    codex_dir = tmp_path / ".codex-bridge"
    codex_dir.mkdir(exist_ok=True)

    # Create key files for each provider (scripts look for files, not env vars)
    (codex_dir / "openrouter-key").write_text("sk-" + "x" * 30)
    (codex_dir / "gemini-key").write_text("ai-" + "x" * 30)
    (codex_dir / "mistral-key").write_text("mi-" + "x" * 30)

    return tmp_path, shimdir


@fixture
def repo_root():
    """Get repo root path."""
    return REPO_ROOT


# === T006: Wrapper pick_default Integration ===

class TestWrapperPickDefaultIntegration:
    """Test wrapper scripts use pick_default when MODEL not set."""

    def test_oask_no_model_uses_pick_default(self, wrapper_env, repo_root, monkeypatch):
        """oask.sh with no MODEL env asks pick_default for a model and sends it."""
        import json
        from agents_inc import free_health

        tmp_path, shimdir = wrapper_env

        # Ensure no MODEL env var
        monkeypatch.delenv("MODEL", raising=False)
        monkeypatch.delenv("TASK", raising=False)

        # Set shim to return 200
        monkeypatch.setenv("SHIM_STATUS", "200")

        # Reference: what pick_default would choose from the repo catalog for
        # the wrapper's default task ("summarize").
        expected_model = free_health.pick_default("openrouter", "summarize")
        assert expected_model is not None, "repo catalog has no eligible openrouter free model for 'summarize'"

        oask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "oask.sh"
        result = subprocess.run(
            ["bash", str(oask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        assert result.returncode != 3, f"oask.sh refused: {result.stderr}"

        # curl shim recorded the outgoing request payload -> assert model matches
        payload_file = tmp_path / ".codex-bridge" / "last_curl_payload.json"
        assert payload_file.exists(), "curl shim did not record a request payload"
        payload = json.loads(payload_file.read_text())
        assert payload["model"] == expected_model

    def test_oask_paid_model_refused_exit_3(self, wrapper_env, repo_root, monkeypatch):
        """oask.sh with paid MODEL exits 3 and stderr contains REFUSED."""
        tmp_path, shimdir = wrapper_env

        # Set a paid model (not :free)
        monkeypatch.setenv("MODEL", "openrouter/gpt-4:turbo")

        oask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "oask.sh"
        result = subprocess.run(
            ["bash", str(oask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        # Must exit 3
        assert result.returncode == 3, f"Expected exit 3, got {result.returncode}: {result.stderr}"

        # stderr must contain REFUSED
        assert "REFUSED" in result.stderr, f"stderr missing REFUSED: {result.stderr}"

        # curl should not have been called
        curl_log = tmp_path / ".codex-bridge" / "curl_calls.log"
        assert not curl_log.exists(), "curl should not be called for paid model"


# === T009: Wrapper Health Reporting ===

class TestWrapperHealthReporting:
    """Test wrapper scripts report health status via free_health report on exit."""

    def test_oask_429_with_retry_delay_reports_cooldown(self, wrapper_env, repo_root, monkeypatch):
        """oask.sh receives 429 with 'retry in 53.02s' -> exit trap reports rate_limited with cooldown."""
        from agents_inc import free_health

        tmp_path, shimdir = wrapper_env

        # Create 429 response body
        body_file = tmp_path / "body_429.json"
        body_file.write_text('{"error":{"message":"Rate limit exceeded. Please retry in 53.02s"}}')

        monkeypatch.setenv("SHIM_STATUS", "429")
        monkeypatch.setenv("SHIM_BODY_FILE", str(body_file))
        monkeypatch.setenv("MODEL", "deepseek/deepseek-v4-flash-0731:free")

        oask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "oask.sh"
        result = subprocess.run(
            ["bash", str(oask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        # Should error
        assert result.returncode != 0

        # Wrapper's own exit trap must have written the health record.
        health = free_health.load_health()
        assert health["openrouter"]["failure_streak"] == 1
        assert health["openrouter"]["status"] == "degraded"
        assert health["openrouter"]["cooldown_until"] is not None

    def test_gask_429_records_gemini_backend_key(self, wrapper_env, repo_root, monkeypatch):
        """gask.sh receives 429 -> exit trap records under gemini backend key with failure_streak."""
        from agents_inc import free_health

        tmp_path, shimdir = wrapper_env

        # Create 429 response
        body_file = tmp_path / "body_429.json"
        body_file.write_text('{"error":{"message":"Rate limit exceeded"}}')

        monkeypatch.setenv("SHIM_STATUS", "429")
        monkeypatch.setenv("SHIM_BODY_FILE", str(body_file))

        gask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "gask.sh"
        result = subprocess.run(
            ["bash", str(gask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        # Should error
        assert result.returncode != 0

        # gask default tier "digest" -> model "gemini-3.8-flash" -> backend key "gemini-flash"
        expected_key = free_health.backend_key("gemini", "gemini-3.8-flash")
        health = free_health.load_health()
        assert expected_key in health
        assert health[expected_key]["failure_streak"] == 1

    def test_mask_429_records_mistral_backend_key(self, wrapper_env, repo_root, monkeypatch):
        """mask.sh with https_proxy loopback -> fails, exit trap reports error under mistral."""
        from agents_inc import free_health

        tmp_path, shimdir = wrapper_env

        # For mask.sh, use https_proxy to fail fast on urllib
        monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")

        mask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "mask.sh"
        result = subprocess.run(
            ["bash", str(mask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        # Should fail due to proxy
        assert result.returncode != 0

        # Wrapper's own exit trap must have reported the connection failure.
        health = free_health.load_health()
        assert "mistral" in health
        assert health["mistral"]["last_error"]

    def test_oask_200_success_resets_streak(self, wrapper_env, repo_root, monkeypatch):
        """oask.sh receives 200 success -> exit trap reports ok, streak resets to 0."""
        from agents_inc import free_health

        tmp_path, shimdir = wrapper_env

        # Pre-seed a failure state for the backend the wrapper will report under.
        free_health.report("openrouter", "auto:free", "rate_limited")
        health = free_health.load_health()
        assert health["openrouter"]["failure_streak"] == 1

        monkeypatch.setenv("SHIM_STATUS", "200")
        monkeypatch.setenv("MODEL", "auto:free")

        oask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "oask.sh"
        result = subprocess.run(
            ["bash", str(oask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, f"oask failed: {result.stderr}"

        health = free_health.load_health()
        assert health["openrouter"]["failure_streak"] == 0
        assert health["openrouter"]["status"] == "ok"
        assert health["openrouter"]["cooldown_until"] is None


# === Integration: Wrapper execution flow ===

class TestWrapperExecution:
    """Test wrapper script execution with real subprocess calls."""

    def test_oask_with_shim_executes_and_logs(self, wrapper_env, repo_root, monkeypatch):
        """oask.sh executes via subprocess, curl shim is called, logs recorded."""
        tmp_path, shimdir = wrapper_env

        monkeypatch.setenv("SHIM_STATUS", "200")

        oask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "oask.sh"
        result = subprocess.run(
            ["bash", str(oask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        # Should succeed
        assert result.returncode == 0, f"oask failed: {result.stderr}"

        # Verify curl shim was called
        curl_log = tmp_path / ".codex-bridge" / "curl_calls.log"
        assert curl_log.exists(), "curl shim was not called"

    def test_gask_with_shim_executes(self, wrapper_env, repo_root, monkeypatch):
        """gask.sh executes via subprocess with curl shim."""
        import json

        tmp_path, shimdir = wrapper_env

        monkeypatch.setenv("SHIM_STATUS", "200")

        # Provide a proper Gemini API response
        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "test response"}
                        ],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5
            }
        }
        body_file = tmp_path / "gemini_response.json"
        body_file.write_text(json.dumps(gemini_response))
        monkeypatch.setenv("SHIM_BODY_FILE", str(body_file))

        gask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "gask.sh"
        result = subprocess.run(
            ["bash", str(gask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        # Should succeed
        assert result.returncode == 0, f"gask failed: {result.stderr}"

    def test_mask_with_proxy_fails_gracefully(self, wrapper_env, repo_root, monkeypatch):
        """mask.sh with https_proxy fails gracefully (no external network)."""
        tmp_path, shimdir = wrapper_env

        monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")

        mask_script = repo_root / "skills" / "codex-bridge" / "scripts" / "mask.sh"
        result = subprocess.run(
            ["bash", str(mask_script), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

        # Should fail due to connection failure (proxy)
        assert result.returncode != 0


# === Spec 029 FR-001: wrapper temp files ===

class TestWrapperTempFiles:
    """Wrappers write no fixed /tmp names; their temp files are unique and removed."""

    SCRIPTS = ("oask.sh", "mask.sh", "gask.sh")

    def _run(self, repo_root, name, tmpdir, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmpdir))
        monkeypatch.setenv("SHIM_STATUS", "200")
        # mask.sh goes through the proxy so it fails fast without network.
        monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
        return subprocess.run(
            ["bash", str(repo_root / "skills" / "codex-bridge" / "scripts" / name), "test prompt"],
            env=os.environ.copy(),
            cwd=str(repo_root),
            timeout=30,
            capture_output=True,
            text=True
        )

    def test_no_fixed_tmp_names(self, repo_root):
        """T003: no script holds a /tmp/<name>report_err or /tmp/<name>response literal."""
        import re
        pattern = re.compile(r"/tmp/[a-z_]+(report_err|response)")
        for name in self.SCRIPTS:
            text = (repo_root / "skills" / "codex-bridge" / "scripts" / name).read_text()
            assert not pattern.search(text), f"{name} still writes a fixed /tmp name"

    def test_temp_dir_empty_after_run(self, wrapper_env, repo_root, monkeypatch):
        """T004: each wrapper leaves its own TMPDIR empty on exit."""
        tmp_path, shimdir = wrapper_env
        tmpdir = tmp_path / "t"
        for name in self.SCRIPTS:
            tmpdir.mkdir(exist_ok=True)
            self._run(repo_root, name, tmpdir, monkeypatch)
            assert list(tmpdir.iterdir()) == [], f"{name} left files in TMPDIR"

    def test_unwritable_temp_dir_fails_clean(self, wrapper_env, repo_root, monkeypatch):
        """T005: an unwritable TMPDIR fails before the request: non-zero, no traceback, no files."""
        import unittest
        tmp_path, shimdir = wrapper_env
        tmpdir = tmp_path / "ro"
        tmpdir.mkdir()
        tmpdir.chmod(0o500)
        try:
            if os.access(tmpdir, os.W_OK):
                raise unittest.SkipTest("chmod 0o500 does not block writes for this user")
            for name in self.SCRIPTS:
                result = self._run(repo_root, name, tmpdir, monkeypatch)
                assert result.returncode != 0, f"{name} exited 0 with unwritable TMPDIR"
                assert "Traceback" not in result.stderr, f"{name} traceback: {result.stderr}"
                assert list(tmpdir.iterdir()) == [], f"{name} left files in TMPDIR"
        finally:
            tmpdir.chmod(0o700)


def load_tests(loader, tests, pattern):
    """Expose this fixture-style file to `unittest discover` (see _free012.suite)."""
    return suite(globals(), autouse=("hermetic",))
