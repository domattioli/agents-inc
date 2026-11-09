"""Release metadata and packaging checks for the agents-inc distribution."""
import glob
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import agents_inc

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "agents_inc"
DIST = ROOT / ".scratch" / "release" / "dist"
POLYFORM_TITLE = "PolyForm Small Business License 1.0.0"
# Files the build needs; tests and docs stay out of the wheel.
BUILD_INPUTS = ("pyproject.toml", "MANIFEST.in", "README.md", "LICENSE", "LICENSE-AI.md", "NOTICE", "CHANGELOG.md", "CITATION.cff")


def _pyproject():
    with open(ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)


def _all_json():
    return {p.relative_to(ROOT).as_posix() for p in PACKAGE.rglob("*.json") if "__pycache__" not in p.parts}


def _package_data_matches(package_data):
    # Every directory under agents_inc is a package (find uses namespaces), so
    # setuptools applies the "*" globs plus the package's own globs in each one.
    matched = set()
    for directory in [PACKAGE, *(p for p in PACKAGE.rglob("*") if p.is_dir())]:
        if "__pycache__" in directory.parts:
            continue
        name = ".".join(directory.relative_to(ROOT).parts)
        patterns = [*package_data.get("*", []), *package_data.get("", []), *package_data.get(name, [])]
        for pattern in patterns:
            for hit in glob.glob(str(directory / pattern), recursive=True):
                path = Path(hit)
                if path.is_file() and "__pycache__" not in path.parts:
                    matched.add(path.relative_to(ROOT).as_posix())
    return matched


