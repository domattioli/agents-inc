"""Review 042 fixes 2, hook screen: shell heredocs, split names on the error path, ANSI-C comments, interpreter -c code."""
import json
import unittest

from agents_inc.install import hook

L = "agents-inc dispatch --slots s.json --model terra"


def verdict(command: str) -> str:
    out = hook.compound_deny({"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": command}})
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"


class Fixes(unittest.TestCase):
    def check(self, command, want):
        self.assertEqual(verdict(command), want, command[:120])

    def test_g1_shell_heredoc_denied(self):
        for sh in ("sh", "bash", "zsh", "bash -e", "sh -s", "bash -"):
            self.check(f"{sh} <<'EOF'\n{L}\nEOF", "deny")
        self.check(f"bash <<EOF\n{L}\nEOF", "deny")
        self.check(f"sh <<-EOF\n\t{L}\n\tEOF", "deny")

    def test_g1_data_heredocs_allowed(self):
        self.check(f"cat <<'EOF'\n{L}\nEOF", "deny")  # minimal allowlist ruling 2026-11-16
        self.check(f"tee notes.txt <<'EOF'\n{L}\nEOF", "deny")  # minimal allowlist ruling 2026-11-16
        self.check("bash <<'EOF'\nls\nEOF", "allow")

    def test_g7_split_names_on_parser_error(self):
        deep = "echo " + "$(" * 1100
        tail = ")" * 1100
        self.check(deep + "ag'en'ts-inc dispatch --slots s.json --model terra" + tail, "deny")
        self.check(deep + "agents\\-inc dispatch --slots s.json --model terra" + tail, "deny")
        self.check(deep + "ls" + tail, "allow")

    def test_g10_ansi_comment_allowed(self):
        self.check("echo $'ok' # agents-inc dispatch", "allow")
        self.check(f"{L} $'x'", "deny")

    def test_g16_interpreter_inline_code(self):
        for cmd in ("python3 -c \"import os; os.popen('agents-inc dispatch x')\"",
                    "node -e \"require('child_process').execSync('agents-inc dispatch x')\"",
                    "node --eval \"x('agents-inc dispatch x')\"",
                    "perl -e 'system(\"agents-inc dispatch x\")'",
                    "ruby -e 'system(\"agents-inc dispatch x\")'",
                    "php -r 'system(\"agents-inc dispatch x\");'",
                    "osascript -e 'do shell script \"agents-inc dispatch x\"'",
                    "python3 -c \"import os; os.popen('ag'+'x')\" ; python3 -c \"os.system('agents\\-inc dispatch')\""):
            self.check(cmd, "deny")

    def test_g16_not_screened(self):
        self.check("python3 script.py", "allow")
        self.check("node app.js", "allow")
        self.check('node -e "console.log(1)"', "allow")

    def test_g18_here_string_into_shell(self):
        self.check("bash -s <<< 'agents-inc dispatch x'", "deny")
        self.check('sh <<< "agents-inc dispatch x"', "deny")
        self.check("bash <<< 'ls'", "allow")
        self.check("cat <<< 'agents-inc dispatch x'", "deny")  # minimal allowlist ruling 2026-11-16

    def test_g19_pipe_into_shell(self):
        self.check("echo 'agents-inc dispatch x' | sh", "deny")
        self.check("printf 'ag\\ents-inc dispatch x' | bash -s", "deny")
        self.check("echo 'agents-inc dispatch x' | xargs -I{} sh -c '{}'", "deny")
        self.check("echo 'ls' | sh", "allow")
        self.check("echo agents-inc | cat", "allow")
        self.check("agents-inc ledger | head", "allow")

    def test_allowlist_denied(self):
        for cmd in ("perl -e'system(\"agents-inc dispatch x\")'",
                    "python3 -c\"import os; os.system('agents-inc dispatch x')\"",
                    "cat <<'EOF' | sh\nagents-inc dispatch x\nEOF",
                    "bash < <(printf '%s\\n' 'agents-inc dispatch x')",
                    "printf '%s\\n' 'agents-inc dispatch x' | sh -s -- arg",
                    "printf '%s\\n' 'agents-inc dispatch x' | env xargs -I{} sh -c '{}'",
                    "echo agents-inc dispatch; printf true | sh",
                    "python3 -c \"print('agents-inc dispatch')\"",
                    "find . -name x -exec agents-inc dispatch {} \\;", "timeout 5 agents-inc dispatch x",
                    "FOO=1 agents-inc dispatch --slots a.json --model sol",
                    "time agents-inc dispatch --slots a.json --model sol",
                    "bash -c 'echo \"#\"; agents-inc dispatch x'", "eval 'echo \"#\"; agents-inc dispatch x'",
                    "if X=1 agents-inc dispatch x; then true; fi",
                    "for x in 1; do X=1 agents-inc dispatch x; done",
                    "env -S 'agents-inc dispatch x'", "env --split-string='agents-inc dispatch x'",
                    "fish -c 'agents-inc dispatch x'", "busybox sh -c 'agents-inc dispatch x'",
                    "Rscript -e \"system('agents-inc dispatch x')\"", "builtin eval 'agents-inc dispatch x'",
                    "trap 'agents-inc dispatch x' EXIT; true",
                    "coproc agents-inc dispatch --slots s.json --model terra",
                    "function f { agents-inc dispatch --slots s.json --model terra; }; f",
                    "rg 'agents-inc dispatch' tests; python3 -m unittest tests.test_x",
                    'echo $(bash -c "echo agents-inc dispatch")',
                    "eval \"echo 'agents-inc dispatch'\"", "bash -c \"grep 'agents-inc dispatch' log.txt\"",
                    "echo 'agents-inc dispatch x' | bash -c 'cat'",
                    "echo sh <<'EOF'\nagents-inc dispatch x\nEOF",
                    "git -c alias.x='!agents-inc dispatch x' x",
                    "git bisect run agents-inc dispatch x", "grep x <<< 'agents-inc dispatch x'",
                    "rg 'agents-inc dispatch' tests", "git log --grep='agents-inc dispatch'",
                    "cat <<'EOF'\nagents-inc dispatch notes\nEOF", "cat sh <<'EOF'\nagents-inc dispatch x\nEOF"):
            self.check(cmd, "deny")

    def test_control_keywords(self):
        for cmd in ("for w in agents-inc dispatch; do echo \"$w\"; done",
                    "if grep -q 'agents-inc dispatch' notes.md; then echo yes; fi",
                    "for x in 1; do X=1 agents-inc dispatch x; done", "if X=1 agents-inc dispatch x; then true; fi",
                    "for w in 'agents-inc dispatch x'; do $w; done", "while true; do bash -c 'agents-inc dispatch x'; done",
                    "'for' x in agents-inc dispatch; do true; done",
                    "if true; then for x in a; do echo agents-inc dispatch; done; fi"):
            self.check(cmd, "deny")

    def test_minimal_allowlist_probes(self):
        for cmd in ("git -calias.x='!agents-inc dispatch x' x", "git commit -m 'agents-inc dispatch'",
                    "rg --pre=agents-inc x file; echo agents-inc dispatch",
                    "sort -S 1b --compress-program='agents-inc dispatch' large.txt",
                    "less +'!agents-inc dispatch' file",
                    "printf -v 'x[$(agents-inc dispatch >&2)0]' %s x",
                    "test -v 'BASH_VERSINFO[$(agents-inc dispatch >&2)0]'",
                    "python3 -c \"import os; os.system(['agents-inc dispatch'][0])\"",
                    "bash -c 'ag\\\nents-inc dispatch x'", "eval 'ag\\\nents-inc dispatch x'",
                    "python3 -c pass >'agents-inc dispatch'", "echo agents-inc dispatch > run.sh",
                    "'grep' x; agents-inc dispatch y", "echo agents-inc dispatch\r; ls",
                    "bash <<'EOF'\ntrue # agents-inc dispatch\nEOF"):
            self.check(cmd, "deny")

    def test_allowlist_allowed(self):
        for cmd in ("agents-inc dispatch --slots a.json --model sol",
                    "grep -n 'agents-inc dispatch' docs/x.md | head", 'grep -rn "agents-inc run" skills | wc -l',
                    "cat notes.md; echo agents-inc dispatch", 'echo "run agents-inc dispatch alone"',
                    "echo $'ok' # agents-inc dispatch",
                    "cd /Users/x/Projects/agents-inc && python3 -m unittest tests.test_x",
                    "python3 -c \"print('notagents-inc dispatch')\"", "python3 -c \"print('agents-inc')\"",
                    "bash <<'EOF'\n# agents-inc dispatch\ntrue\nEOF", 'node -e "console.log(1)"',
                    "agents-inc ledger | head", "git status"):
            self.check(cmd, "allow")

    def test_regressions(self):
        self.check("agents-inc dispatch --slots a.json --model sol", "allow")
        self.check('echo "see agents-inc docs"', "allow")
        self.check("# agents-inc note\nls", "allow")
        self.check("ls && agents-inc dispatch --slots a.json --model sol", "deny")
        self.check('bash -c "agents-inc dispatch x"', "deny")
        self.check("git status", "allow")


if __name__ == "__main__":
    unittest.main()
