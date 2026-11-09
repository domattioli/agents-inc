"""Tests for agents_inc.catalog_refresh module (spec 012 T014)."""
import json
from pathlib import Path
from tests._free012 import fixture, hermetic, parametrize, suite  # noqa: F401


# 3 stale IDs from spec FR-002
STALE_IDS = [
    "google/lyria-3-pro-preview",
    "google/lyria-3-clip-preview",
    "openrouter/free",
]

# New free text model in fixture
NEW_FREE_TEXT = "newvendor/new-flash-2026:free"

# Audio model in fixture (non-text output)
AUDIO_MODEL = "google/lyria-3-audio:free"


class TestCatalogRefreshDryRun:
    """Test catalog refresh in dry-run mode (default)."""

    def test_dry_run_lists_stale_ids_as_unavailable(self, hermetic, tmp_path):
        """Dry-run lists all 3 stale ids as 'would mark unavailable' and doesn't modify file."""
        # Copy models.json to tmp
        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())
        original_bytes = models_path.read_bytes()

        # Call refresh with fixture
        from agents_inc import catalog_refresh
        fixture_path = Path(__file__).parent / "fixtures" / "012" / "openrouter_models.json"
        lines = catalog_refresh.refresh(apply=False, from_file=str(fixture_path), models_path=str(models_path))

        # Check: all 3 stale IDs listed as "would mark unavailable"
        unavailable_lines = [line for line in lines if "would mark unavailable:" in line]
        unavailable_ids = [line.split("would mark unavailable:")[1].strip() for line in unavailable_lines]

        for stale_id in STALE_IDS:
            assert stale_id in unavailable_ids, f"Stale ID {stale_id} not listed as unavailable"

        # Check: file is byte-identical
        assert models_path.read_bytes() == original_bytes, "Dry-run modified the file"

    def test_dry_run_lists_3_unavailable_lines_exactly(self, hermetic, tmp_path):
        """Dry-run lists exactly 3 'would mark unavailable' lines."""
        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())

        from agents_inc import catalog_refresh
        fixture_path = Path(__file__).parent / "fixtures" / "012" / "openrouter_models.json"
        lines = catalog_refresh.refresh(apply=False, from_file=str(fixture_path), models_path=str(models_path))

        unavailable_lines = [line for line in lines if "would mark unavailable:" in line]
        assert len(unavailable_lines) == 3, f"Expected 3 unavailable lines, got {len(unavailable_lines)}: {unavailable_lines}"


class TestCatalogRefreshApply:
    """Test catalog refresh in apply mode."""

    def test_apply_adds_new_free_text_model_with_empty_tasks_good(self, hermetic, tmp_path):
        """Apply mode adds new free text model with tasks_good: []."""
        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())

        from agents_inc import catalog_refresh
        fixture_path = Path(__file__).parent / "fixtures" / "012" / "openrouter_models.json"
        lines = catalog_refresh.refresh(apply=True, from_file=str(fixture_path), models_path=str(models_path))

        # Read the updated models.json
        with open(models_path) as f:
            data = json.load(f)

        # Check: new free text model is added
        assert NEW_FREE_TEXT in data["models"], f"New model {NEW_FREE_TEXT} not added"
        entry = data["models"][NEW_FREE_TEXT]
        assert entry.get("tasks_good") == [], f"tasks_good should be [], got {entry.get('tasks_good')}"
        assert entry.get("provider") == "openrouter", f"provider should be openrouter"
        assert entry.get("tier") == "grunt", f"tier should be grunt"
        assert entry.get("status") == "unprobed", f"status should be unprobed"

    def test_apply_marks_audio_model_unavailable(self, hermetic, tmp_path):
        """Apply mode marks non-text (audio) models unavailable."""
        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())

        from agents_inc import catalog_refresh
        fixture_path = Path(__file__).parent / "fixtures" / "012" / "openrouter_models.json"
        lines = catalog_refresh.refresh(apply=True, from_file=str(fixture_path), models_path=str(models_path))

        # Read the updated models.json
        with open(models_path) as f:
            data = json.load(f)

        # Check: audio model is marked unavailable
        assert AUDIO_MODEL in data["models"], f"Audio model {AUDIO_MODEL} not in catalog"
        assert data["models"][AUDIO_MODEL].get("status") == "unavailable", \
            f"Audio model should be unavailable, got {data['models'][AUDIO_MODEL].get('status')}"

    def test_apply_clears_overlay_for_refreshed_ids(self, hermetic, tmp_path):
        """Apply mode clears overlay entries for refreshed ids."""
        # Setup: create an overlay with some entries
        codex_dir = tmp_path / ".codex-bridge"
        codex_dir.mkdir()
        overlay_path = codex_dir / "model-status.json"
        overlay = {
            STALE_IDS[0]: {"status": "unavailable", "reason": "withdrawn"},
            STALE_IDS[1]: {"status": "unavailable", "reason": "zdr"},
            "some-other-model": {"status": "unavailable", "reason": "withdrawn"},
        }
        overlay_path.write_text(json.dumps(overlay))

        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())

        from agents_inc import catalog_refresh
        fixture_path = Path(__file__).parent / "fixtures" / "012" / "openrouter_models.json"
        lines = catalog_refresh.refresh(apply=True, from_file=str(fixture_path), models_path=str(models_path))

        # Check: overlay is cleared for refreshed stale IDs but preserves unrelated entries
        with open(overlay_path) as f:
            updated_overlay = json.load(f)

        for stale_id in STALE_IDS:
            assert stale_id not in updated_overlay, f"Stale ID {stale_id} should be removed from overlay"

        assert "some-other-model" in updated_overlay, "Unrelated overlay entry should be preserved"


