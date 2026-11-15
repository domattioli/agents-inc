# Routing ranking (CEO, 2026-09-06)

Working routing ranking, not a universal benchmark ranking. 1 = best fit for that task; lower-ranked models may still be preferable when cost, speed, or tool compatibility matters.

| Model | Hard reasoning | Complex coding | Agentic/tool use | Research & long context | Writing & analysis | Document extraction | Routine coding | Classification / summarization | Speed / cost |
|---|---|---|---|---|---|---|---|---|---|
| Claude Fable 5 | 1 | 1 | 2 | 1 | 1 | 1 | 4 | 4 | 8 |
| GPT-6 Astra | 2 | 2 | 1 | 2 | 4 | 3 | 5 | 5 | 7 |
| GPT-5.6 Sol | 3 | 3 | 3 | 4 | 5 | 5 | 1 | 3 | 6 |
| Claude Opus 5 | 4 | 4 | 4 | 3 | 2 | 4 | 3 | 4 | 5 |
| Claude Sonnet 5 | 5 | 5 | 6 | 5 | 3 | 2 | 2 | 2 | 3 |
| GPT-5.6 Terra | 6 | 6 | 5 | 6 | 6 | 6 | 2 | 1 | 2 |
| Claude Haiku 4.5 | 7 | 8 | 8 | 7 | 7 | 6 | 6 | 1 | 1 |
| GPT-5.6 Luna | 8 | 7 | 7 | 8 | 8 | 7 | 5 | 2 | 1 |

## Rungs

Renamed 2026-09-07 (operator ruling, D34): top rung Supervisor -> Executive. Orchestrator gained "Supervisor" as a synonym/invocation keyword for the same rung, same role — not a new rung, not a name swap with Orchestrator. Supervisor retired as synonym (D83): "supervisor" now names only the relation (the party that dispatched a delegate and verifies its return). <!-- terms: historical -->

| Rung | Default | Escalate to | Second opinion when |
|---|---|---|---|
| Executive | Fable 5 or Astra | the other frontier model | final decisions, conflicting results, high-risk actions |
| Orchestrator | Opus 5 or Sol | Fable 5 or Astra | task decomposition ambiguous, dependencies complex |
| Workhorse | Sonnet 5 or Terra | Opus 5 or Sol | coding, research, or synthesis has meaningful uncertainty |
| Grunt | Haiku 4.5 or Luna | the other cheap model | outputs anomalous or validation cheap |

## Scouting

Scouting is a mode, not a rung. Recon sent before committing real work goes to a free grunt when it is text-only, and to the Grunt rung (Haiku 4.5 or Luna) when it needs tools. Never to Workhorse or above. Definition and ledger treatment: CONTEXT.md (Scout, Scout node, Scout roster) and docs/DECISIONS.md D28.

## Routing rule

```text
if irreversible, high-risk, or strategically important:  Fable 5 <-> Astra
elif complex planning, coding, or multi-step delegation:  Opus 5 <-> Sol
elif normal research, coding, synthesis, or document work: Sonnet 5 <-> Terra
else:                                                      Haiku 4.5 <-> Luna
```

Second opinion: send the task to the paired model without showing the first answer. The supervisor compares both outputs afterward. Claude Code `/advisor` and the `@model` router do not satisfy this column: `/advisor` sees the first answer, and neither writes a ledger node (see CONTEXT.md, Advisor / @model).

Source: CEO message, 2026-09-06, citing openai.com positioning of Astra as a top-class model and GPT-5.6 as a family spanning capability and efficiency.
