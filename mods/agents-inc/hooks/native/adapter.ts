// Spec 038 contracts/step-adapter.md: what a provider supplies to the shared step loop (native/loop.ts).
// The loop owns prompt build, render, parse, correction, push, handback, abort, timeout, usage, snapshot calls.

export type AdapterKind = 'thread' | 'stateless'
// T021a: how the adapter is authorised. `cli-login` uses a provider CLI's own login (Codex); `key-store` is reserved for
// a later, opt-in API-key adapter (Q4). Any other value fails closed: the loop registers no type for the adapter.
export type AdapterAuth = 'cli-login' | 'key-store'
export const AUTHS: readonly string[] = ['cli-login', 'key-store']

export type NativeModel = { nickname: string; provider: string; slug: string }
export type Reply = { say: string; tools: { name: string; input: unknown }[] }
// One run: the reply (or why it was rejected), whether the run failed, and what the parent sees for a failure.
// `retry: false` marks a failure a fresh thread cannot cure; `asked` marks a run stopped for asking (exit 77).
export type Outcome = { reply: Reply | string | null; failed: boolean; fail?: string; retry?: boolean; asked?: boolean }

export interface Adapter {
  provider: 'codex' | 'gemini' | 'mistral' | 'openrouter'
  kind: AdapterKind // 'thread': the provider keeps the thread and reports running usage totals; 'stateless': neither
  auth: AdapterAuth
  nickname: string // the type is `agents-inc:<nickname>`; also the prefix of every failure text
  cli: readonly string[] // argv prefix of the status|begin|end verbs, e.g. ['agents-inc', 'luna']
  description(slug: string): string // the registered type's description
  // Prompt fragments: where the catalog tools live (after the first header line), the identity line naming the model,
  // the provider's own-tools rule (after the identity line), and the delta-header rule about provider tools.
  toolHome: string
  identity(slug: string): string
  ownTools: string
  deltaRule: string
  pushes: { refusal: string; unfinished: string; asked: string } // model-tuned nudges
  timeoutEnv: string // env var that overrides the step limit
  timeoutText(limitS: number): string
  // Spawn argv for one run; the prompt goes on stdin. `timeoutS` null: the runtime has no run timeout flag.
  // `session` and `agent` name the agent's run directory (FR-015 events.jsonl); a stateless adapter passes them on.
  argv(model: NativeModel, o: { thread: string; cwd: string; timeoutS: number | null; session?: string; agent?: string }): string[]
  // True when a run failed only because the installed runtime rejected the timeout flag: the loop runs again without it.
  rejectsTimeout(code: number | null, stderr: string): boolean
  // Exit-code mapping; null = generic failure (`<nickname> failed: run exited <code>: <stderr>`).
  classify(code: number | null, stderr: string, why: string, limitS: number): Outcome | null
}

// Fail closed on a value the type does not allow (adapters built from data in later slices).
export const authKnown = (a: { auth?: unknown }): boolean => typeof a.auth === 'string' && AUTHS.includes(a.auth)
