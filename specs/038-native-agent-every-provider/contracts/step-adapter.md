<!-- provenance: author=domattioli model=claude-opus-5-5 effort=medium date=2026-11-11 skill=speckit-pipeline repo=agents-inc session=cc99f334-8d7a-4ad1-8d91-84f345d12dfb -->
# Contract: step adapter

## TypeScript side (mod, `mods/agents-inc/hooks/native/`)

```ts
type AdapterKind = 'thread' | 'stateless'
interface Adapter {
  provider: 'codex' | 'gemini' | 'mistral' | 'openrouter'
  kind: AdapterKind
  identity(slug: string): string            // one prompt line naming the model
  pushes: { refusal: string; unfinished: string } // model-tuned nudges; defaults from loop
  argv(model: NativeModel, threadFile?: string): string[] // spawn argv; prompt goes on stdin
  classify(code: number | null, stderr: string): Outcome | null // exit-code mapping; null = generic failure
}
```

The loop owns: prompt build, render, parse, correction, push, handback, abort, timeout, usage, snapshot calls, events rows.

## CLI side (Python)

- `agents-inc native status --json` -> `{"models": [{"nickname", "provider", "slug", "offered", "reason"}]}`. Reads files only.
- `agents-inc native step --model <nick> [--thread FILE] --cwd DIR` reads the prompt on stdin, writes the reply text on stdout, progress on stderr as `agents-inc run: event|usage|record <json>` (same lines luna.ts parses today).
- Exit codes: 0 ok; 75 quota-paused; 69 provider host blocked; 3 model not offered / catalog missing; 2 usage or context over limit; other nonzero failure.
- `agents-inc native begin|end` = today's `luna begin|end`, with `--provider`.
- `agents-inc native on|off|allow`.

Keys: read in-process, sent in a header, never in argv, env or stdout/stderr.