class ReleaseMetadataTests(unittest.TestCase):
    def setUp(self):
        if tomllib is None:
            self.skipTest("tomllib needs Python 3.11 or later")
        self.pyproject = _pyproject()

    def test_versions_agree(self):
        project = self.pyproject["project"]
        if "version" in project:
            self.assertEqual(project["version"], agents_inc.__version__)
        else:
            self.assertIn("version", project.get("dynamic", []))
            attr = self.pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"]
            self.assertEqual(attr, "agents_inc.__version__")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        released = re.findall(r"^## \[(\d[^\]]*)\]", changelog, re.MULTILINE)
        self.assertTrue(released, "CHANGELOG.md has no released version heading")
        self.assertEqual(released[0], agents_inc.__version__)

    def test_citation_and_zenodo_versions(self):
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        match = re.search(r"^version:\s*(\S+)\s*$", citation, re.MULTILINE)
        self.assertIsNotNone(match, "CITATION.cff has no version line")
        self.assertEqual(match.group(1).strip("\"'"), agents_inc.__version__)
        zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
        self.assertEqual(zenodo["version"], agents_inc.__version__)

    def test_license_text(self):
        # LICENSE is the official PolyForm Small Business 1.0.0 text, unmodified (DomI licensing policy).
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        first = text.splitlines()[0]
        self.assertEqual(first.removeprefix("# "), POLYFORM_TITLE)
        self.assertNotIn("AI/ML TRAINING", text)
        self.assertEqual(hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest(),
                         "03eea824bff13316b767424b3e8f49538b46e52d897aecc87d6344343364aa56")
        addendum = (ROOT / "LICENSE-AI.md").read_text(encoding="utf-8")
        self.assertIn("SPDX-" "License-Identifier: LicenseRef-Mattioli-NoAI-Training-1.0", addendum)
        self.assertIn("PolyForm\nSmall Business License 1.0.0, unmodified", addendum)
        notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
        self.assertIn("Required Notice: This software is also subject to the additional terms in LICENSE-AI.md", notice)
        # Operator ruling 2026-10-07: the licensing contact is the GitHub profile, never an email address.
        self.assertIn("https://github.com/domattioli", addendum)
        for t in (text, addendum, notice):
            self.assertNotRegex(t, r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    def test_package_data_covers_every_json(self):
        package_data = self.pyproject["tool"]["setuptools"]["package-data"]
        self.assertEqual(_package_data_matches(package_data), _all_json())


def _has_pypa_build():
    # A stray build/ output directory at the repo root imports as a namespace
    # package named "build", so look for the real module entry point.
    try:
        return importlib.util.find_spec("build.__main__") is not None
    except ModuleNotFoundError:
        return False


# Fallback when pypa build is absent: call the PEP 517 hooks of the installed
# setuptools directly, which is what build --no-isolation does underneath.
BUILD_META = (
    "import sys, setuptools.build_meta as b; "
    "out = sys.argv[1]; b.build_sdist(out); b.build_wheel(out)"  # the hooks rewrite sys.argv
)


class BuildTests(unittest.TestCase):
    def test_wheel_ships_json_and_license(self):
        if tomllib is None:
            self.skipTest("tomllib needs Python 3.11 or later")
        # Offline build: reuse the local setuptools instead of downloading one.
        try:
            setuptools_major = int(importlib.metadata.version("setuptools").split(".")[0])
        except importlib.metadata.PackageNotFoundError:
            setuptools_major = 0
        if setuptools_major < 77:
            self.skipTest("setuptools 77 or later is needed for an offline build")
        dist = DIST
        try:
            dist.mkdir(parents=True, exist_ok=True)
        except OSError:  # read-only checkout (e.g. a container mount, #129)
            dist = Path(self.enterContext(tempfile.TemporaryDirectory())) / "dist"
            dist.mkdir()
        if _has_pypa_build():
            command = [sys.executable, "-m", "build", "--no-isolation", "--sdist", "--wheel", "--outdir", str(dist), "."]
        else:
            command = [sys.executable, "-c", BUILD_META, str(dist)]
        for stale in dist.glob(f"agents_inc-{agents_inc.__version__}*"):
            stale.unlink()
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            for name in BUILD_INPUTS:
                shutil.copy2(ROOT / name, source / name)
            for package in ("agents_inc", "workerbees", "skills/workerbee", "skills/codex-bridge"):
                shutil.copytree(ROOT / package, source / package, ignore=ignore)
            (source / "docs/governance").mkdir(parents=True)
            shutil.copy2(ROOT / "docs/governance/SCHEMA-3NF.md", source / "docs/governance/SCHEMA-3NF.md")
            env = {**os.environ, "HOME": tmp, "XDG_CACHE_HOME": str(Path(tmp) / "cache")}
            result = subprocess.run(command, cwd=source, capture_output=True, text=True, env=env, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
        wheels = list(dist.glob(f"agents_inc-{agents_inc.__version__}-*.whl"))
        self.assertEqual(len(wheels), 1, result.stdout[-2000:] + result.stderr[-2000:])
        self.assertTrue(list(dist.glob(f"agents_inc-{agents_inc.__version__}.tar.gz")))
        with zipfile.ZipFile(wheels[0]) as wheel:
            names = set(wheel.namelist())
            metadata = next(n for n in names if n.endswith(".dist-info/METADATA"))
            self.assertIn("License-Expression: PolyForm-Small-Business-1.0.0 AND LicenseRef-Mattioli-NoAI-Training-1.0", wheel.read(metadata).decode())
        self.assertLessEqual(_all_json(), names)
        self.assertTrue(any(re.fullmatch(r"[^/]+\.dist-info/(licenses/)?LICENSE", n) for n in names), sorted(names))
        tops = {n.split("/")[0] for n in names if not n.split("/")[0].endswith(".dist-info")}
        self.assertEqual(tops, {"agents_inc", "workerbees"})
        for packaged in ("agents_inc/_skills/workerbee/SKILL.md",
                         "agents_inc/_skills/workerbee/scripts/check_dispatch_prompt.py",
                         "agents_inc/_skills/codex-bridge/scripts/at_route.sh",
                         "agents_inc/_docs/SCHEMA-3NF.md"):
            self.assertIn(packaged, names)
        self.assertFalse([n for n in names if n.startswith("agents_inc/_skills/") and "/tests/" in n])
        self.assertFalse([n for n in names if n.startswith("agents_inc/_skills/")
                          and n.split("/")[2] not in ("workerbee", "codex-bridge")])


if __name__ == "__main__":
    unittest.main()
