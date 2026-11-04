"""dispatch_record.v1: stdlib validator for the slots JSON that `render_dispatch.py --slots` and `agents-inc dispatch` read.

No JSON Schema files, no third-party import (same stance as agents_inc/config_schema.py).

validate_record(obj, model=None) -> list[str]: every error, empty when the record is valid. Slot names are the field names.
normalize(obj) -> (copy of obj, converted field names): old string forms of FILES_IN_SCOPE, ALLOWLIST and FAN_OUT become
structured values; a value already structured is left alone. Renderers turn structured values back into the string form
with slot_text(), so a structured record and its old string form render identically.

Structured types:
  FILES_IN_SCOPE, ALLOWLIST: list of non-empty strings (single-line); "none" or an item starting "none" means nothing.
  FAN_OUT: {"width": int, "total": int, "depth": int}, each >= 0.
Enums:
  CLASSIFICATION: first word is public, internal or confidential.
  EFFORT: a whole word low, medium, high, xhigh or max (ultra only for a codex model).
  schema_version: absent means 1; any other value is an error.
"""
from __future__ import annotations

import re

SCHEMA_VERSION = 1
CLASSIFICATIONS = ("public", "internal", "confidential")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
CODEX_ALIASES = ("astra", "sol", "terra", "luna")
_FAN_OUT_RE = re.compile(r"width\s+(\d+)\s*,\s*total\s+(\d+)\s*,\s*depth\s+(\d+)")
_FAN_OUT_KEYS = ("width", "total", "depth")
_NONE_ITEM = "none"


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _is_none_text(text: str) -> bool:
    return text.strip().lower().startswith(_NONE_ITEM)


def _split_list(text: str) -> list[str]:
    """Old string form to items: one per line for FILES_IN_SCOPE, commas also split for ALLOWLIST."""
    return [part.strip() for part in re.split(r"[\n,]", text) if part.strip()]


def normalize(obj) -> tuple[dict, list[str]]:
    """Return (shallow copy with structured fields, names converted from the old string form). Never raises."""
    if not isinstance(obj, dict):
        return obj, []
    out = dict(obj)
    converted: list[str] = []
    for name in ("FILES_IN_SCOPE", "ALLOWLIST"):
        value = out.get(name)
        if isinstance(value, str) and value.strip():
            if _is_none_text(value) and "\n" not in value.strip():
                out[name] = [_NONE_ITEM]
            elif name == "FILES_IN_SCOPE":
                out[name] = [ln.strip() for ln in value.splitlines() if ln.strip()]
            else:
                out[name] = _split_list(value)
            converted.append(name)
    value = out.get("FAN_OUT")
    if isinstance(value, str):
        match = _FAN_OUT_RE.fullmatch(value.strip())
        if match:
            out["FAN_OUT"] = dict(zip(_FAN_OUT_KEYS, (int(g) for g in match.groups())))
            converted.append("FAN_OUT")
    return out, converted


def slot_text(name: str, value):
    """The string form a structured value renders as; a str (or anything else) is returned unchanged."""
    if name == "FAN_OUT" and isinstance(value, dict):
        return f"width {value['width']}, total {value['total']}, depth {value['depth']}"
    if name == "FILES_IN_SCOPE" and isinstance(value, list):
        return "\n".join(value)
    if name == "ALLOWLIST" and isinstance(value, list):
        return "none -- do all work yourself" if value == [_NONE_ITEM] else ", ".join(value)
    return value


def _check_list(name: str, value, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{name} must be a non-empty array of strings or the string form")
        return
    for n, item in enumerate(value, 1):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{name} item {n} must be a non-empty string")
        elif "\n" in item or "\r" in item:
            errors.append(f"{name} item {n} must be one line")


def _check_fan_out(value, errors: list[str]) -> None:
    if isinstance(value, str):
        errors.append("FAN_OUT string must read 'width <n>, total <n>, depth <n>'")
        return
    if not isinstance(value, dict):
        errors.append("FAN_OUT must be an object {width, total, depth} of integers")
        return
    extra = sorted(set(value) - set(_FAN_OUT_KEYS))
    if extra:
        errors.append(f"FAN_OUT has unknown keys: {', '.join(extra)}")
    for key in _FAN_OUT_KEYS:
        if not _is_int(value.get(key)) or value[key] < 0:
            errors.append(f"FAN_OUT.{key} must be an integer of 0 or more")


def _delegate_is_codex(obj: dict, model) -> bool:
    for cand in (model, obj.get("DELEGATE"), obj.get("MODEL")):
        if isinstance(cand, str) and cand.strip().lower() in CODEX_ALIASES:
            return True
    return False


def validate_record(obj, model=None) -> list[str]:
    """Return every error in a dispatch record; [] when valid. Absent optional slots are not errors."""
    if not isinstance(obj, dict):
        return [f"record must be a JSON object, got {type(obj).__name__}"]
    obj, _ = normalize(obj)  # idempotent: the old string forms validate as their structured selves
    errors: list[str] = []
    version = obj.get("schema_version", SCHEMA_VERSION)
    if not _is_int(version) or version != SCHEMA_VERSION:
        errors.append(f"schema_version {version!r} is not supported; this validator reads {SCHEMA_VERSION}")
    for name in ("FILES_IN_SCOPE", "ALLOWLIST"):
        if not _blank(obj.get(name)):
            _check_list(name, obj[name], errors)
    if not _blank(obj.get("FAN_OUT")):
        _check_fan_out(obj["FAN_OUT"], errors)
    value = obj.get("CLASSIFICATION")
    if not _blank(value):
        words = re.findall(r"[a-z]+", value.lower()) if isinstance(value, str) else []
        if not words or words[0] not in CLASSIFICATIONS:
            errors.append(f"CLASSIFICATION must start with one of {', '.join(CLASSIFICATIONS)}")
    value = obj.get("EFFORT")
    if not _blank(value):
        words = re.findall(r"[a-z]+", value.lower()) if isinstance(value, str) else []
        allowed = EFFORTS + (("ultra",) if _delegate_is_codex(obj, model) else ())
        if not any(w in allowed for w in words):
            note = "" if "ultra" in allowed else " (ultra is for a codex model only)"
            errors.append(f"EFFORT must name one of {', '.join(allowed)}{note}")
    return errors
