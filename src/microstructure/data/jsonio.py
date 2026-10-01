"""Strict JSON output for analysis results.

Python's json module writes NaN and Infinity by default, which are not valid
JSON and break downstream readers. `dumps_strict` converts non-finite floats to
null first and passes allow_nan=False as a backstop, so an unconverted value
raises instead of being written.
"""
from __future__ import annotations

import json
import math
from typing import Any

import numpy as np


def json_safe(obj: Any) -> Any:
    """Recursively convert numpy types to Python types and non-finite floats to None."""
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [json_safe(v) for v in obj.tolist()]
    if isinstance(obj, np.generic):
        return json_safe(obj.item())
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def dumps_strict(obj: Any, indent: int = 2) -> str:
    """json.dumps of `json_safe(obj)` with allow_nan=False."""
    return json.dumps(json_safe(obj), indent=indent, allow_nan=False)
