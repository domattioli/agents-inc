"""Spec 045 FR-009 (#87 item 2, #155 n): a free model gets no web tools, so a prompt that promises web search or fetch to
it is refused before launch. Claude and Codex rungs never reach this check. A false refusal is worse than a miss."""
import unittest

from agents_inc.install import dispatch, free_launch, rules

ROUTING = {"optional_allowed_tasks": ["extract", "summarize"]}


def check(task, **extra):
    slots = {"TASK_KIND": "summarize", "CLASSIFICATION": "public (x)", "TASK": task, **extra}
    return free_launch.pre_checks(slots, None, ROUTING)


class WebPromiseTest(unittest.TestCase):
    def test_promises_are_refused_with_a_fix(self):
        for task in ("Search the web for the release date.", "Use WebFetch on the changelog.",
                     "Fetch https://example.org/notes and summarize it.", "Do a web search for prior art.",
                     "Browse the web and summarize what you find."):
            with self.subTest(task=task):
                r = check(task)
                self.assertEqual(r, "refused-web-promise")
                self.assertIn("INPUTS", r.detail)

    def test_promise_in_another_slot_is_refused(self):
        self.assertEqual(check("Summarize the file.", CONSTRAINTS="You may search the web."), "refused-web-promise")

    def test_negatives_are_never_refused(self):
        for task in ("Summarize the webhook handler in hooks/x.py.", "Summarize docs/website/index.md.",
                     "WebFetch is not available; summarize the inlined text.", "You have no web access; use INPUTS.",
                     "Do not search the web.", "Summarize the paper (source: https://example.org/paper.pdf).",
                     "Extract the URLs cited in the text."):
            with self.subTest(task=task):
                self.assertIsNone(check(task))

    def test_negation_elsewhere_in_the_sentence_does_not_cancel(self):  # 045 review F3b
        for task in ("Search the web for prices and do not guess.", "Use WebSearch, no guessing."):
            with self.subTest(task=task):
                self.assertEqual(check(task), "refused-web-promise")

    def test_inlined_text_in_inputs_is_not_checked(self):  # 045 review F3a: the fix line itself says to inline in INPUTS
        self.assertIsNone(check("Summarize the inlined page.", INPUTS="The page said: search the web for cheaper flights."))

    def test_rule_is_registered(self):
        self.assertIn("web-promise", rules.RULES)

    def test_claude_and_codex_routes_do_not_call_pre_checks(self):
        self.assertNotEqual(dispatch._kind("sonnet"), "free")
        self.assertNotEqual(dispatch._kind("terra"), "free")


if __name__ == "__main__":
    unittest.main()
