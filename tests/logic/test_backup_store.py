import time

import pytest

import logic.backup_store as backup_store
import logic.metadata_store as metadata_store


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_store, "BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setattr(backup_store, "LEGACY_BACKUP_ROOT", str(tmp_path / "legacy-backups"))
    monkeypatch.setattr(metadata_store, "METADATA_ROOT", str(tmp_path / "metadata"))
    monkeypatch.setattr(metadata_store, "LEGACY_METADATA_ROOT", str(tmp_path / "legacy"))


def _save_versions(path, versions):
    for v in versions:
        path.write_text('{"KAT": "%s"}' % v, encoding="utf-8")
        backup_store.backup_dictionary(str(path), kind="save")
        time.sleep(0.01)  # distinct millisecond timestamps


def test_restoring_the_oldest_save_backup_survives_the_safety_snapshot(tmp_path):
    dictionary = tmp_path / "main.json"
    _save_versions(dictionary, ["v1", "v2", "v3"])
    saves = [b for b in backup_store.list_backups(str(dictionary)) if b["kind"] == "save"]
    oldest = saves[-1]

    # Same order as main._restore_backup: read, snapshot, write.
    dict_bytes, meta_bytes = backup_store.read_backup_contents(oldest)
    backup_store.backup_dictionary(str(dictionary), kind="save")
    backup_store.write_restored_contents(str(dictionary), dict_bytes, meta_bytes)

    assert dictionary.read_text(encoding="utf-8") == '{"KAT": "v2"}'


def test_restoring_a_backup_without_metadata_removes_current_metadata(tmp_path):
    dictionary = tmp_path / "main.json"
    dictionary.write_text('{"KAT": "cat"}', encoding="utf-8")
    metadata_store.save_metadata(str(dictionary), {"KAT": {"comments": "stale"}})

    backup_store.write_restored_contents(str(dictionary), b'{"KAT": "old"}', None)

    assert dictionary.read_text(encoding="utf-8") == '{"KAT": "old"}'
    assert metadata_store.load_metadata(str(dictionary)) == {}
