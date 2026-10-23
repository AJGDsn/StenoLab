from ui.dictionary_tab import DictionaryTab


def test_default_column_order_keeps_metadata_columns_visible():
    assert DictionaryTab._make_column_order(show_freq=False, focus_mode=False) == [
        "steno",
        "english",
        "S",
        "W",
        "B",
        "added",
        "modified",
        "comments",
    ]
    assert DictionaryTab._make_column_order(show_freq=True, focus_mode=False) == [
        "steno",
        "english",
        "S",
        "W",
        "B",
        "F",
        "added",
        "modified",
        "comments",
    ]


def test_focus_column_order_keeps_daily_editing_columns_compact():
    assert DictionaryTab._make_column_order(show_freq=False, focus_mode=True) == [
        "steno",
        "english",
        "B",
    ]
    assert DictionaryTab._make_column_order(show_freq=True, focus_mode=True) == [
        "steno",
        "english",
        "B",
        "F",
    ]


def test_entry_for_row_maps_directly_to_filtered_entries():
    # The virtualized sheet shows every filtered row, so a sheet row index
    # maps straight onto filtered_entries with no pagination offset.
    tab = object.__new__(DictionaryTab)
    tab.filtered_entries = [
        {"steno": f"S{i}", "english": f"word{i}"}
        for i in range(5)
    ]

    assert tab._entry_for_row(0) is tab.filtered_entries[0]
    assert tab._entry_for_row(4) is tab.filtered_entries[4]
    assert tab._entry_for_row(5) is None      # out of range (past the end)
    assert tab._entry_for_row(-1) is None     # out of range (before the start)
