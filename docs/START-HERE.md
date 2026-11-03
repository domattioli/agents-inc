# Start here

## Install (0.5.0)

```bash
pip install agents-inc
agents-inc install
agents-inc doctor      # the first line prints READY when the install works
```

The skills and the schema ship inside the package, so `install` and `repair`
need no git checkout (D55). To install from a checkout instead, run
`python3 -m agents_inc.install.cli install --source "$PWD"` from it.
Restart Claude or Codex after installation. The recorded absolute launcher is
`~/.local/share/agents-inc/current/bin/agents-inc`.
Claude Code is the only required provider; Codex is optional (D50).
`agents-inc install` does not stop when the `codex` CLI is missing. It prints
one `NOTE:` line per skipped provider. `--without-codex` (install and repair)
skips Codex on purpose and silences that note.
Under `agents-inc run`, astra, sol and terra get Codex's shell tool, and luna
gets it only with `--tools` (D49, D49.1). Tool commands cannot read your home
directory, cannot reach the network, and write only with `--write`.
Under `agents-inc dispatch`, a Codex delegate can write to its working
directory by default, the same as a Claude subagent. The slot `CODEX_WRITE: no`
makes it read-only.
`agents-inc dispatch` can also run a broker that lets a Codex Lead ask for
Workers without seeing any credentials (D51). The installer does not manage the
HTTP bridge or any daemon.

### Requirements

- Python 3.11 or later. The test suite also runs on Python 3.14.
- Bash 3.2 or later. The scripts support macOS system Bash.
- Claude Code CLI, signed in through an Anthropic subscription.
- `jq`, used by the hook scripts and the `@alias` router.
- Optional: Codex CLI, signed in through a ChatGPT/OpenAI account. The Codex
  aliases (astra, sol, terra, luna) map to slugs that depend on your account;
  `~/.config/agents-inc/roster.json` overrides the pins in
  `agents_inc/routing.json`.
- Optional: Gemini, Mistral, or OpenRouter API keys. A missing optional key
  skips that provider. It does not block the system.

### Setup decision tree

```
Do you have Claude Code CLI installed + authenticated?
├─ NO → Install via https://claude.ai/code (Anthropic account required)
│       └─ After install, continue below at "Do you have Codex..."
├─ YES → Do you have Codex CLI installed + authenticated? (optional)
│        ├─ NO → Install via https://openai.com/codex, or skip Codex with --without-codex
│        └─ YES → Do you want to use free-tier providers (Gemini, Mistral, OpenRouter)?
│                 ├─ NO → Ready. Demo without keys, from a checkout:
│                 │       PYTHONPATH=. python3 tools/governance_demo.py --fake
│                 └─ YES → Configure each one (Enter skips it):
│                         ├─ python3 -m workerbees.keys gemini
│                         ├─ python3 -m workerbees.keys mistral
│                         └─ python3 -m workerbees.keys openrouter
```

- **Key storage:** each command opens the provider's key page and asks for a
  hidden paste. Keys go to `~/.config/workerbees/.env` with mode `0600`. The
  agent never receives the raw key.
- **Skipped keys:** a skipped key is not an error. It removes that provider
  from the pool. Optional providers get only Grunt-class `extract` and
  `summarize` work.
- **Skill dependencies:** [`skills.requirements.txt`](../skills.requirements.txt)
  pins the version and source of each skill, like `requirements.txt` for pip.
  From a checkout, `bash scripts/install_skills.sh` syncs and verifies them;
  `--dry-run` shows what would change.

### Your first dispatch

Tell the session what to do and which models to use, for example
"Fix the parser. opus, haiku." The higher model manages the lower one. The
session then runs `agents-inc dispatch`. Every dispatch prompt names its
reporting chain in a `REPORTING CHAIN` line; `agents-inc models chain
supervisor=opus` changes the default supervisor. Each launched dispatch also
writes one row to the ledger. Details: `HOW-IT-WORKS.md`, section
"Asking for work".

### Watching a delegate work (optional)

Install also adds a small Claude Code add-on, the agents-inc mod. It lets you
watch a delegate while it works. Start a relay subagent with
`subagent_type: "agents-inc:relay"`, give it a model and a slots file, and open
its transcript: short rows appear as the delegate reads, edits and runs
commands. The final answer is the same report you get without the mod.

