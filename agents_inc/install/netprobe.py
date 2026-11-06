"""Spec 029: child script for `agents-inc doctor --probe-dispatch`. Stdlib only, no package imports:
the child runs under `worker_env`, which passes no PYTHONPATH."""
import json
import ssl
import sys
import time
import urllib.error
import urllib.request


def classify(exc) -> str:
    """reachable = TLS ok and any HTTP answer; cert = verification failed; blocked = anything else."""
    if isinstance(exc, urllib.error.HTTPError): return "reachable"
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    return "cert" if isinstance(reason, ssl.SSLCertVerificationError) else "blocked"


def probe(host, timeout=5.0, opener=None) -> dict:
    """GET https://<host>/ with no proxy from env or the system; opener is injected by tests."""
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({})).open
    start = time.monotonic()
    try:
        opener(f"https://{host}/", timeout=timeout)
        status = "reachable"
    except Exception as exc:  # any failure is a status, never a crash
        status = classify(exc)
    return {"host": host, "status": status, "elapsed": round(time.monotonic() - start, 2)}


if __name__ == "__main__":
    for host in sys.argv[1:]:
        print(json.dumps(probe(host)), flush=True)  # flush: a killed child still leaves the finished rows
