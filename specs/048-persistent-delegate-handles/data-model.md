# Data Model: 048

`handles.json` (per session): `{ "version": 1, "handles": { "<id>": Handle } }`

Handle: `id` string; `provider`; `nickname` (the binding, with provider); `slug` string|null (from the first completed step's `acc.slug`, informational); `thread` string (path or provider ref); `cwd`; `charsSent` int; `seen` int (messages seen); `ceiling` int chars (800000 for every guest); `state` `live|retired`; `restarts` int; `lastRestartReason` `compaction|failed-step|refusal|thread-missing|null`; `history` string[] (old thread refs); `fingerprint` 8 hex (FNV-1a 32-bit over header + system + catalog) plus `fingerprintLen` int, `fingerprintChanged` bool; `threadTotal` last per-thread total (from `threadTotals`, loop.ts:746); `n` int (thread suffix); `used` bool.

Rules: `charsSent` resets to 0 on every `st.n` bump; a stateless handle sets it to the last prompt length. A step on a `retired` handle is refused. `saveHandles` re-reads the file and merges; the file's state wins over memory for `state`.

Transitions: `live -> retired` (retire command). Retired is terminal. There is no `failed` state.