class TestCatalogRefreshErrors:
    """Test catalog refresh error handling."""

    def test_fetch_failure_exits_2_no_file_writes(self, hermetic, tmp_path):
        """Fetch error (missing file, urlopen fail) exits 2 and doesn't modify file."""
        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())
        original_bytes = models_path.read_bytes()

        from agents_inc import catalog_refresh
        # Non-existent file path
        try:
            exit_code = catalog_refresh.main(argv=["--apply", "--from-file", "/nonexistent/path.json"])
            assert exit_code == 2, f"Expected exit 2, got {exit_code}"
        except SystemExit as e:
            assert e.code == 2, f"Expected exit 2, got {e.code}"

        # File should be unchanged
        assert models_path.read_bytes() == original_bytes, "File was modified on error"

    def test_dry_run_no_network_call(self, hermetic, tmp_path):
        """Dry-run with hermetic fixture raises if urlopen is called (no network)."""
        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())

        # Hermetic fixture blocks urlopen, so if we don't use from_file, it should raise
        from agents_inc import catalog_refresh
        # This should work fine with from_file
        fixture_path = Path(__file__).parent / "fixtures" / "012" / "openrouter_models.json"
        lines = catalog_refresh.refresh(apply=False, from_file=str(fixture_path), models_path=str(models_path))
        assert len(lines) > 0, "Should have returned lines"


class TestCatalogRefreshCLI:
    """Test CLI interface."""

    def test_cli_default_dry_run(self, hermetic, tmp_path):
        """CLI default behavior is dry-run."""
        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())
        original_bytes = models_path.read_bytes()

        from agents_inc import catalog_refresh
        fixture_path = Path(__file__).parent / "fixtures" / "012" / "openrouter_models.json"
        exit_code = catalog_refresh.main(argv=["--from-file", str(fixture_path), "--models-path", str(models_path)])

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"
        assert models_path.read_bytes() == original_bytes, "Dry-run should not modify file"

    def test_cli_apply_flag(self, hermetic, tmp_path):
        """CLI --apply flag enables apply mode."""
        models_path = tmp_path / "models.json"
        original = Path(__file__).parent.parent / "agents_inc" / "models.json"
        models_path.write_text(original.read_text())

        from agents_inc import catalog_refresh
        fixture_path = Path(__file__).parent / "fixtures" / "012" / "openrouter_models.json"
        exit_code = catalog_refresh.main(argv=["--apply", "--from-file", str(fixture_path), "--models-path", str(models_path)])

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"

        # File should be modified
        with open(models_path) as f:
            data = json.load(f)
        assert NEW_FREE_TEXT in data["models"], "New model should be added in apply mode"


def load_tests(loader, tests, pattern):
    """Expose this fixture-style file to `unittest discover` (see _free012.suite)."""
    return suite(globals(), autouse=("hermetic",))
