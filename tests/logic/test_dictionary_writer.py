import json

import pytest

import logic.metadata_store as metadata_store
from logic.dictionary_loader import load_dictionary_with_metadata
from logic.dictionary_writer import convert_dictionary

RTF = (
    "{\\rtf1\\ansi{\\*\\cxrev100}\\cxdict{\\*\\cxsystem Test}{\\stylesheet{\\s0 Normal;}}\r\n"
    "{\\*\\cxs KAT}cat\r\n"
    "{\\*\\cxs -G}\\cxds ing\r\n"
    "{\\*\\cxs KAT}duplicate\r\n"
    "}\r\n"
)


@pytest.fixture(autouse=True)
def isolated_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(metadata_store, "METADATA_ROOT", str(tmp_path / "metadata"))
    monkeypatch.setattr(metadata_store, "LEGACY_METADATA_ROOT", str(tmp_path / "legacy"))


def _pairs(path):
    entries, _, _ = load_dictionary_with_metadata(str(path))
    return [(e["steno"], e["english"]) for e in entries]


def test_convert_rtf_to_json_preserves_order_and_duplicates(tmp_path):
    src = tmp_path / "dict.rtf"
    src.write_text(RTF, encoding="ascii")
    dst = tmp_path / "dict.json"

    assert convert_dictionary(str(src), str(dst)) == 3

    assert json.loads(dst.read_text(encoding="utf-8"), object_pairs_hook=list) == [
        ("KAT", "cat"), ("-G", "{^ing}"), ("KAT", "duplicate"),
    ]


def test_convert_json_to_rtf_round_trips(tmp_path):
    src = tmp_path / "dict.json"
    src.write_text('{"KAT": "cat", "-G": "{^ing}", "TEFT": "café {.}"}', encoding="utf-8")
    dst = tmp_path / "dict.rtf"

    convert_dictionary(str(src), str(dst))

    assert dst.read_text(encoding="ascii").startswith("{\\rtf1")
    assert _pairs(dst) == _pairs(src)


def test_convert_carries_metadata_to_destination(tmp_path):
    src = tmp_path / "dict.json"
    src.write_text('{"KAT": "cat"}', encoding="utf-8")
    metadata_store.save_metadata(str(src), {"KAT": {"comments": "keep me"}})
    dst = tmp_path / "dict.rtf"

    convert_dictionary(str(src), str(dst))

    assert metadata_store.load_metadata(str(dst)) == {"KAT": {"comments": "keep me"}}
