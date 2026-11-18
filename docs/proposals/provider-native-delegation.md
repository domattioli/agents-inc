# Provider-native delegation

The host owns subagent creation, permissions, messaging, and cancellation. The
supervisor checks task authority, chooses an offered model, and verifies the
result. Governed dispatch stays available for authorized cross-provider and
non-interactive work. In Codex, use it only for authorized Claude integration
tests, with Haiku for a live test.

## Decisions from the native reviews

- **Sol, routing.** Resolve a named model from the active host. Preserve Claude's
  explicit enforce mode and its persona guard. An unavailable model leaves any
  mandatory review open. A denial ends that action. In either case, continue
  independent work. Record the model, identity and outcome when the host supplies
  them. Keep the verification verdict separate.
- **Sol, token use.** Start independent reviews with fresh context and a bounded
  brief. Reuse the same agent for related work and send the delta. Keep short
  sequential work local.
- **Astra, operator duty.** Put one short statement in root `AGENTS.md`. Preserve
  existing work and the supervisor's responsibility for missing grants. Let
  routine authorized work proceed. Resolve actual uncertainty and respect host
  permission decisions.

The [operator guide](../HOW-IT-WORKS.md#native-delegation) describes the ledger
coverage. Codex lifecycle events leave the task description and full usage
unknown. Claude foreground responses provide last-request usage when available.
A native background cancellation needs an explicit host signal to be recorded
as cancelled. A missing stop event supplies no such signal. Gemini routing is
conditional on the host's current tools, with no agents-inc lifecycle wiring.

## Measuring Codex token use

Run paired trials from the same starting state. Match the task, model, effort,
permissions and acceptance checks. Track elapsed time, acceptance, retries,
input tokens, cached input and output tokens for the whole task, including
retries. Compare fresh native and authorized governed runs only where both routes
can use the same model and grants. Separately compare fresh and reused native
agents on follow-up tasks.

If the host omits per-agent usage, use isolated session totals when available.
Prompt bytes can measure brief size. Report unknown token counts as unknown and
make no savings claim without measurements. Keep the guest adapter's resumed
thread behavior and the zero-incremental-spend limit.
