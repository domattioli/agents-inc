# Releasing agents_Inc

This runbook covers release 0.5.0: a GitHub tag and release, a Zenodo archive, and the PyPI upload of the `agents-inc` package (import name `agents_inc`). 0.2.0 was the first PyPI upload; 0.3.0 is the first release that installs from pip alone, with no `--source` checkout. Pushing a tag that starts with `v` runs `.github/workflows/release.yml`, which tests, builds, publishes to PyPI, and then creates the GitHub release. The workflow then deposits the release on Zenodo under the concept DOI with the `ZENODO_TOKEN` repository secret (step 8 below).

## Decisions

### What a pip install gives you

- The wheel ships `agents_inc`, `workerbees`, every `*.json` file under `agents_inc/`, and, from 0.3.0, the skill and doc files the installer needs.
- `setuptools` maps `agents_inc._skills` to `skills/` and `agents_inc._docs` to `docs/governance/`. Only `skills/workerbee`, `skills/codex-bridge` (without their `tests/`), and `SCHEMA-3NF.md` are packaged.
- `agents_inc/datafiles.py` finds these files. In a checkout it uses the checkout. In a pip install it reads the packaged copy.
- `agents-inc install` and `agents-inc repair` work without `--source`. `doctor` then compares the installed hook with the packaged one.

What `datafiles` resolves:

- the schema doc, `docs/governance/SCHEMA-3NF.md` (`agents_inc/schema.py`)
- the OpenRouter wrapper, `skills/codex-bridge/scripts/oask.sh` (`agents_inc/doctor.py`)
- the prompt scripts, `skills/workerbee/scripts/` (`agents_inc/install/dispatch.py`)
- the install bundle sources (`agents_inc/install/cli.py`)

Two items still need a checkout:

- `agents-inc models bump` (`agents_inc/install/models_cmd.py`) rewrites `routing.json` and `models.json` beside the package. Run it from a checkout only.
- The bench (`agents_inc/bench.py`) needs the top-level `fixtures/` directory, which is not in the wheel.

D55 in `docs/DECISIONS.md` records this.

### License identifiers

The `LICENSE` file is the PolyForm Small Business License 1.0.0, unmodified, followed by a licensor-added term that forbids AI and machine-learning training use. The combined text is therefore not the plain SPDX license, and each file says so in the form it supports:

| File | Value | Why |
|---|---|---|
| `pyproject.toml` | `license = "LicenseRef-PolyForm-Small-Business-1.0.0-NoAI-Training"` | PEP 639 needs an SPDX expression. A `LicenseRef-` id marks a custom license, and the plain `PolyForm-Small-Business-1.0.0` id would misstate the terms. No license classifier is used, because PEP 639 replaces them and none fits. |
| `pyproject.toml` | `license-files = ["LICENSE"]` | The wheel carries the full text under `dist-info/licenses/`. |
| `CITATION.cff` | `license: PolyForm-Small-Business-1.0.0` plus `license-url` to `LICENSE` | The CFF schema accepts only SPDX ids. The URL points readers to the full terms, including the added term. |
| `.zenodo.json` | no `license` field; a `notes` field names the added term | No network access was available while preparing this release, so the Zenodo license id for PolyForm Small Business 1.0.0 could not be checked in the Zenodo documentation. Before tagging, check https://help.zenodo.org and https://developers.zenodo.org. Add a `license` field only if a documented id exists. |

### DOI handling

- `10.5281/zenodo.22670100` is the concept DOI ("Cite all versions"). The operator confirmed it on 2026-10-07 from Zenodo record 23092581, the v0.1.0 version record.
- Every release keeps that DOI in `CITATION.cff` and the README badge. Each release is a new version under that concept, with its own version DOI. Version DOIs never go in the citation.
- `.zenodo.json` carries no `doi` or concept field, because one would file the release outside the concept record.
- `tests/test_release_metadata.py` enforces all three rules. The release workflow runs the suite before it builds, so a changed DOI stops the release.

## Operator steps (before the tag)

1. Keep the Zenodo GitHub integration switch for `domattioli/agents_Inc` off. See the stray record note below.
2. On PyPI, create a pending trusted publisher with these values:
   - Project name: `agents-inc`
   - Owner: `domattioli`
   - Repository: `agents_Inc`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. In the GitHub repository settings, create an environment named `pypi`. Adding a required reviewer gives one manual approval before each upload.
4. Fill every `TODO-operator` in `CITATION.cff` and `.zenodo.json`. The ORCID in `CITATION.cff` must be a full URL, for example `https://orcid.org/0000-0000-0000-0000`. The release workflow refuses to build while any `TODO-operator` remains. Done for 0.2.0 on 2026-10-07 (ORCID 0000-0002-7327-6337).

## CoS steps (cutting the release)

1. Pre-tag gate. Both commands must pass:
   - `grep -c TODO-operator CITATION.cff .zenodo.json` prints 0 for both files.
   - `python3 -m unittest discover -s tests -p 'test_*.py'` ends with `OK`.
