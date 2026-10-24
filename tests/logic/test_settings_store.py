import logic.settings_store as settings_store


def test_settings_are_cached_and_returned_as_copies(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_store, "SETTINGS_PATH", str(path))
    monkeypatch.setattr(settings_store, "LEGACY_SETTINGS_PATH", str(tmp_path / "old.json"))

    settings_store.save_settings({"open_tabs": ["a.json"]})
    path.write_text('{"open_tabs": ["changed on disk"]}', encoding="utf-8")
    loaded = settings_store.load_settings()
    assert loaded == {"open_tabs": ["a.json"]}, "served from memory after a save"

    loaded["open_tabs"].append("b.json")
    assert settings_store.load_settings() == {"open_tabs": ["a.json"]}, "callers get copies"


def test_a_new_settings_path_is_read_from_disk(tmp_path, monkeypatch):
    path = tmp_path / "other.json"
    path.write_text('{"theme": "light"}', encoding="utf-8")
    monkeypatch.setattr(settings_store, "SETTINGS_PATH", str(path))
    monkeypatch.setattr(settings_store, "LEGACY_SETTINGS_PATH", str(tmp_path / "old.json"))

    assert settings_store.load_settings() == {"theme": "light"}
