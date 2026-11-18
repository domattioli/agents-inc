# Demo clip: run your AI like a company (v6)

`out/agents-inc-demo.mp4` (git-ignored; the tracked web copies are `docs/assets/demo.mp4`, `demo.gif` and `demo-poster.png`) is a 38-second advert, 1920x1080 at 30 fps, captions only. The scene is `scene.py`, scene class `CompanyV6`.

**Nothing on screen is run data.** The whole clip is an illustration of how agents-inc works, and the corner badge reads "Illustration". The scene reads one field from the recorded runs, `kind` in each `runs/*/run.json`. That is used only so the caught Worker and the reviewer get different provider rings, as in the real run the clip is modelled on.

**Beats:**
1. The company appears top-down. Each rung name shows a plain-words alias for a moment ("the CEO", "your chief of staff", "project manager", "second opinion", "does the work", "quick errands").
2. You and the Executive talk the request through.
3. The Orchestrator and the Executive confer: a "clarify" question and answer, then "analyze" (a plan is sent up and approved). Work then fans out to Workers and Grunts and comes back with script check marks. The reviewer, a sibling of the Orchestrator, sends one result back red; it returns green.
4. A second project grows under the same Executive.
5. Close: `agents-inc`, "Experimental", `github.com/domattioli/agents-inc`.

**Rules the picture follows** (`docs/governance/DELEGATION-MODEL.md`, `CONTEXT.md`, `docs/DECISIONS.md` D78):
- Review sits at the Orchestrator rung.
- Workers delegate only to Grunts; Grunts never delegate.
- Free models do only Grunt work, so the "free models" ring appears on Grunts only.
- The aliases are a transient marketing gloss. The permanent labels are rung names.

## The run this clip is modelled on

`draft.md`, `source_notes.md`, `check_structure.py`, `format.json`, `review.json`, `export_run.py` and `runs/` are a runnable example: a Codex Worker formats a draft, a script checks it, and a Claude reviewer catches two planted wording errors that the script cannot see. The steps to re-run it are below. The clip does not show its text.

## Files

- **Scene:** `scene.py`, scene class `CompanyV6`.
- **Avatars:** `make_avatars.py` cuts the round portraits in `assets/` from `docs/assets/logo-wide.png` (the crop boxes are in the script). The logo's sign text is not used.
- **Recorded runs:** `draft.md`, `source_notes.md`, `check_structure.py`, `format.json`, `review.json`, `export_run.py`, `runs/`.
  - `export_run.py` keeps only the fields the clip reads. It leaves out any field, or the whole report, that holds the home path or the user name, and it changes nothing else.

## Render

```bash
python3 demo/clip/make_avatars.py   # any Python with Pillow
manim -qh --media_dir demo/clip/media demo/clip/scene.py CompanyV6
cp demo/clip/media/videos/scene/1080p30/CompanyV6.mp4 demo/clip/out/agents-inc-demo.mp4
```

The fonts are Avenir Next and Menlo, which ship with macOS. `demo/clip/media/` and `demo/clip/out/` are git-ignored.

## Re-run the two recorded runs

Run from the repository root, one command per line, outside a sandbox. Each run uses a model subscription.

```bash
mkdir -p .scratch/demo-clip demo/clip/out
cp demo/clip/format.json demo/clip/review.json .scratch/demo-clip/
agents-inc doctor
agents-inc dispatch --slots .scratch/demo-clip/format.json --model terra
agents-inc dispatch --slots .scratch/demo-clip/review.json --model opus
python3 demo/clip/export_run.py .scratch/agents-inc-runs/<terra-run-id> demo/clip/runs/format
python3 demo/clip/export_run.py .scratch/agents-inc-runs/<opus-run-id> demo/clip/runs/review
cp demo/clip/out/formatted.md demo/clip/runs/format/formatted.md
```

- **The check:** `check_structure.py` checks structure, and that the wording equals the draft word for word. It never reads the source notes, so it cannot see a wrong fact copied from the draft. That is why the review exists.
- **The review run:** it has no gate, because dispatch passes the report path to a gate only for free-model runs. It ends `outcome=unverified reason=no-gates`.
