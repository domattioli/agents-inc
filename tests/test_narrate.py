import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from agents_inc import narrate

FIXTURE = Path(__file__).parent / "fixtures" / "narrate_transcript.jsonl"


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)


class FailingSummarizer:
    name = "luna"

    def __init__(self, paused=False):
        self.paused = paused

    def summarize(self, text):
        raise narrate.SummarizerError("boom", paused=self.paused)


class EchoSummarizer:
    name = "echo"

    def summarize(self, text):
        return "digest: " + text[:20]


def quiet(fn, *a, **k):
    with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
        return fn(*a, **k)


class ParseTests(unittest.TestCase):
    def test_only_assistant_text_blocks_are_collected(self):
        texts, offset = narrate.read_new_messages(FIXTURE, 0)
        self.assertEqual(len(texts), 2)
        self.assertEqual(texts[0], "I read the file.")  # tool_use block skipped
        self.assertNotIn("SECRET", " ".join(texts))  # tool_result record skipped
        self.assertEqual(offset, FIXTURE.stat().st_size)

    def test_user_record_and_bad_json_ignored(self):
        self.assertIsNone(narrate.assistant_text('{"type":"user","message":{"content":"hi"}}'))
        self.assertIsNone(narrate.assistant_text("not json"))

    def test_partial_last_line_waits(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.jsonl"
            p.write_text('{"type":"assistant","message":{"content":[{"type":"text","text":"half')
            self.assertEqual(narrate.read_new_messages(p, 0), ([], 0))

    def test_strip_markdown_and_code(self):
        raw = narrate.latest_message(FIXTURE)
        out = narrate.strip_markdown(raw)
        self.assertNotIn("hidden", out)
        self.assertNotIn("```", out)
        self.assertNotIn("**", out)
        self.assertNotIn("#", out)
        self.assertIn("I fixed the parser bug.", out)

    def test_find_transcript_picks_newest(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            proj = narrate.projects_dir(home)
            (proj / "a").mkdir(parents=True)
            (proj / "b").mkdir(parents=True)
            old, new = proj / "a" / "1.jsonl", proj / "b" / "2.jsonl"
            old.write_text("{}\n")
            new.write_text("{}\n")
            import os
            os.utime(old, (1, 1))
            self.assertEqual(narrate.find_transcript(home), new)


class GuardTests(unittest.TestCase):
    def test_classification_marker_skips_and_logs(self):
        speaker = FakeSpeaker()
        n = narrate.Narrator(EchoSummarizer(), speaker)
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertIsNone(n.handle("This is u//fouo material."))
        self.assertEqual(speaker.said, [])
        self.assertIn("skipped", err.getvalue())

    def test_luna_failure_falls_back_to_local_with_prefix(self):
        speaker = FakeSpeaker()
        n = narrate.Narrator(FailingSummarizer(), speaker)
        quiet(n.handle, "First para here.\n\nSecond para.")
        self.assertEqual(speaker.said, ["local. First para here."])

    def test_quota_pause_falls_back_too(self):
        n = narrate.Narrator(FailingSummarizer(paused=True), FakeSpeaker())
        self.assertTrue(quiet(n.digest, "Hello there.").startswith("local. "))

    def test_decide_only_filter(self):
        n = narrate.Narrator(EchoSummarizer(), FakeSpeaker(), decide_only=True)
        self.assertIsNone(n.digest("All done.\n\nNothing else."))
        self.assertIsNone(n.digest("Why?\n\nAll done."))  # question is not in the final paragraph
        self.assertIsNotNone(n.digest("Done.\n\nShip it?"))
        self.assertIsNotNone(n.digest("DECIDE: pick one.\n\nOk."))

    def test_local_summarizer_truncates(self):
        out = narrate.LocalSummarizer().summarize("x" * 500 + "\n\nsecond")
        self.assertEqual(len(out), narrate.LOCAL_LIMIT)

    def test_flag_file_gates_watcher(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            t = Path(d) / "t.jsonl"
            t.write_text("")
            speaker = FakeSpeaker()
            n = narrate.Narrator(EchoSummarizer(), speaker)
            line = '{"type":"assistant","message":{"content":[{"type":"text","text":"Hello"}]}}\n'
            ticks = []

            def sleep(_):
                ticks.append(1)
                if len(ticks) == 1:
                    t.write_text(line)  # flag off: consumed silently
                elif len(ticks) == 2:
                    narrate.set_flag(True, home)
                    with open(t, "a") as fh:
                        fh.write(line)
                else:
                    raise KeyboardInterrupt

            narrate.watch(n, t, home=home, sleep=sleep)
            self.assertEqual(len(speaker.said), 1)
            self.assertTrue(narrate.flag_path(home).is_relative_to(home))


class SpeakerTests(unittest.TestCase):
    def test_queue_speaks_in_order(self):
        spoken = []
        s = narrate.Speaker("Test", lambda voice, text: spoken.append((voice, text)))
        for i in range(5):
            s.say(f"m{i}")
        s.close()
        self.assertEqual(spoken, [("Test", f"m{i}") for i in range(5)])


class LunaTests(unittest.TestCase):
    def make(self, returncode=0, stdout="Two sentences."):
        calls = []

        def runner(argv, **kw):
            calls.append((argv, kw))
            return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")

        return narrate.LunaSummarizer("/work", launcher="/bin/agents-inc", runner=runner), calls

    def test_argv_and_stdin_prompt(self):
        s, calls = self.make()
        self.assertEqual(s.summarize("body text"), "Two sentences.")
        argv, kw = calls[0]
        self.assertEqual(argv, ["/bin/agents-inc", "run", "--model", "luna", "--no-tools", "--cwd", "/work"])
        self.assertIn(narrate.LUNA_PROMPT, kw["input"])  # `run` reads the prompt from stdin
        self.assertIn("body text", kw["input"])

    def test_exit_75_marks_paused(self):
        s, _ = self.make(returncode=75, stdout="")
        with self.assertRaises(narrate.SummarizerError) as cm:
            s.summarize("x")
        self.assertTrue(cm.exception.paused)

    def test_launch_error_raises_summarizer_error(self):
        def runner(argv, **kw):
            raise subprocess.TimeoutExpired(argv, 1)

        s = narrate.LunaSummarizer("/w", launcher="/x", runner=runner)
        with self.assertRaises(narrate.SummarizerError):
            s.summarize("x")


if __name__ == "__main__":
    unittest.main()
