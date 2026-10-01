"""Tests for site/build_data.py, which is stdlib-only and so cannot import the package."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from microstructure.analyses.q5_kernel_panel import BALANCE_BIAS_FLOOR

BUILD_DATA_PATH = Path(__file__).resolve().parents[2] / "site" / "build_data.py"


@pytest.fixture(scope="module")
def build_data():
    spec = importlib.util.spec_from_file_location("site_build_data", BUILD_DATA_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_balance_band_floor_matches_q5(build_data):
    assert build_data.BALANCE_BAND_FLOOR == BALANCE_BIAS_FLOOR


def test_write_slice_raises_on_nan_instead_of_writing_invalid_json(build_data, tmp_path, monkeypatch):
    monkeypatch.setattr(build_data, "OUT", tmp_path)
    monkeypatch.setattr(build_data, "REPO_ROOT", tmp_path)
    with pytest.raises(ValueError, match="Out of range float"):
        build_data.write_slice("bad.json", {"x": float("nan")})
    assert not (tmp_path / "bad.json").exists()


def test_write_slice_writes_compact_sorted_json(build_data, tmp_path, monkeypatch):
    monkeypatch.setattr(build_data, "OUT", tmp_path)
    monkeypatch.setattr(build_data, "REPO_ROOT", tmp_path)
    build_data.write_slice("ok.json", {"b": 1, "a": [1.5, None]})
    text = (tmp_path / "ok.json").read_text()
    assert text == '{"a":[1.5,null],"b":1}\n'
    assert json.loads(text) == {"a": [1.5, None], "b": 1}