2. Check that `CHANGELOG.md` has a dated `[0.5.0]` section and that `agents_inc.__version__` is `0.5.0`.
3. Merge `development` into `main` by pull request.
4. On `main`, create the tag: `git tag -a v0.5.0 -m "agents_Inc 0.5.0"`.
5. Push the tag: `git push origin v0.5.0`.
6. Watch the `release` workflow in the Actions tab. The `publish` job waits for the `pypi` environment approval if a reviewer was set.
7. Confirm that https://pypi.org/project/agents-inc/0.5.0/ exists and that the GitHub release lists the wheel and the sdist.
8. Zenodo. The workflow's `zenodo-concept` job runs `tools/zenodo_deposit.py`: it publishes the built wheel and sdist as a new version of the newest record under the concept, with metadata from `.zenodo.json` at the tag, then `tools/check_zenodo_concept.py` confirms the record. It needs the repository secret `ZENODO_TOKEN` (a Zenodo personal access token with `deposit:write` and `deposit:actions`; Zenodo account settings, Applications). Without the secret the job goes red and the deposit falls back to hand: from a DomI checkout, `python3 skills/zenodo-publish/scripts/zenodo_publish.py --new-version-of <latest record id> --draft`, then review and publish the draft, then rerun the job with `gh run rerun <id> --failed`. Description edits made after the tag happen in the Zenodo editor; the next release carries them in `.zenodo.json`.
9. Confirm that the `README.md` DOI badge still shows the concept DOI `10.5281/zenodo.22670100`. Version DOIs never go in the README.

## Stray Zenodo record (0.3.1)

On 2026-10-10 the Zenodo GitHub integration archived v0.3.1 as record 23288172 under a new concept, `10.5281/zenodo.23286662`, instead of `10.5281/zenodo.22670100`.

- Cite `10.5281/zenodo.22670100` only.
- Fix: the owner deletes record 23288172 from its Zenodo page (owners may delete a record within 30 days of publishing; after that only Zenodo support can). Then deposit 0.3.1 under 22670100 with `--new-version-of 23286808 --draft` and publish the draft.
- The integration switch stays off, so it cannot start another concept.

## Rollback

- PyPI: yank the release on pypi.org. Never delete it to reuse the number. PyPI never accepts the same version twice, so fix forward with 0.3.2.
- GitHub: delete the release with `gh release delete v0.3.1`, then delete the tag with `git push origin :refs/tags/v0.3.1` and `git tag -d v0.3.1`.
- Zenodo: the owner may delete a record within 30 days of publishing; after that only Zenodo support can.

## README EDIT PLAN

Applied in the 0.3.0 docs pass, which rewrote `README.md` to 150 lines or fewer. Kept as a record; line numbers come from commit ed35b0b and no longer match. Item 1 and item 7 predate D55: from 0.3.0, `agents-inc install` needs no `--source` checkout.

1. Install from PyPI. `README.md` line 427, under "### Install and configure providers".
   - Current: `Run the project from the repository root. Its Python code uses the standard library. No Python package-install step exists.`
   - Proposed: `Install the command and library with pip install agents-inc, or run it without installing with uvx agents-inc doctor. The package uses only the standard library. agents-inc install --source <checkout> still needs a git checkout, because the installer copies skills/ from it. To work on the project itself, run it from the repository root.`

2. PyPI and license badges. `README.md` line 14, after the DOI badge.
   - Current: `[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22670100.svg)](https://doi.org/10.5281/zenodo.22670100)`
   - Proposed: keep that line, then add:
     - `[![PyPI](https://img.shields.io/pypi/v/agents-inc)](https://pypi.org/project/agents-inc/)`
     - `[![License: PolyForm Small Business 1.0.0 + no AI training](https://img.shields.io/badge/license-PolyForm%20Small%20Business%201.0.0%20%2B%20no%20AI%20training-lightgrey)](LICENSE)`

3. DOI badge. `README.md` line 14.
   - Current: the DOI badge with `10.5281/zenodo.22670100`.
   - Proposed: once Zenodo confirms it, use the concept DOI in both the badge image and the link, `[![DOI](https://zenodo.org/badge/DOI/<concept DOI>.svg)](https://doi.org/<concept DOI>)`. Do not change the line if `10.5281/zenodo.22670100` is already the concept DOI.

4. Version line. `README.md` line 312, under "## 5. Project status".
   - Current: `**Pre-MVP and under active development.** The build plan and cut line live in [docs/PLAN-MVP.md](docs/PLAN-MVP.md).`
   - Proposed: `**Version 0.3.0. Pre-MVP and under active development.** The build plan and cut line live in [docs/PLAN-MVP.md](docs/PLAN-MVP.md). Changes per release are in [CHANGELOG.md](CHANGELOG.md).`

5. License section. `README.md` line 547.
   - Current: `No LICENSE file exists yet.`
   - Proposed: a `### License` heading, then: `agents_Inc is licensed under the PolyForm Small Business License 1.0.0 with one licensor-added term that forbids using the software for AI or machine-learning training. The full terms are in [LICENSE](LICENSE). Small businesses, individuals, and noncommercial users may use it under those terms. For commercial use or AI training rights, contact the address in LICENSE.`

6. Citation section. `README.md`, a new `### Citation` block after the proposed License section (after line 547).
   - Current: none.
   - Proposed: `If you use agents_Inc in research, please cite it. GitHub's "Cite this repository" button reads CITATION.cff. The DOI for all versions is <concept DOI>.` Replace `<concept DOI>` once Zenodo confirms it.

7. Start-here install line. `docs/START-HERE.md` line 5, under "## Cross-project direct Codex install (pre-MVP)".
   - Current: ``From a source checkout: `python3 -m agents_inc.install.cli install --source "$PWD"`.``
   - Proposed: ``From a source checkout: `python3 -m agents_inc.install.cli install --source "$PWD"`. With the PyPI package installed (`pip install agents-inc`), the same step is `agents-inc install --source <path to your checkout>`; it still needs the checkout, because the installer copies `skills/` from it.``
