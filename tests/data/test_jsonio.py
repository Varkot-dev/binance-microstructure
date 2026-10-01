import json

import numpy as np

from microstructure.data.jsonio import dumps_strict, json_safe


def test_non_finite_floats_become_null_at_any_depth():
    obj = {"a": float("nan"), "b": [1.0, float("inf"), {"c": float("-inf")}], "d": (np.nan,)}
    parsed = json.loads(dumps_strict(obj))
    assert parsed == {"a": None, "b": [1.0, None, {"c": None}], "d": [None]}


def test_numpy_scalars_and_arrays_are_converted():
    obj = {"x": np.float64("nan"), "y": np.int64(3), "z": np.array([1.0, np.nan])}
    assert json_safe(obj) == {"x": None, "y": 3, "z": [1.0, None]}


def test_output_is_strict_json():
    text = dumps_strict({"v": float("nan")})
    assert "NaN" not in text and "Infinity" not in text
