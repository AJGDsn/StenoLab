import json
import os

import pytest

import logic.metadata_store as metadata_store
from logic.dictionary_loader import load_dictionary_with_metadata


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(metadata_store, "METADATA_ROOT", str(tmp_path / "metadata"))
    monkeypatch.setattr(metadata_store, "LEGACY_METADATA_ROOT", str(tmp_path / "legacy"))


def write(path, data, mtime=None):
    path.write_text(json.dumps(data), encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def comments(dict_path):
    _, metadata, _ = load_dictionary_with_metadata(str(dict_path))
    return {steno: m["comments"] for steno, m in metadata.items()}


def test_delivered_metadata_is_imported_on_first_open(tmp_path):
    dictionary = tmp_path / "Ian-rationalised.json"
    write(dictionary, {"KAT": "cat", "TKOG": "dog"})
    write(tmp_path / "Ian-rationalised.stenolab-meta.json",
          {"KAT": {"comments": "? double: KA*T", "brief": False, "date_added": ""}})

    assert comments(dictionary) == {"KAT": "? double: KA*T"}
    stored = metadata_store.load_metadata(str(dictionary))
    assert stored["KAT"]["comments"] == "? double: KA*T"


def test_not_reimported_once_stenolab_has_a_newer_copy(tmp_path):
    dictionary = tmp_path / "d.json"
    write(dictionary, {"KAT": "cat"})
    sidecar = tmp_path / "d.stenolab-meta.json"
    write(sidecar, {"KAT": {"comments": "delivered"}}, mtime=1_000_000)
    comments(dictionary)

    # The user edits the comment in StenoLab and saves.
    metadata_store.save_metadata(str(dictionary), {"KAT": {"comments": "edited in StenoLab"}})
    assert comments(dictionary)["KAT"] == "edited in StenoLab"


def test_a_newer_delivery_is_merged_without_wiping_dates(tmp_path):
    dictionary = tmp_path / "d.json"
    write(dictionary, {"KAT": "cat", "TKOG": "dog"})
    metadata_store.save_metadata(str(dictionary), {
        "KAT": {"comments": "old", "date_added": "2020-01-01"},
        "TKOG": {"comments": "keep me"},
    })
    stored = metadata_store._metadata_file_for(str(dictionary))
    os.utime(stored, (1_000_000, 1_000_000))
    write(tmp_path / "d.stenolab-meta.json",
          {"KAT": {"comments": "rebuilt", "date_added": ""}}, mtime=2_000_000)

    _, metadata, _ = load_dictionary_with_metadata(str(dictionary))
    assert metadata["KAT"]["comments"] == "rebuilt"
    assert metadata["KAT"]["date_added"] == "2020-01-01"
    assert metadata["TKOG"]["comments"] == "keep me"


def test_opening_the_metadata_file_itself_explains_the_mistake(tmp_path):
    sidecar = tmp_path / "d.stenolab-meta.json"
    write(sidecar, {"KAT": {"comments": "x"}})
    with pytest.raises(ValueError, match="metadata file, not a dictionary"):
        load_dictionary_with_metadata(str(sidecar))
