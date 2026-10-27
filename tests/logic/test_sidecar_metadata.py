import json
import os

import pytest

import logic.metadata_store as metadata_store
from logic.dictionary_loader import load_dictionary_with_metadata
from logic.metadata_store import DELIVERED_COMMENT_MARK, import_sidecar_metadata


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


def edit(dictionary, steno, **fields):
    """The user changes metadata in StenoLab and saves."""
    stored = metadata_store.load_metadata(str(dictionary))
    stored[steno] = {**stored.get(steno, {}), **fields}
    metadata_store.save_metadata(str(dictionary), stored)


@pytest.fixture
def delivered(tmp_path):
    """A dictionary with a first delivery already imported."""
    dictionary = tmp_path / "d.json"
    write(dictionary, {"KAT": "cat", "TKOG": "dog", "PWEUG": "big"})
    write(tmp_path / "d.stenolab-meta.json", {
        "KAT": {"comments": "rule: vowel"},
        "TKOG": {"comments": "rule: o"},
        "PWEUG": {"comments": "rule: i", "brief": False},
    }, mtime=1_000_000)
    comments(dictionary)
    return dictionary


def redeliver(dictionary, data, mtime=2_000_000):
    write(dictionary.with_name("d.stenolab-meta.json"), data, mtime=mtime)


def test_delivered_metadata_is_imported_on_first_open(tmp_path):
    dictionary = tmp_path / "Ian-rationalised.json"
    write(dictionary, {"KAT": "cat", "TKOG": "dog"})
    write(tmp_path / "Ian-rationalised.stenolab-meta.json",
          {"KAT": {"comments": "? double: KA*T", "brief": False, "date_added": ""}})

    assert comments(dictionary) == {"KAT": "? double: KA*T"}
    stored = metadata_store.load_metadata(str(dictionary))
    assert stored["KAT"]["comments"] == "? double: KA*T"


def test_the_same_delivery_is_not_imported_twice(delivered):
    edit(delivered, "KAT", comments="mine")
    assert import_sidecar_metadata(str(delivered)) is None
    assert comments(delivered)["KAT"] == "mine"


def test_a_rebuild_keeps_comments_edited_in_stenolab(delivered):
    edit(delivered, "KAT", comments="my note")
    redeliver(delivered, {
        "KAT": {"comments": "rule: vowel"},      # unchanged by the rebuild
        "TKOG": {"comments": "rule: short o"},   # changed by the rebuild
        "PWEUG": {"comments": "rule: i", "brief": True},
    })

    assert import_sidecar_metadata(str(delivered)) == 0
    _, metadata, _ = load_dictionary_with_metadata(str(delivered))
    assert metadata["KAT"]["comments"] == "my note"
    assert metadata["TKOG"]["comments"] == "rule: short o"
    assert metadata["PWEUG"]["brief"] is True
    assert not metadata["KAT"]["bookmarked"]


def test_both_sides_changed_keeps_both_and_bookmarks(delivered):
    edit(delivered, "KAT", comments="my note")
    redeliver(delivered, {"KAT": {"comments": "rule: long a"}})

    assert import_sidecar_metadata(str(delivered)) == 1
    meta = metadata_store.load_metadata(str(delivered))["KAT"]
    assert meta["comments"] == f"my note\n{DELIVERED_COMMENT_MARK} rule: long a"
    assert meta["bookmarked"] is True


def test_user_values_win_for_other_fields(delivered):
    edit(delivered, "PWEUG", brief=True)
    redeliver(delivered, {"PWEUG": {"comments": "rule: i", "brief": False, "frequency": 7}})

    import_sidecar_metadata(str(delivered))
    meta = metadata_store.load_metadata(str(delivered))["PWEUG"]
    assert meta["brief"] is True
    assert meta["frequency"] == 7


def test_a_rebuild_can_remove_its_own_comment(delivered):
    redeliver(delivered, {"TKOG": {"comments": ""}})
    import_sidecar_metadata(str(delivered))
    assert comments(delivered)["TKOG"] == ""


def test_removing_a_comment_the_user_edited_keeps_the_users(delivered):
    edit(delivered, "TKOG", comments="my note")
    redeliver(delivered, {"TKOG": {"comments": ""}})
    assert import_sidecar_metadata(str(delivered)) == 0
    assert comments(delivered)["TKOG"] == "my note"


def test_an_older_file_copied_in_by_hand_is_still_imported(delivered):
    # Copying keeps the build's modified time, which can be older than
    # StenoLab's own files; a different file must still come through.
    redeliver(delivered, {"TKOG": {"comments": "rule: short o"}}, mtime=500_000)
    import_sidecar_metadata(str(delivered))
    assert comments(delivered)["TKOG"] == "rule: short o"


def test_blank_delivered_dates_never_wipe_stored_ones(delivered):
    edit(delivered, "KAT", date_added="2020-01-01")
    redeliver(delivered, {"KAT": {"comments": "rule: vowel", "date_added": ""}})
    import_sidecar_metadata(str(delivered))
    assert metadata_store.load_metadata(str(delivered))["KAT"]["date_added"] == "2020-01-01"


def test_new_outlines_in_a_rebuild_are_added(delivered):
    redeliver(delivered, {"SKWRAOUP": {"comments": "rule: j", "date_added": ""}})
    import_sidecar_metadata(str(delivered))
    meta = metadata_store.load_metadata(str(delivered))["SKWRAOUP"]
    assert meta["comments"] == "rule: j"
    assert "date_added" not in meta or meta["date_added"]


def test_a_delivery_imported_before_copies_were_kept_becomes_the_base(tmp_path):
    # StenoLab already holds this delivery (imported by an older version)
    # plus the user's edit; the first open now must not touch either.
    dictionary = tmp_path / "d.json"
    write(dictionary, {"KAT": "cat"})
    write(tmp_path / "d.stenolab-meta.json", {"KAT": {"comments": "rule"}}, mtime=1_000_000)
    metadata_store.save_metadata(str(dictionary), {"KAT": {"comments": "my note"}})

    assert import_sidecar_metadata(str(dictionary)) is None
    assert comments(dictionary)["KAT"] == "my note"

    redeliver(dictionary, {"KAT": {"comments": "rule"}, "TKOG": {"comments": "new"}})
    import_sidecar_metadata(str(dictionary))
    assert comments(dictionary) == {"KAT": "my note", "TKOG": "new"}


def test_opening_the_metadata_file_itself_explains_the_mistake(tmp_path):
    sidecar = tmp_path / "d.stenolab-meta.json"
    write(sidecar, {"KAT": {"comments": "x"}})
    with pytest.raises(ValueError, match="metadata file, not a dictionary"):
        load_dictionary_with_metadata(str(sidecar))
