"""F2: deny agents-inc dispatch wrapped in a compound Bash command; fail open on errors."""
import contextlib, io, json, os, tempfile, unittest
from pathlib import Path
from unittest import mock

from agents_inc.install import hook
from agents_inc.install.paths import InstallPaths

REASON = ("agents-inc must be the whole Bash call. Write the slots file in one call, dispatch in the next. "
          "Never set dangerouslyDisableSandbox.")


def bash(command):
    return {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": command}}


class CompoundDispatchTest(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"AGENTS_INC_AGENT_GATE": "advisory"}); env.start(); self.addCleanup(env.stop)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.paths = InstallPaths.for_home(Path(self.tmp.name))

    def _run(self, payload):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            hook.run(self.paths, "agent-nudge", "claude", stdin=io.StringIO(json.dumps(payload)))
        return out.getvalue()

    def _assert_denied(self, command):
        data = json.loads(self._run(bash(command)))["hookSpecificOutput"]
        self.assertEqual(data["permissionDecision"], "deny")
        self.assertEqual(data["permissionDecisionReason"], REASON)

    def test_plain_dispatch_allowed(self):
        out = self._run(bash("agents-inc dispatch --model haiku slots.json"))
        self.assertNotIn("deny", out)

    def test_cd_and_dispatch_denied(self):
        self._assert_denied("cd /x && agents-inc dispatch --model haiku slots.json")

    def test_heredoc_then_dispatch_denied(self):
        self._assert_denied("cat > s.json <<EOF\n{}\nEOF\nagents-inc dispatch --model haiku s.json")

    def test_pipe_denied(self):
        self._assert_denied("agents-inc dispatch --model haiku s.json | tail -5")

    def test_run_and_luna_denied(self):
        self._assert_denied("agents-inc run s.json; echo done")
        self._assert_denied("agents-inc luna x > out.txt")

    def test_unrelated_compound_allowed(self):
        self.assertEqual(hook.compound_deny(bash("cd /x && ls | tail")), "")

    def test_exception_fails_open(self):
        with mock.patch.object(hook, "_tool_input", side_effect=RuntimeError("boom")):
            self.assertEqual(hook.compound_deny(bash("cd x && agents-inc dispatch s")), "")


if __name__ == "__main__":
    unittest.main()
