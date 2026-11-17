"""Optional, operator-supplied BenchLM selector evidence; never grants eligibility."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

JOBS = frozenset({
    "Emails", "Copywriting", "Creative writing", "Studying", "Research", "Reasoning",
    "Math", "Legal research", "Image understanding", "Chart analysis", "PDFs", "Excel",
    "Data analysis", "Finance and accounting", "Data extraction", "Presentations", "Coding",
    "Debugging", "Website building", "Local LLM for coding", "Agents", "RAG",
    "Customer service", "Translation", "Language learning", "AI assistant", "Roleplay",
    "Medical research", "Cybersecurity", "AI voice assistant", "Meeting notes", "Images", "Video",
})
SOURCE = "https://benchlm.ai/tools/llm-selector"
MAX_AGE_DAYS = 90


def load_snapshot(snapshot_path: str | Path, *, today: date | None = None) -> dict:
    """Load an operator-supplied snapshot or raise ValueError; never fetch data."""
    try:
        data = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("source") != SOURCE:
            raise ValueError("unexpected source")
        stamp = date.fromisoformat(data["date"])
        current = today or date.today()
        if stamp > current or current - stamp > timedelta(days=MAX_AGE_DAYS):
            raise ValueError("snapshot date is stale or in the future")
        entries = data["entries"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("snapshot has no entries")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid entry")
            entry_job, kind = entry["job"], entry["evidence_kind"]
            model, cohort, rank = entry["model"], entry["cohort"], entry["rank"]
            if (entry_job not in JOBS or kind not in ("direct", "proxy")
                    or not isinstance(model, str) or not model.strip()
                    or not isinstance(cohort, str) or not cohort.strip()
                    or type(rank) is not int or rank < 1):
                raise ValueError("invalid entry")
            key = (entry_job, model)
            if key in seen:
                raise ValueError("duplicate job and model")
            seen.add(key)
        return data
    except (OSError, UnicodeError, TypeError, KeyError, OverflowError) as exc:
        raise ValueError("snapshot is unreadable or malformed") from exc


def advise(routes: tuple, snapshot_path: str | Path | None, job: str | None, *, today: date | None = None) -> tuple:
    """Reorder only ranked slots within a single provider, evidence kind and cohort."""
    if not snapshot_path or not isinstance(job, str) or job not in JOBS:
        return routes
    try:
        data = load_snapshot(snapshot_path, today=today)
    except ValueError:
        return routes
    groups = {entry["model"]: (entry["evidence_kind"], entry["cohort"], entry["rank"])
              for entry in data["entries"] if entry["job"] == job}

    result = list(routes)
    slots = {}
    for index, route in enumerate(routes):
        evidence = groups.get(route.model)
        # Preserve the existing auto fallback and provider priority boundaries.
        if evidence and route.model != "openrouter/auto:free":
            slots.setdefault((route.provider, evidence[0], evidence[1]), []).append(index)
    for indexes in slots.values():
        ordered = sorted((routes[i] for i in indexes), key=lambda route: groups[route.model][2])
        for index, route in zip(indexes, ordered):
            result[index] = route
    return tuple(result)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Validate a local BenchLM evidence snapshot")
    parser.add_argument("snapshot")
    args = parser.parse_args(argv)
    try:
        data = load_snapshot(args.snapshot)
    except ValueError as exc:
        print(f"snapshot invalid: {exc}")
        return 1
    print(f"snapshot valid: {data['date']}, {len(data['entries'])} entries; source content is not independently verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
