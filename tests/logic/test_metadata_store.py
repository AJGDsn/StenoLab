from logic.metadata_store import ensure_metadata


def test_ensure_metadata_preserves_existing_and_fills_defaults():
    entries = [
        {"steno": "ST", "english": "set", "date_added": "2026-01-01", "modified": "2026-01-02"},
        {"steno": "TEFT", "english": "test"},
    ]
    existing = {"ST": {"comments": "keep me", "brief": True}}

    metadata = ensure_metadata(entries, existing)

    assert metadata["ST"] == {"comments": "keep me", "brief": True}
    assert metadata["TEFT"]["comments"] == ""
    assert metadata["TEFT"]["brief"] is False
    assert metadata["TEFT"]["bookmarked"] is False
    assert metadata["TEFT"]["frequency"] == 0


def test_saved_metadata_omits_defaults_and_reads_back_the_same(tmp_path, monkeypatch):
    import json
    import logic.metadata_store as ms
    monkeypatch.setattr(ms, "METADATA_ROOT", str(tmp_path / "m"))
    monkeypatch.setattr(ms, "LEGACY_METADATA_ROOT", str(tmp_path / "lm"))
    record = ms.default_metadata("2024-01-01", "2024-02-02")
    noted = dict(record, comments="note", frequency=12)
    ms.save_metadata(str(tmp_path / "d.json"), {"KAT": record, "TKOG": noted})

    raw = json.loads(open(ms._metadata_file_for(str(tmp_path / "d.json")), encoding="utf-8").read())
    assert raw["KAT"] == {"date_added": "2024-01-01", "modified": "2024-02-02"}
    assert raw["TKOG"]["comments"] == "note" and raw["TKOG"]["frequency"] == 12

    loaded = ms.load_metadata(str(tmp_path / "d.json"))
    for steno, original in (("KAT", record), ("TKOG", noted)):
        for field, value in original.items():
            assert loaded[steno].get(field, ms._OMIT_WHEN_DEFAULT.get(field)) == value
