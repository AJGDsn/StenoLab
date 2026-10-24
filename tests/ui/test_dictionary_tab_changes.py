"""
Regression tests for how edits change entries, metadata, undo and the
unsaved-changes flag.  They drive the real dialogs where the bugs were.
"""
import json
import tkinter as tk
from tkinter import messagebox

import pytest

import logic.backup_store as backup_store
import logic.metadata_store as metadata_store
import logic.settings_store as settings_store
from logic.dictionary_loader import load_dictionary_with_metadata
from ui.dictionary_tab import DictionaryTab
from ui.find_replace_dialog import FindReplaceDialog


@pytest.fixture(scope="module")
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(metadata_store, "METADATA_ROOT", str(tmp_path / "metadata"))
    monkeypatch.setattr(metadata_store, "LEGACY_METADATA_ROOT", str(tmp_path / "legacy"))
    monkeypatch.setattr(settings_store, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(settings_store, "LEGACY_SETTINGS_PATH", str(tmp_path / "old.json"))
    monkeypatch.setattr(backup_store, "BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)


def make_tab(root, tmp_path, pairs, metadata=None):
    """Open a dictionary written from (steno, english) pairs, like main.py does."""
    path = tmp_path / "dict.json"
    path.write_text(
        "{" + ",".join(f"{json.dumps(s)}: {json.dumps(e)}" for s, e in pairs) + "}",
        encoding="utf-8",
    )
    if metadata:
        metadata_store.save_metadata(str(path), metadata)
    entries, meta, _ = load_dictionary_with_metadata(str(path))
    tab = DictionaryTab(root, name="dict")
    tab.dict_path = str(path)
    tab.load_entries(entries, meta)
    tab.apply_search(tab.searchbar.get_config())
    return tab


def _widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _widgets(child)


def save_dialog(tab, steno=None, english=None):
    """Fill the open Add/Edit dialog and press Save."""
    dlg = [w for w in tab.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    widgets = list(_widgets(dlg))
    fields = [w for w in widgets if w.winfo_class() == "TEntry"]
    for field, value in zip(fields, (steno, english)):
        if value is not None:
            field.delete(0, "end")
            field.insert(0, value)
    next(w for w in widgets
         if w.winfo_class() == "TButton" and w.cget("text") == "Save").invoke()


def edit(tab, entry, **values):
    tab._select_rows([tab.filtered_entries.index(entry)])
    tab._open_edit_dialog(entry)
    save_dialog(tab, **values)


def add(tab, steno, english):
    tab._open_add_dialog()
    save_dialog(tab, steno=steno, english=english)


NOTE = {"comments": "keep me", "brief": True, "date_added": "2020-01-01",
        "modified": "2020-01-01", "bookmarked": False, "frequency": 7}


def test_edit_does_not_write_metadata_before_the_dictionary_is_saved(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat")], {"KAT": dict(NOTE)})

    edit(tab, tab.entries[0], steno="KAEUT")

    # Discarding now must leave the saved dictionary and metadata consistent.
    assert list(metadata_store.load_metadata(tab.dict_path)) == ["KAT"]
    assert tab._json_dirty

    assert tab.save_json()
    on_disk = metadata_store.load_metadata(tab.dict_path)
    assert list(on_disk) == ["KAEUT"]
    assert on_disk["KAEUT"]["comments"] == "keep me"


def test_restroking_one_of_two_shared_rows_keeps_the_others_metadata(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat"), ("KAT", "kat")], {"KAT": dict(NOTE)})

    edit(tab, tab.entries[1], steno="KA*T")

    assert tab.metadata["KAT"]["comments"] == "keep me"
    assert tab.metadata["KA*T"]["comments"] == "keep me"

    tab.undo()
    assert tab.metadata["KAT"] == NOTE
    assert "KA*T" not in tab.metadata
    assert [e["steno"] for e in tab.entries] == ["KAT", "KAT"]


def test_adding_an_existing_steno_keeps_its_metadata_and_undo_restores_it(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat")], {"KAT": dict(NOTE)})

    add(tab, "KAT", "Kat")

    assert tab.metadata["KAT"]["comments"] == "keep me"
    assert tab.metadata["KAT"]["brief"] is True
    assert tab.metadata["KAT"]["date_added"] == "2020-01-01"

    tab.undo()
    assert tab.metadata["KAT"] == NOTE
    assert len(tab.entries) == 1


def test_deleting_one_shared_row_keeps_metadata_until_the_last_goes(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat"), ("KAT", "kat")], {"KAT": dict(NOTE)})

    tab._select_rows([tab.filtered_entries.index(tab.entries[0])])
    tab.delete_selected(confirm=False)
    assert tab.metadata["KAT"] == NOTE

    tab._select_rows([0])
    tab.delete_selected(confirm=False)
    assert "KAT" not in tab.metadata

    tab.undo()
    tab.undo()
    assert [e["english"] for e in tab.entries] == ["cat", "kat"]
    assert tab.metadata["KAT"] == NOTE


def test_received_entries_are_undoable_and_keep_the_tab_unsaved(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat")])

    tab.receive_entries([({"steno": "TKOG", "english": "dog"}, {})])
    edit(tab, tab.entries[0], english="cats")
    tab.undo()

    assert tab._json_dirty, "the copied-in TKOG entry is still unsaved"
    tab.undo()
    assert [e["steno"] for e in tab.entries] == ["KAT"]
    assert not tab._json_dirty


def test_replace_all_is_one_undoable_change(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat"), ("KAT", "kat"), ("TKOG", "dog")],
                   {"KAT": dict(NOTE)})
    dlg = FindReplaceDialog(root, lambda: tab)
    try:
        dlg.field_var.set("Steno")
        dlg.find_var.set("KAT")
        dlg.replace_var.set("KA*T")
        dlg._replace_all()
    finally:
        dlg.destroy()

    assert sorted(e["steno"] for e in tab.entries) == ["KA*T", "KA*T", "TKOG"]
    assert tab.metadata["KA*T"]["comments"] == "keep me"
    assert "KAT" not in tab.metadata
    assert tab._json_dirty

    tab.undo()
    assert sorted(e["steno"] for e in tab.entries) == ["KAT", "KAT", "TKOG"]
    assert tab.metadata["KAT"] == NOTE
    assert "KA*T" not in tab.metadata
    assert not tab._json_dirty


def test_replacement_text_is_inserted_exactly_as_typed(root, tmp_path):
    tab = make_tab(root, tmp_path, [("-G", "testing")])
    dlg = FindReplaceDialog(root, lambda: tab)
    try:
        dlg.find_var.set("ing")
        dlg.replace_var.set(r"\d\1{^\n^}")
        dlg._replace_all()
    finally:
        dlg.destroy()

    assert tab.entries[0]["english"] == r"test\d\1{^\n^}"


def _error_text(tab):
    dlg = [w for w in tab.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    return next(w for w in _widgets(dlg) if w.winfo_class() == "TLabel"
                and "Save again" in str(w.cget("text")))


def test_translation_edit_of_a_palantype_entry_is_not_blocked(root, tmp_path):
    tab = make_tab(root, tmp_path, [("PRAI^S", "praise")])

    edit(tab, tab.entries[0], english="praises")

    assert tab.entries[0]["english"] == "praises"


def test_invalid_new_steno_is_saved_on_the_second_press(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat")])
    tab._select_rows([0])
    tab._open_edit_dialog(tab.entries[0])

    save_dialog(tab, steno="AKT")
    assert tab.entries[0]["steno"] == "KAT", "first press only warns"
    assert _error_text(tab)

    save_dialog(tab)
    assert tab.entries[0]["steno"] == "AKT"


def test_copy_menu_labels_use_tab_names(root, tmp_path):
    class App:
        tabs = {}
    first = make_tab(root, tmp_path, [("KAT", "cat")])
    second = DictionaryTab(root, name="main")
    second.dict_path = str(tmp_path / "a" / "main.json")
    third = DictionaryTab(root, name="main")
    third.dict_path = str(tmp_path / "b" / "main.json")
    App.tabs = {"k1": first, "k2": second, "k3": third}
    first.winfo_toplevel = lambda: App

    assert sorted(first._get_other_tabs()) == ["main  (a)", "main  (b)"]
