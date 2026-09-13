# Tests path sanitizing and contained path joining for execution ids.
# Rejects traversal separators and absolute paths.
from __future__ import annotations
from pathlib import Path
import pytest
from src.services.path_safety import contained_path, sanitize_leaf_name


def test_sanitize_leaf_name_allows_execution_style_ids():
    assert sanitize_leaf_name("Indomie_001 (BAD)") == "Indomie_001 (BAD)"


def test_sanitize_leaf_name_rejects_traversal_and_separators():
    with pytest.raises(ValueError, match="traversal|separators|absolute"):
        sanitize_leaf_name("../secret")
    with pytest.raises(ValueError, match="separators|absolute"):
        sanitize_leaf_name("foo/bar")
    with pytest.raises(ValueError, match="absolute"):
        sanitize_leaf_name("/etc/passwd")


def test_contained_path_stays_under_base(tmp_path: Path):
    path = contained_path(tmp_path, "Aqua_001 (BAD)", suffix=".wav")
    assert path.parent == tmp_path.resolve()
    assert path.name == "Aqua_001 (BAD).wav"


def test_contained_path_rejects_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        contained_path(tmp_path, "..")
