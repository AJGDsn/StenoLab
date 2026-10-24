import os

import pytest

import logic.file_io as file_io


def test_atomic_write_replaces_contents_and_leaves_no_temp_file(tmp_path):
    target = tmp_path / "dict.json"
    target.write_text("old", encoding="utf-8")

    file_io.atomic_write_text(str(target), "new")

    assert target.read_text(encoding="utf-8") == "new"
    assert os.listdir(tmp_path) == ["dict.json"]


def test_failed_atomic_write_keeps_the_original_file(tmp_path, monkeypatch):
    target = tmp_path / "dict.json"
    target.write_text("original", encoding="utf-8")

    def fail(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(file_io.os, "replace", fail)

    with pytest.raises(OSError):
        file_io.atomic_write_text(str(target), "half-written")

    assert target.read_text(encoding="utf-8") == "original"
    assert os.listdir(tmp_path) == ["dict.json"]
