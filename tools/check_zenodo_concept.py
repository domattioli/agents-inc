"""Check that Zenodo archived a release under the agents-inc concept DOI.

Run after the GitHub release. Zenodo archives a few minutes later, so the check retries.
Exit 0: a record for the version sits under the concept. Exit 1: the record is missing
after the last try, or it sits under another concept (the 0.3.1 failure, record 23288172).

    python3 tools/check_zenodo_concept.py 0.3.2 [--attempts 10] [--interval 60]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

CONCEPT_RECID = "22670100"
CONCEPT_DOI = "10.5281/zenodo.22670100"
API = "https://zenodo.org/api/records"


def _get(params: dict) -> list:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "agents-inc-zenodo-check"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed https URL)
        return json.load(resp)["hits"]["hits"]


def _version(hit: dict) -> str:
    return str(hit.get("metadata", {}).get("version", "")).strip().lstrip("v")


def check_once(version: str, fetch=_get) -> tuple[str, str]:
    """Return (status, message). status: ok, stray, missing."""
    version = version.strip().lstrip("v")
    for hit in fetch({"q": f"conceptrecid:{CONCEPT_RECID}", "all_versions": "true", "size": 25}):
        if _version(hit) == version:
            if hit.get("conceptdoi") != CONCEPT_DOI:
                return "stray", f"record {hit.get('id')} has conceptdoi {hit.get('conceptdoi')}, want {CONCEPT_DOI}"
            return "ok", f"record {hit.get('id')} version {version} under {CONCEPT_DOI}"
    for hit in fetch({"q": "title:agents-inc", "all_versions": "true", "sort": "mostrecent", "size": 25}):
        if _version(hit) == version and str(hit.get("conceptrecid")) != CONCEPT_RECID:
            return "stray", (f"record {hit.get('id')} version {version} sits under concept "
                             f"{hit.get('conceptdoi')}, not {CONCEPT_DOI}; see docs/RELEASING.md")
    return "missing", f"no Zenodo record for version {version} yet"


def main(argv=None, fetch=_get, sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("version")
    ap.add_argument("--attempts", type=int, default=10)
    ap.add_argument("--interval", type=float, default=60.0)
    args = ap.parse_args(argv)
    msg = ""
    for attempt in range(1, args.attempts + 1):
        try:
            status, msg = check_once(args.version, fetch)
        except Exception as exc:  # network or API error: retry, never pass
            status, msg = "missing", f"Zenodo query failed: {exc}"
        print(f"attempt {attempt}/{args.attempts}: {status}: {msg}")
        if status == "ok":
            return 0
        if status == "stray":
            print(f"FAIL: {msg}", file=sys.stderr)
            return 1
        if attempt < args.attempts:
            sleep(args.interval)
    print(f"FAIL: {msg} after {args.attempts} attempts", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
