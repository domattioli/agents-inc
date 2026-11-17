# Spec 038 baseline: luna stress on the shared loop

Harness: `docker/luna_stress.sh` on the macOS host (live Claude Code and Codex, `gpt-6-luna`), 10 runs per scenario. Bar: 10 of 10 per scenario (grill ruling 2026-11-11).

| Date | Build | tools | par | steps5 | follow | Log |
|---|---|---|---|---|---|---|
| 2026-11-11 | a8800e6 (slice 1) | 8/10 | 10/10 | 9/10 | 10/10 | `.scratch/luna-stress2/` |
| 2026-11-11 | 233a990 | 10/10 | 10/10 | 7/10 | 10/10 | `.scratch/luna-stress3/` |
| 2026-11-11 | e352c02 | not rerun | not rerun | 10/10 | not rerun | `.scratch/luna-stress4/` |
| 2026-11-11 | 7e21b41 (slices 1 to 4) | 10/10 | 10/10 | 9/10 | 10/10 | `.scratch/luna-stress5/` |
| 2026-11-11 | 899cc64 | 10/10 | 10/10 | 10/10 | 10/10 | `.scratch/luna-stress6/` |

Failure causes and fixes:

- a8800e6: reply left in commentary messages with an empty final message (tools); hand-back that skipped the named tools (tools, steps5). Fixed in 233a990.
- 233a990, steps5 runs 7, 9, 10: luna handed back before all five commands ran. Two runs reported counts no tool produced (`E=2`; `C=208 D=64 E=127`); one said the results "have not been provided". Fixed in e352c02: a hand-back whose `KEY=<number>` values appear in no tool result gets one push; the early-stop pattern covers the run 9 wording.
- 7e21b41, steps5 run 5: luna ran one of five commands, then handed back `A=173` and said the other results "were not included in the messages available to me; their counts remain unverified". No push fired: the early-stop check skips any reply that carries a tool call, and a hand-back always carries one; the ungrounded-value check flags only invented numbers. Fix in 4e85d93 (was eeec613; passed 10/10 in the 899cc64 run): a hand-back that admits missing results gets one push. In that run the parent launched the agent in the background; the steps5 prompt did not ask for foreground, unlike par.

Open: a full four-scenario run on the final release build. The e352c02 run covers steps5 only; the other three passed 10/10 on 233a990 and their code paths changed after that (new push branch, chat-only and write-directory checks in the loop).

Live tool probe (T029), `models probe all` from the slice 3 source (3d4206d), 2026-11-11, two runs about 15 minutes apart, same result both times:

| Nickname | Result | Reason |
|---|---|---|
| gemini-flash | unavailable | Gemini answered HTTP 503, "This model is currently experiencing high demand". The key was found. Tool use is not yet measured for this model. |
| codestral, ministral | pass | reply named Read |
| dots-note, nemotron-lightning, nemotron-ultra, nemotron-nano | pass | reply named Read |
| gemma-26b, gemma-31b | unavailable | OpenRouter answered HTTP 404, "0 endpoints ... matching your guardrail restrictions and data policy". An account setting on the operator's OpenRouter account excludes these endpoints. |

On e352c02 the same command answered `WB_NATIVE_KEY_MISSING` (lookup read only `~/.config/workerbees/.env`; fixed in fcdcccf). Before 3d4206d a 503 or 404 was stored as `fail`, which offered the model as chat only; it is now `unavailable` and not offered.

Third run, 2026-11-11 evening, build 0423e35: `gemini-flash probe: unavailable (WB_NATIVE_TIMEOUT: no reply from generativelanguage.googleapis.com within 60 s)`.

Open: rerun `agents-inc models probe gemini-flash` when Gemini answers. Tool use for this model is still unmeasured.