- **Install:** `agents-inc install` and `agents-inc repair` add the mod when the
  `claude` command is on your PATH. Add `--no-mod` to skip it. If the step
  fails you get a warning and everything else still works.
- **Permission:** allow the tool `mcp__agents-inc__run` in your Claude Code
  permissions, or the relay asks each time.
- **Check:** `agents-inc doctor` prints the warning `MOD_NOT_INSTALLED` when the
  mod is missing. It still says `READY`.
- **Stop a run:** stop the relay in Claude Code. Or run
  `agents-inc dispatch --cancel <run dir>` from a terminal.
- **Manual install:** see `mods/agents-inc/README.md`.

- **Audience:** People who have not run the system before.
- **Style:** Plain language; the other docs are compressed for experienced readers.
- **Next reading:** Return to those docs after this page.

## What this is

- **Delegation system**
  - **Purpose:** Gets several AI models to do work cheaply without trusting any model blindly.
  - **Division of labor:** A capable model supervises while cheaper models handle narrow jobs such as reading a long document, extracting every date from files, or writing a first draft.
  - **Core problem:** Deciding whether returned work is correct.

## The two pieces

- **System**
  - **Plumbing:** `skills/codex-bridge/` sends requests to OpenAI, Google, or Mistral, retries temporary failures, stops on exhausted free requests, and records cost.
  - **Judgment:** `skills/workerbee/` contains no code. It defines model choice and work verification.
  - **Boundary:** Separate layers let you replace the plumbing while keeping the supervision lessons.

## The one rule

- **Independent checking**
  - **Failure mode:** An AI model can report what it meant to produce instead of what it produced.
  - **Evidence:** That happened three times in a row during one session on this machine, and each report looked convincing.
  - **Rule:** The thing that checks the work must not be the thing that did the work.
  - **Practice:** Write the check yourself or have the supervising model write it somewhere the worker cannot edit, then run it yourself.
  - **Reason:** A self-reported result is not evidence.

## What it costs

- **Billing**
  - **Anthropic subscription:** Covers Claude models.
  - **ChatGPT subscription:** Covers OpenAI models.
  - **API keys:** Google’s free tier, Mistral, and OpenRouter use pay-per-use access.
  - **Budget mode:** Shifts work from the first bill to the second and third, which can save money while increasing verification time.
  - **Constraint:** Use it when money limits the work, not when correctness limits it.
  - **Price rule:** Unknown price and free price are different facts.
  - **Evidence:** Treating an unknown price as free once inflated a savings figure by a factor of twenty-nine.

## If you are a lawyer

- **Confidentiality**
  - **Transmission:** Sending text to a cloud AI model sends that text to the company’s servers.
  - **Privilege:** Summarizing a privileged document still transmits the privileged document.
  - **Decision:** Decide what may leave the machine, write the rule as an absolute rule, and include it in every model instruction.
  - **Scope:** Client names, case facts, and active matter files require your decision and your bar’s decision.
- **Hard stops**
  - **Client communications:** Do not delegate anything filed, served, or sent to a client. You are the signatory.
  - **High-cost errors:** Do not delegate work where confident error is worse than delay.
- **Verification**
  - **Problem:** Law has no compiler, so fluent wrong prose is harder to catch than faulty code.
  - **Gate:** Define how you will know a category of work is wrong before delegating it.
  - **Test set:** Keep twenty documents you handled correctly, run every new delegation against them, and count misses.

## Actually running something

- **Prerequisite**
  - **Access:** You need the `codex` command-line tool logged into ChatGPT, a Google Gemini API key, or a Mistral API key.
  - **First job:** Put a key in place before using the simplest example.

```bash
skills/codex-bridge/scripts/agent.sh submit --backend gemini --wait "your question here"
```

`agent.sh list` shows past jobs. `agent.sh result <id>` reprints one.

- **Key handling**
  - **Location:** Keys live in a file.
  - **Prohibition:** Never type a key into a command or paste it into a model message.
  - **Exposure:** If a real key enters a chat window, treat it as compromised and replace it.

## When you are ready

- **Further reading**
  - **System:** `HOW-IT-WORKS.md` describes the whole system in compressed form.
  - **Extension:** `EXTENDING.md` covers new models, vendors, and domains, including a law-practice example.
  - **Discipline:** `../skills/workerbee/SKILL.md` contains the full supervision rules and their failure history.
  - **Style:** The documents use terse shorthand for experienced readers. That is intentional.
