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
        self.assertTrue(data["permissionDecisionReason"].startswith(REASON))

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

    def _assert_allowed(self, command):
        self.assertEqual(hook.compound_deny(bash(command)), "")

    def test_quoted_marker_allowed(self):
        self._assert_allowed('git commit -m "agents-inc dispatch; x"')
        self._assert_allowed('git commit -m "fix agents-inc dispatch; tidy"')

    def test_quoted_redirect_arg_allowed(self):
        self._assert_allowed("agents-inc dispatch --slots s.json --message 'a > b'")

    def test_env_prefix_denied(self):
        self._assert_denied("AGENTS_INC_ALLOW_SANDBOXED=1 agents-inc dispatch --model haiku s.json")

    def test_double_quoted_subst_denied(self):
        self._assert_denied('agents-inc dispatch --message "$(cat x)" s.json')

    def test_single_quoted_subst_allowed(self):
        self._assert_allowed("agents-inc dispatch --message '$(x)' s.json")

    def test_unbalanced_quote_falls_back(self):
        self._assert_denied("agents-inc dispatch --message 'oops; s.json")

    def test_newline_separated_denied(self):
        self._assert_denied("ls\nagents-inc dispatch --model haiku s.json")

    def test_absolute_path_launcher_denied(self):
        self._assert_denied("/Users/x/.local/bin/agents-inc dispatch --model haiku s.json && ls")

    def test_echo_mention_allowed(self):
        self._assert_allowed("echo agents-inc dispatch")

    def test_hash_in_word_does_not_hide_chain(self):
        self._assert_denied("agents-inc dispatch --slots s.json --tag a#b && rm -rf x")

    def test_hash_comment_then_newline_command_denied(self):
        self._assert_denied("agents-inc dispatch s.json # note\nrm -rf x")

    def test_dispatch_in_double_quoted_subst_denied(self):
        self._assert_denied('echo "$(agents-inc dispatch s.json)"')

    def test_dispatch_in_backtick_subst_denied(self):
        self._assert_denied("echo `agents-inc dispatch s.json`")

    def test_dispatch_in_shell_c_denied(self):
        self._assert_denied('bash -c "agents-inc dispatch s.json"')
        self._assert_denied("sh -c 'agents-inc dispatch s.json'")

    def test_wrapper_words_denied(self):
        for wrapper in ("env", "exec", "command", "nohup", "time", "nice", "xargs"):
            self._assert_denied(f"{wrapper} agents-inc dispatch --slots s.json")

    def test_leading_backslash_denied(self):
        self._assert_denied("\\agents-inc dispatch s.json && ls")

    def test_echo_quoted_prose_still_allowed(self):
        self._assert_allowed('echo "run agents-inc dispatch later"')

    def test_equals_flag_with_quoted_semicolon_allowed(self):
        self._assert_allowed('agents-inc dispatch --message="a;b" --slots s.json')

    def test_reason_names_plain_form(self):
        data = json.loads(hook.compound_deny(bash("agents-inc dispatch s.json && ls")))["hookSpecificOutput"]
        reason = data["permissionDecisionReason"]
        self.assertTrue(reason.startswith(REASON))
        self.assertIn("Run it as: agents-inc dispatch --slots <file> --model <alias>", reason)
        self.assertIn("found: &&", reason)

    def test_brace_and_keyword_heads_denied(self):
        self._assert_denied("{ agents-inc dispatch s.json; printf done; }")
        self._assert_denied("if true; then agents-inc dispatch s.json; printf done; fi")

    def test_eval_and_quoted_launcher_shell_c_denied(self):
        self._assert_denied("eval 'agents-inc dispatch s.json; printf done'")
        self._assert_denied("bash -c \"'agents-inc' dispatch s.json; printf done\"")

    def test_launcher_expansion_denied(self):
        self._assert_denied('launcher=agents-inc; "$launcher" dispatch s.json; printf done')
        self._assert_denied("agents-${EMPTY-}inc dispatch s.json; printf done")
        self._assert_denied("$'agents-inc' dispatch s.json; printf done")
        self._assert_denied("agents-\\\ninc dispatch s.json; printf done")

    def test_quoted_launcher_in_substitution_denied(self):
        self._assert_denied("""printf '%s' "$('agents-inc' dispatch s.json; printf done)\"""")

    def test_premature_close_denied(self):
        self._assert_denied("""printf '%s' "$(printf ')'; agents-inc dispatch s.json)\"""")

    def test_alias_denied(self):
        self._assert_denied("shopt -s expand_aliases\nalias ai='agents-inc'\nai dispatch s.json; printf done")

    def test_hiding_shapes_allowed_without_agents_inc(self):
        self._assert_allowed("ls $HOME")
        self._assert_allowed("if true; then ls; fi")
        self._assert_allowed("eval \"$(ssh-agent)\"")
        self._assert_allowed("{ ls; }")

    def test_quoted_operator_argument_allowed(self):
        self._assert_allowed("agents-inc dispatch s.json --message '&&'")
        self._assert_allowed("agents-inc dispatch s.json --message '&''&'")
        self._assert_allowed('agents-inc dispatch s.json --message "&&"')
        self._assert_allowed("agents-inc dispatch s.json --message=x'&&'")

    def test_quoted_operator_does_not_hide_real_one(self):
        self._assert_denied("agents-inc dispatch s.json --message '&&' && ls")

    def test_quoted_heredoc_body_allowed(self):
        self._assert_allowed("cat <<'EOF'\nagents-inc dispatch s.json\nEOF")
        self._assert_allowed("cat <<'EOF'\nagents-inc dispatch s.json && ls; echo $(x)\n\nEOF")
        self._assert_allowed("cat <<-EOF\n\tagents-inc dispatch s.json; ls\n\tEOF")

    def test_heredoc_then_real_dispatch_denied(self):
        self._assert_denied("cat <<'EOF'\nprose\nEOF\nagents-inc dispatch s.json")

    def test_unquoted_heredoc_substitution_denied(self):
        self._assert_denied("cat <<EOF\n$(agents-inc dispatch s.json)\nEOF")

    def test_quoted_prose_in_substitution_allowed(self):
        self._assert_allowed("""printf '%s' "$(printf '%s' 'agents-inc dispatch s.json')\"""")

    def test_comment_substitution_allowed(self):
        self._assert_allowed("printf done # $(agents-inc dispatch s.json)")

    def test_wrapper_running_other_command_allowed(self):
        self._assert_allowed("env printf '%s' agents-inc dispatch")
        self._assert_allowed("env -i FOO=1 printf agents-inc dispatch")
        self._assert_denied("env -u X FOO=1 agents-inc dispatch s.json")

    def test_quoted_assignment_is_command_name(self):
        self._assert_allowed("'X=1' agents-inc dispatch s.json")

    def test_quoted_paren_in_substitution_is_data(self):
        self._assert_allowed("""printf '%s' "$(printf ')' )\"""")
        self._assert_denied("""printf '%s' "$(printf ')'; agents-inc dispatch s.json)\"""")

    def test_reason_names_element_for_premature_close(self):
        data = json.loads(hook.compound_deny(bash("""printf '%s' "$(printf ')'; agents-inc dispatch s.json)\"""")))
        self.assertIn("found: command substitution", data["hookSpecificOutput"]["permissionDecisionReason"])

    def test_exception_fails_open(self):
        with mock.patch.object(hook, "_tool_input", side_effect=RuntimeError("boom")):
            self.assertEqual(hook.compound_deny(bash("cd x && agents-inc dispatch s")), "")


if __name__ == "__main__":
    unittest.main()
