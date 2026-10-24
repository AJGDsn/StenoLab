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


# --- Cached display rows and sort order ------------------------------------

def shown(tab, column):
    """Values the table currently shows in one column, top to bottom."""
    idx = tab.column_order.index(column)
    return [row[idx] for row in tab.sheet.get_sheet_data()]


def test_table_shows_edits_in_sorted_position_and_undo_restores_them(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat"), ("TKOG", "dog"), ("PWEUFRD", "bird")])
    assert shown(tab, "english") == ["bird", "cat", "dog"]

    edit(tab, next(e for e in tab.entries if e["english"] == "bird"), english="zebra")
    assert shown(tab, "english") == ["cat", "dog", "zebra"]

    tab.undo()
    assert shown(tab, "english") == ["bird", "cat", "dog"]


def test_changing_shared_metadata_redraws_every_row_on_that_steno(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat"), ("KAT", "kat")])
    entry = tab.entries[0]
    tab._select_rows([tab.filtered_entries.index(entry)])
    tab._open_edit_dialog(entry)
    dlg = [w for w in tab.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    next(w for w in _widgets(dlg) if w.winfo_class() == "Text").insert("1.0", "shared note")
    save_dialog(tab)

    assert shown(tab, "comments") == ["shared note", "shared note"]


def test_sort_order_survives_searching_and_clearing(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat"), ("TKOG", "dog"), ("KAUT", "caught")])
    tab._sort_by("steno")
    assert shown(tab, "steno") == ["KAT", "KAUT", "TKOG"]
    tab._sort_by("steno")  # second click reverses
    assert shown(tab, "steno") == ["TKOG", "KAUT", "KAT"]

    config = dict(tab.searchbar.get_config(), text_query="ca")
    tab.apply_search(config)
    assert shown(tab, "steno") == ["KAUT", "KAT"]
    tab.apply_search(dict(config, text_query=""))
    assert shown(tab, "steno") == ["TKOG", "KAUT", "KAT"]


def test_toggling_the_frequency_column_rebuilds_rows(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat")],
                   {"KAT": dict(NOTE)})
    width = len(tab.sheet.get_sheet_data()[0])
    tab.show_freq_column.set(True)
    tab._apply_freq_column(True)
    try:
        assert len(tab.sheet.get_sheet_data()[0]) == width + 1
        assert shown(tab, "F") == ["7"]
    finally:
        tab.show_freq_column.set(False)
        tab._apply_freq_column(False)


def test_bulk_metadata_change_shows_after_invalidate_all(root, tmp_path):
    tab = make_tab(root, tmp_path, [("KAT", "cat")])
    tab.metadata["KAT"]["brief"] = True   # as frequency import does, in place
    tab.invalidate_all_cached()
    tab._apply_filters()
    assert shown(tab, "B") == ["✓"]


def test_fast_text_search_ignores_case_and_padding(root, tmp_path):
    # The fast path compares cached lowered, stripped translations; null
    # translations count as empty.
    pairs = [("KAT", "Cat"), ("KAUT", " caught "), ("TKOG", "dog"), ("SKAT", "scat"),
             ("TPHUL", None)]
    tab = make_tab(root, tmp_path, pairs)
    for method, query, expected in (
        ("Begins With", "ca", {"KAT", "KAUT"}),
        ("Contains", "at", {"KAT", "SKAT"}),
        ("Ends With", "ght", {"KAUT"}),
    ):
        tab.apply_search(dict(tab.searchbar.get_config(), text_query=query, text_method=method))
        assert {e["steno"] for e in tab.filtered_entries} == expected

    # After an edit the cache is rebuilt, so new text is searchable.
    tab.apply_search(dict(tab.searchbar.get_config(), text_query=""))
    edit(tab, next(e for e in tab.entries if e["steno"] == "TKOG"), english="cart")
    tab.apply_search(dict(tab.searchbar.get_config(), text_query="car", text_method="Begins With"))
    assert {e["steno"] for e in tab.filtered_entries} == {"TKOG"}


@pytest.mark.parametrize("column", ["english", "steno", "W", "comments", "B"])
@pytest.mark.parametrize("reverse", [False, True])
def test_incremental_sort_order_matches_a_full_sort(root, tmp_path, column, reverse):
    import random
    rng = random.Random(f"{column}{reverse}")
    words = ["cat", "dog", "bird", "a b", "Zed", "echo", "fox", "go on", "hat", "ink"]
    tab = make_tab(root, tmp_path, [(f"S{i}", rng.choice(words)) for i in range(40)])
    tab.sort_column, tab.sort_reverse = column, reverse
    tab._sorted_entries = None

    for _ in range(60):
        action = rng.choice(["add", "edit", "delete", "undo", "redo", "meta"])
        if action == "add":
            change = tab._begin_change("Add")
            steno = f"S{rng.randrange(60)}"
            change.add({"steno": steno, "english": rng.choice(words)})
            if steno not in tab.metadata:
                change.set_meta(steno, metadata_store.default_metadata("2020-01-01", "2020-01-01"))
            change.commit()
        elif action in ("edit", "meta") and tab.entries:
            entry = rng.choice(tab.entries)
            change = tab._begin_change("Edit")
            if action == "edit":
                change.update(entry, english=rng.choice(words))
            meta = dict(tab.metadata.get(entry["steno"]) or {})
            meta.update(comments=rng.choice(["", "x", "note"]), brief=rng.random() < 0.5)
            change.set_meta(entry["steno"], meta)
            change.commit()
        elif action == "delete" and tab.entries:
            change = tab._begin_change("Delete")
            change.remove([rng.choice(tab.entries)])
            change.commit()
        elif action == "undo":
            tab.undo()
        elif action == "redo":
            tab.redo()

        key = tab._sort_key(column)
        ordered = tab._entries_in_sort_order()
        assert sorted(map(id, ordered)) == sorted(map(id, tab.entries))
        keys = [key(e) for e in ordered]
        assert keys == sorted(keys, reverse=reverse)


# --- Following a selection across tabs ---------------------------------------

def select_cell(tab, entry, column):
    tab.sheet.deselect("all")
    tab.sheet.select_cell(tab.filtered_entries.index(entry), tab.column_order.index(column))


def selected(tab):
    sel = tab.sheet.get_currently_selected()
    return (tab.filtered_entries[sel.row]["steno"], sel.type_,
            tab.column_order[sel.column]) if sel else None


def test_follow_matches_translation_or_steno_by_selected_cell(root, tmp_path):
    source = make_tab(root, tmp_path, [("KAT", "cat"), ("TKOG", "Dog")])
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    target = make_tab(root, other_dir, [("KA*T", "CAT"), ("TKOEG", "dogs"), ("TKOG", "hound")])

    select_cell(source, source.entries[0], "english")
    assert target.follow(source.follow_target())
    assert selected(target) == ("KA*T", "cells", "english"), "exact match ignoring case"

    select_cell(source, source.entries[1], "english")
    target.follow(source.follow_target())
    assert selected(target) == ("TKOEG", "cells", "english"), "falls back to begins-with"

    select_cell(source, source.entries[1], "steno")
    target.follow(source.follow_target())
    assert selected(target) == ("TKOG", "cells", "steno"), "a steno cell matches by steno"

    source._select_rows([source.filtered_entries.index(source.entries[0])])
    target.follow(source.follow_target())
    assert selected(target)[:2] == ("KA*T", "rows"), "a whole row matches by translation"


def test_follow_searches_only_visible_rows_and_leaves_state_when_unmatched(root, tmp_path):
    source = make_tab(root, tmp_path, [("KAT", "cat")])
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    target = make_tab(root, other_dir, [("KAT", "cat"), ("TKOG", "dog")])
    target.apply_search(dict(target.searchbar.get_config(), text_query="dog"))
    target.sheet.select_cell(0, 0)

    select_cell(source, source.entries[0], "english")
    assert not target.follow(source.follow_target())
    assert target.search_config["text_query"] == "dog", "search left as found"
    assert [e["steno"] for e in target.filtered_entries] == ["TKOG"]
    assert selected(target) == ("TKOG", "cells", "steno"), "selection left as found"
