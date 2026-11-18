"""Spec 048 US3: mask.sh --handle gives each Mistral agent conversation its own id file."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASK = ROOT / "skills" / "codex-bridge" / "scripts" / "mask.sh"

# A sitecustomize that answers every urlopen with a canned Mistral conversation reply.
SHIM = '''
import io, json, os, urllib.request

class _Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def getcode(self): return 200

def _urlopen(request, timeout=None):
    body = {"conversation_id": os.environ["FAKE_CONVERSATION"],
            "outputs": [{"type": "message.output", "role": "assistant", "content": "hi"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    return _Response(json.dumps(body).encode())

urllib.request.urlopen = _urlopen
'''


class MaskHandleTest(unittest.TestCase):
    def run_mask(self, home: str, shim: str, conversation: str, *flags: str):
        env = {k: v for k, v in os.environ.items() if k not in ("SANDBOX_RUNTIME",)}
        env.update(HOME=home, MISTRAL_API_KEY="k" * 30, MISTRAL_AGENT_ID="agent-1", FAKE_CONVERSATION=conversation,
                   PYTHONPATH=shim + os.pathsep + env.get("PYTHONPATH", ""))
        return subprocess.run(["bash", str(MASK), "--agent", *flags, "hello"], env=env, capture_output=True, text=True, timeout=60)

    def test_two_handles_get_two_id_files_and_the_legacy_file_is_untouched(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as shim:
            Path(shim, "sitecustomize.py").write_text(SHIM)
            a = self.run_mask(home, shim, "conv-a", "--handle", "job-a")
            b = self.run_mask(home, shim, "conv-b", "--handle", "job-b")
            self.assertEqual(a.returncode, 0, a.stderr)
            self.assertEqual(b.returncode, 0, b.stderr)
            base = Path(home, ".codex-bridge")
            self.assertEqual(Path(base, "mistral-conversations", "job-a").read_text(), "conv-a")
            self.assertEqual(Path(base, "mistral-conversations", "job-b").read_text(), "conv-b")
            self.assertFalse(Path(base, "mistral-conversation-id").exists())

    def test_without_handle_the_legacy_file_is_used(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as shim:
            Path(shim, "sitecustomize.py").write_text(SHIM)
            r = self.run_mask(home, shim, "conv-legacy")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(home, ".codex-bridge", "mistral-conversation-id").read_text(), "conv-legacy")
            self.assertFalse(Path(home, ".codex-bridge", "mistral-conversations").exists())

    def test_handle_is_sanitised(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as shim:
            Path(shim, "sitecustomize.py").write_text(SHIM)
            r = self.run_mask(home, shim, "conv-x", "--handle", "../evil/id")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(sorted(p.name for p in Path(home, ".codex-bridge", "mistral-conversations").iterdir()), [".._evil_id"])


if __name__ == "__main__":
    unittest.main()
