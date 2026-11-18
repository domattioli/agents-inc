# workerbee: runtime model discovery

Moved verbatim from `skills/workerbee/SKILL.md` (2026-11-16, token-efficiency order). Rules here bind as if in SKILL.md.

#### Step 1b: Discover models at runtime — don't hardcode, verify

Nicknames, slugs, and available effort levels can change per Codex-account
config. Before trusting this table on a machine or account you have not
just verified, run:

```bash
# What's the current default model + effort for this Codex account?
grep -E '^model' ~/.codex/config.toml
# → model = "gpt-6.2-astra"
# → model_reasoning_effort = "medium"

# Full roster this account can see, with per-model reasoning levels:
python3 -c "
import json
d = json.load(open('$HOME/.codex/models_cache.json'))
for m in d['models']:
    slug = m.get('slug') or m.get('id') or ''
    levels = [e['effort'] for e in m.get('supported_reasoning_levels', [])]
    print(slug, '|', m.get('display_name'), '| effort levels:', levels)
"

# Is a vendor CLI/credential actually present before you write a roster row for it?
which codex; which gemini; which mistral
ls ~/.codex-bridge/*-key 2>/dev/null   # gemini-key, openrouter-key present = wired
ls ~/.config/devstral 2>/dev/null       # mistral agent creds present = wired
```

Never document a vendor row from memory or from a prior session's table —
re-run this before dispatching to a nickname you have not already
confirmed exists on this account, this session.
