# ui/dictionary_tab.py
import bisect
import copy
import heapq
import os
import re
import tkinter as tk
from collections import Counter
from operator import itemgetter
from tkinter import ttk, messagebox
from datetime import datetime

from tksheet import Sheet

from logic.settings_store import load_settings, save_settings
from logic.metadata_store import (
    save_metadata, ensure_metadata, default_metadata, merge_metadata,
)
from logic.dictionary_writer import write_dictionary
from logic.undo_stack import UndoStack
from ui.searchbar import SearchBar
from ui.theme import C
from ui.tooltip import HoverTooltip, Tooltip


MAX_COMMENT_CHARS  = 40

WRITTEN_NUMBERS = frozenset({
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million",
    "billion", "trillion",
})

# Pre-compiled regexes used in the per-entry filter loop.  Compiling once at
# module load saves ~half the work for each filter pass on a large dictionary.
_DIGIT_RE = re.compile(r"\d")
_WORD_RE  = re.compile(r"[a-z]+")
_PUNCT_RE = re.compile(
    r"[\.,;:!\?\-\u2014\u2013'\"\(\)\[\]\{\}/\\&\*@#%\$\^\+=<>~\|`]"
)


def center_on_parent(dialog, parent):
    dialog.update_idletasks()
    pw, ph = parent.winfo_width(),  parent.winfo_height()
    px, py = parent.winfo_rootx(),  parent.winfo_rooty()
    dw, dh = dialog.winfo_width(),  dialog.winfo_height()
    dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")


def _style_dialog(dialog):
    dialog.configure(bg=C["bg_panel"])


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class _Descending:
    """Sort-key wrapper that orders values in reverse, so bisect can search
    a list sorted with reverse=True."""
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return other.value < self.value


class _Change:
    """
    One undoable edit to a tab, built up step by step and pushed onto the
    undo stack by commit().

    Every change to entries or metadata goes through one of these, so undo
    can always reverse it exactly and the unsaved-changes flag (which is
    derived from the undo stack) never misses an edit.  Metadata is keyed by
    steno and may be shared by several rows, so the before-state of each key
    is recorded the first time it is touched and restored as a whole.
    """

    def __init__(self, tab, label: str):
        self.tab = tab
        self.label = label
        if tab.metadata is None:
            tab.metadata = {}
        self._conflicts_before = set(tab.conflict_stenos)
        self.added: list = []
        self.removed: list = []     # (entry, original position)
        self._changed: dict = {}    # id(entry) -> (entry, values before)
        self._meta_before: dict = {}  # steno -> metadata copy, or None if absent

    def add(self, entry: dict) -> dict:
        self.tab.entries.append(entry)
        self.added.append(entry)
        return entry

    def remove(self, entries) -> None:
        """Remove entries by identity.  Call at most once per change."""
        targets = {id(e) for e in entries}
        kept = []
        for i, e in enumerate(self.tab.entries):
            if id(e) in targets:
                self.removed.append((e, i))
            else:
                kept.append(e)
        self.tab.entries = kept

    def update(self, entry: dict, **fields) -> None:
        if id(entry) not in self._changed:
            self._changed[id(entry)] = (entry, dict(entry))
        entry.update(fields)

    def old_values(self) -> list:
        """The values each updated entry had before this change."""
        return [old for _ref, old in self._changed.values()]

    def set_meta(self, steno: str, meta: dict) -> None:
        self._touch(steno)
        self.tab.metadata[steno] = meta

    def drop_unused_meta(self, stenos) -> None:
        """Delete metadata (and bookmarks) for stenos no row uses any more."""
        in_use = {e["steno"] for e in self.tab.entries}
        for steno in set(stenos) - in_use:
            if steno in self.tab.metadata:
                self._touch(steno)
                del self.tab.metadata[steno]
            self.tab.bookmarked_stenos.discard(steno)

    def _touch(self, steno: str) -> None:
        if steno not in self._meta_before:
            current = self.tab.metadata.get(steno)
            self._meta_before[steno] = copy.deepcopy(current) if current is not None else None

    def commit(self) -> bool:
        """Record the change for undo and refresh the tab.  False if nothing changed."""
        if not (self.added or self.removed or self._changed or self._meta_before):
            return False
        metadata = self.tab.metadata
        frame = {
            "label":       self.label,
            "added":       list(self.added),
            "removed":     list(self.removed),
            "changed":     [(ref, old, dict(ref)) for ref, old in self._changed.values()],
            "meta_before": self._meta_before,
            "meta_after":  {
                k: copy.deepcopy(metadata[k]) if k in metadata else None
                for k in self._meta_before
            },
        }
        self.tab._undo_stack.push(frame)
        self.tab._metadata_dirty = True
        self.tab._invalidate_frame_cache(frame, "redo")
        self.tab._set_dirty(True)
        self.tab._after_entries_changed(self._conflicts_before)
        return True


class DictionaryTab(ttk.Frame):
    """Main dictionary workspace."""

    HEADINGS = {
        "steno":    "Steno",
        "english":  "Translation",
        "S":        "S",
        "W":        "W",
        "B":        "B",
        "F":        "F",
        "added":    "Added",
        "modified": "Modified",
        "comments": "Comments",
    }

    # Hover help for the cryptic single-letter columns.  Shown as a tooltip
    # whenever the user pauses over the column heading.
    COLUMN_TOOLTIPS = {
        "steno":    "Steno outline (key)",
        "english":  "Translation / output text",
        "S":        "Stroke count (number of '/' separated strokes)",
        "W":        "Word count in the translation",
        "B":        "Brief: ✓ if this outline is marked as a brief",
        "F":        "Frequency score for this word (higher = more common)",
        "added":    "Date this entry was first added",
        "modified": "Date this entry was last modified",
        "comments": "Notes you've added to this entry",
    }

    DEFAULT_WIDTHS = {
        "steno":    150,
        "english":  420,
        "S":        40,
        "W":        40,
        "B":        30,
        "F":        70,
        "added":    90,
        "modified": 90,
        "comments": 300,
    }

    # F (frequency) is not listed here — it is inserted after B dynamically
    # when the user enables "Show frequency column" in the filter panel.
    VIEW_COLUMNS = ["steno", "english", "S", "W"]
    FOCUS_COLUMNS = ["steno", "english", "B"]
    EDIT_COLUMNS = ["steno", "english", "S", "W", "B", "added", "modified", "comments"]

    def __init__(self, parent, name="Dictionary",
                 on_entries_changed=None,
                 on_filter_count_changed=None,
                 on_search_broadcast=None,
                 on_search_collapse_changed=None,
                 initial_search_collapsed=True):
        super().__init__(parent)
        self.name = name
        self.on_entries_changed   = on_entries_changed
        self._on_filter_count_changed = on_filter_count_changed
        self._on_search_broadcast = on_search_broadcast
        self._on_search_collapse_changed = on_search_collapse_changed
        self._initial_search_collapsed = bool(initial_search_collapsed)

        # Data
        self.entries          = []
        self.filtered_entries = []
        self.dict_path        = None
        self.metadata         = {}
        self._metadata_dirty  = False
        self._json_dirty      = False   # tracks unsaved edits; shown as * on tab title

        # Session-only state
        self.bookmarked_stenos: set = set()
        self.conflict_stenos:   set = set()

        # Row-index highlight sets for the current view (indices into
        # self.filtered_entries).  Recomputed on every _refresh_tree and
        # re-applied to the sheet together with any active find highlights.
        self._bm_rows:   list = []
        self._cf_rows:   list = []
        self._both_rows: list = []
        self._find_rows: list = []
        self._current_row = None   # row holding the selection, tinted
        self._fitted_flex = (None, -1)   # (column, width) set by _fit_flex_column

        # Undo / redo
        self._undo_stack = UndoStack()

        # Caches that keep large dictionaries fast; see _invalidate_cached.
        #   _row_cache:      id(entry) -> (entry, display row) for column_order
        #   _sorted_entries: every entry in the current sort order, or None
        #   _stats:          (brief count, frequency-matched count), or None
        #   _lowered_cache:  (_sorted_entries, their lowered translations)
        self._row_cache: dict = {}
        self._sorted_entries = None
        self._stats = None
        self._lowered_cache = None

        # Sorting
        self.sort_column  = "english"
        self.sort_reverse = False

        # Filters
        self.filter_has_comments        = tk.BooleanVar(value=False)
        self.filter_is_brief            = tk.BooleanVar(value=False)
        self.filter_bookmarked          = tk.BooleanVar(value=False)
        self.filter_capitalised         = tk.BooleanVar(value=False)
        self.filter_has_digits          = tk.BooleanVar(value=False)
        self.filter_has_written_numbers = tk.BooleanVar(value=False)
        self.filter_has_punctuation     = tk.BooleanVar(value=False)
        self.filter_conflicts           = tk.BooleanVar(value=False)

        # Settings (loaded once here; refreshed on tab activation)
        self.settings      = load_settings()
        self.column_widths = self.settings.get("column_widths", {})

        # Frequency filters
        self.filter_has_frequency  = tk.BooleanVar(value=False)
        self.filter_top_freq       = tk.BooleanVar(value=False)
        self.filter_top_freq_n_var = tk.StringVar(value="500")
        self.filter_top_freq_n_var.trace_add("write", lambda *_: self._apply_filters())
        # Frequency column display toggle (persisted in settings)
        show_freq = self.settings.get("show_freq_column", False)
        self.show_freq_column = tk.BooleanVar(value=show_freq)
        self.focus_mode = tk.BooleanVar(value=False)

        # Build the active column order, inserting F when the toggle is on
        self.column_order = self._make_column_order(show_freq, self.focus_mode.get())

        # Unified Search & Filters bar state.  Default collapsed so the
        # table gets maximum vertical space; the user can expand it when
        # they need to refine results.
        self.unified_expanded      = not bool(initial_search_collapsed)

        self.search_config = {}

        # Build — note the dictionary info bar is no longer drawn as a
        # permanent block above the table.  Its information lives in the
        # right-hand cluster of the unified bar (entry count + ⓘ popover).
        self._build_search_filter_panel()
        self._build_tree()
        self._update_sort_headings()
        self.bind("<<DictionaryTabActivated>>", self._on_activated)

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------
    def _on_activated(self, event=None):
        """Tab switch: sync column widths only — no row rebuild."""
        self.settings      = load_settings()
        self.column_widths = self.settings.get("column_widths", {})
        if hasattr(self, "sheet"):
            for i, col in enumerate(self.column_order):
                self.sheet.column_width(
                    i, self.column_widths.get(col, self.DEFAULT_WIDTHS[col]),
                    redraw=False,
                )
            self.sheet.refresh()
        self._update_sort_headings()
        self._fit_flex_column()

    # ------------------------------------------------------------------
    # Column order helpers
    # ------------------------------------------------------------------
    @classmethod
    def _make_column_order(cls, show_freq: bool, focus_mode: bool = False) -> list:
        """Return the active column list, inserting F where it reads naturally."""
        cols = list(cls.FOCUS_COLUMNS if focus_mode else cls.EDIT_COLUMNS)
        if show_freq:
            if "B" in cols:
                cols.insert(cols.index("B") + 1, "F")
            else:
                cols.append("F")
        return cols

    def _configure_columns(self):
        """Apply headers, widths and alignment for the current column_order."""
        if not hasattr(self, "sheet"):
            return
        # reset_col_positions=True rebuilds the column-position array to exactly
        # len(column_order); without it, shrinking the column count (focus mode)
        # leaves stale slots that draw as empty, letter-headed columns.
        self.sheet.headers([self.HEADINGS[c] for c in self.column_order],
                           reset_col_positions=True)
        for i, col in enumerate(self.column_order):
            width = self.column_widths.get(col, self.DEFAULT_WIDTHS[col])
            self.sheet.column_width(i, width, redraw=False)
        # Left-align the text columns; centre the short metric columns.
        left   = [i for i, c in enumerate(self.column_order)
                  if c in ("steno", "english", "comments")]
        centre = [i for i, c in enumerate(self.column_order)
                  if c not in ("steno", "english", "comments")]
        try:
            if left:
                self.sheet.align_columns(left, align="w", align_header=True)
            if centre:
                self.sheet.align_columns(centre, align="c", align_header=True)
        except Exception:
            pass
        self._update_sort_headings()
        self._fit_flex_column()

    # Smallest width the flexible Comments column is squeezed to before the
    # table scrolls sideways instead.
    _MIN_FLEX_COMMENTS_WIDTH = 80

    def _flex_column(self) -> str | None:
        """The column that absorbs spare or missing width: Comments, or
        Translation in layouts without Comments (Focus mode)."""
        for col in ("comments", "english"):
            if col in self.column_order:
                return col
        return None

    def _fit_flex_column(self, _event=None):
        """
        Keep the table exactly as wide as the window by resizing the
        flexible column (_flex_column): widening another column takes the
        space from it, narrowing one gives the space to it, and so does
        resizing the window.  Its fitted width is never saved, so the
        other columns' widths are what persist.
        """
        flex = self._flex_column() if hasattr(self, "sheet") else None
        if flex is None:
            return
        available = self.sheet.MT.winfo_width()
        if available <= 1:
            return  # not laid out yet; the <Configure> binding retries
        widths = self.sheet.get_column_widths()
        idx = self.column_order.index(flex)
        if idx >= len(widths):
            return
        others = sum(w for i, w in enumerate(widths) if i != idx)
        if flex == "comments":
            minimum = self._MIN_FLEX_COMMENTS_WIDTH
        else:
            minimum = self.column_widths.get(flex, self.DEFAULT_WIDTHS[flex])
        target = int(max(minimum, available - others - 2))
        if abs(widths[idx] - target) > 1:
            self.sheet.column_width(idx, target, redraw=True)
        self._fitted_flex = (flex, target)

    def _toggle_freq_column(self):
        """Show or hide the F column; sync to all other open tabs and persist."""
        show = self.show_freq_column.get()

        # Persist
        settings = load_settings()
        settings["show_freq_column"] = show
        save_settings(settings)

        # Apply to this tab
        self._apply_freq_column(show)

        # Sync every other open tab so all tabs stay consistent
        app = self.winfo_toplevel()
        if hasattr(app, "tabs"):
            for tab in app.tabs.values():
                if tab is not self and hasattr(tab, "show_freq_column"):
                    tab.show_freq_column.set(show)
                    tab._apply_freq_column(show)

    def _apply_freq_column(self, show: bool):
        """Rebuild column_order and reconfigure the sheet accordingly."""
        self.column_order = self._make_column_order(show, self.focus_mode.get())
        self._row_cache.clear()
        # Load the new-width data first so the sheet knows the new column
        # count, then (re)apply headers / widths / alignment.
        self._refresh_tree(reset_columns=True)
        self._configure_columns()

    def _toggle_focus_mode(self):
        """Switch between the full editing table and a compact daily-editing view."""
        self.column_order = self._make_column_order(
            self.show_freq_column.get(), self.focus_mode.get()
        )
        self._row_cache.clear()
        self._refresh_tree(reset_columns=True)
        self._configure_columns()
        self._refresh_dictionary_header()

    # ------------------------------------------------------------------
    # Dirty / unsaved-changes indicator
    # ------------------------------------------------------------------
    def _set_dirty(self, dirty: bool = True):
        """Mark the tab as having unsaved changes and update the tab title."""
        if dirty == self._json_dirty:
            return
        self._json_dirty = dirty
        try:
            nb    = self.nametowidget(self.winfo_parent())
            # A leading bullet reads as "modified" more clearly than a
            # trailing asterisk and is the convention most editors use.
            title = ("● " if dirty else "") + self.name
            nb.tab(self, text=title)
        except Exception:
            pass
        self._refresh_dictionary_header()

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------
    def _rebuild_conflict_stenos(self):
        """Flag steno keys that appear more than once within this dictionary."""
        counts = Counter(map(itemgetter("steno"), self.entries))
        self.conflict_stenos = {s for s, n in counts.items() if n > 1}

    # ------------------------------------------------------------------
    # Caches
    # ------------------------------------------------------------------
    def _invalidate_cached(self, entries=(), stenos=(), gone=()):
        """
        Forget cached state made stale by a change.

        A row shows its entry plus the metadata of its steno, which other
        rows may share, so rows are dropped both for the given entries and
        for every entry on the given stenos.  `gone` lists entries among
        `entries` that are no longer in the dictionary.  The sort order and
        the header statistics are brought up to date too.
        """
        cache = self._row_cache
        affected = {id(e): e for e in entries}
        for e in entries:
            cache.pop(id(e), None)
        stenos = set(stenos)
        sort_uses_metadata = self.sort_column in self._METADATA_SORT_COLUMNS
        if stenos and (cache or sort_uses_metadata):
            for e in self.entries:
                if e["steno"] in stenos:
                    cache.pop(id(e), None)
                    if sort_uses_metadata:
                        affected[id(e)] = e
        self._resort_entries(list(affected.values()), {id(e) for e in gone})
        self._stats = None

    _METADATA_SORT_COLUMNS = frozenset({"B", "F", "added", "modified", "comments"})
    _INCREMENTAL_SORT_LIMIT = 2000

    def _resort_entries(self, affected: list, gone_ids: set) -> None:
        """
        Bring the cached sort order up to date after `affected` entries were
        added, removed or changed (`gone_ids`: the removed ones).  A small
        change takes each affected entry out and puts the rest back by binary
        search,
        rather than re-sorting everything; a large one drops the order so it
        is rebuilt in full.
        """
        ordered = self._sorted_entries
        if ordered is None:
            return
        if len(affected) > self._INCREMENTAL_SORT_LIMIT:
            self._sorted_entries = None
            return
        ids = {id(e) for e in affected}
        kept = [e for e in ordered if id(e) not in ids]
        key = self._sort_key(self.sort_column)
        if self.sort_reverse:
            base = key
            key = lambda e: _Descending(base(e))  # noqa: E731
        for e in affected:
            if id(e) not in gone_ids:
                kept.insert(bisect.bisect_right(kept, key(e), key=key), e)
        self._sorted_entries = kept

    def invalidate_all_cached(self):
        """Forget every cached row, e.g. after metadata changed wholesale
        (frequency import) outside a recorded change."""
        self._row_cache.clear()
        self._sorted_entries = None
        self._stats = None

    # ------------------------------------------------------------------
    # Find highlight support (used by FindReplaceDialog)
    # ------------------------------------------------------------------
    def apply_find_highlights(self, rows):
        """Highlight the given filtered-row indices as find matches."""
        self._find_rows = sorted(r for r in rows
                                 if 0 <= r < len(self.filtered_entries))
        self._apply_row_highlights()

    def clear_find_highlights(self):
        """Remove all find-match highlighting."""
        self._find_rows = []
        self._apply_row_highlights()

    # ------------------------------------------------------------------
    # Dictionary info (no longer a permanent header — info lives in the
    # right-hand cluster of the unified Search & Filters bar and the
    # popover that opens from the ⓘ chip).
    # ------------------------------------------------------------------
    def _refresh_dictionary_header(self):
        """Refresh the unified bar's entry-count chip and cached info
        strings.  Kept as ``_refresh_dictionary_header`` because dozens of
        callers reach it from outside this file."""
        if not hasattr(self, "entry_count_var"):
            return

        total = len(self.entries)
        conflict_count = len(self.conflict_stenos)

        # The entry-count chip is owned by _apply_filters, which knows
        # both the filtered ("X of Y") and unfiltered ("N entries") forms.
        # Only seed it here if the filter hasn't yet had a chance to run.
        if not (self.entry_count_var.get() or "").strip():
            self.entry_count_var.set(
                f"{total:,} entr{'y' if total == 1 else 'ies'}"
            )

        # Conflict chip - shown only when there are actual conflicts; uses
        # the danger style so it stands out.
        if hasattr(self, "conflict_chip"):
            if conflict_count:
                text = f"{conflict_count:,} conflict{'s' if conflict_count != 1 else ''}"
                self.conflict_chip.configure(text=text, style="HeaderDanger.TLabel")
                if not self.conflict_chip.winfo_ismapped():
                    self.conflict_chip.pack(side=tk.LEFT, padx=(0, 6),
                                            before=self.saved_chip)
            else:
                if self.conflict_chip.winfo_ismapped():
                    self.conflict_chip.pack_forget()

        # Saved / unsaved state chip
        if hasattr(self, "saved_chip"):
            if self._json_dirty:
                self.saved_chip.configure(text="Unsaved", style="HeaderWarning.TLabel")
            else:
                self.saved_chip.configure(text="Saved", style="HeaderSuccess.TLabel")

    def _info_tooltip_text(self) -> str:
        """Path and statistics for the count chip's tooltip.  Built when the
        tooltip appears, so the brief / frequency counts (a pass over every
        entry) are only computed when someone looks, then cached."""
        total = len(self.entries)
        if self._stats is None:
            metadata = self.metadata or {}
            empty = {}
            brief_count = freq_count = 0
            for entry in self.entries:
                meta = metadata.get(entry["steno"], empty)
                if meta.get("brief", False):
                    brief_count += 1
                if meta.get("frequency", 0):
                    freq_count += 1
            self._stats = (brief_count, freq_count)
        brief_count, freq_count = self._stats
        freq_pct = round((freq_count / total) * 100) if total else 0
        path = self.dict_path or "Unsaved dictionary"
        return (
            f"{path}\n\n"
            f"{total:,} entries\n"
            f"{brief_count:,} briefs\n"
            f"{len(self.conflict_stenos):,} conflicts\n"
            f"{freq_pct}% frequency matched"
        )

    # ------------------------------------------------------------------
    # Unified Search & Filters bar
    # ------------------------------------------------------------------
    def _build_search_filter_panel(self):
        """One collapsible bar that contains the search inputs, filter
        checkboxes, active chips for both, and the entry-count chip.

        Layout:

            Header (always visible):
                ▶/▼  Search & Filters   [chips ...]      [123 entries] [Unsaved]
            Body (shown when expanded):
                ┌ Search ────────────────────────────────────────────────┐
                │ Text:  [Method ▼] [____________]  [ ] Match case       │
                │ Steno: [Method ▼] [____________]  [ ] Whole strokes    │
                │ Scope: [Current Dictionary ▼]                  [Clear] │
                └────────────────────────────────────────────────────────┘
                ┌ Filters ───────────────────────────────────────────────┐
                │ [ ] Has comments  [ ] Is brief  [ ] Bookmarked …       │
                │ [ ] Capitalised   [ ] Digits   [ ] Punctuation …       │
                │ [ ] Has freq  [ ] Top [500] entries  [ ] Show F col    │
                └────────────────────────────────────────────────────────┘
        """
        # Container
        self.unified_container = ttk.Frame(self, style="UnifiedBar.TFrame")
        self.unified_container.pack(fill=tk.X, pady=(0, 6))

        # ---------------------------------------------------------------
        # Header
        # ---------------------------------------------------------------
        self.unified_header = ttk.Frame(self.unified_container,
                                        style="UnifiedBarInner.TFrame")
        self.unified_header.pack(fill=tk.X, padx=10, pady=(6, 6))
        self.unified_header.columnconfigure(0, weight=0)
        self.unified_header.columnconfigure(1, weight=1)
        self.unified_header.columnconfigure(2, weight=0)
        self.unified_header.bind("<Button-1>", self._toggle_unified)

        arrow = "▼" if self.unified_expanded else "▶"
        self.unified_label = ttk.Label(
            self.unified_header,
            text=f"{arrow}  Search & Filters",
            style="Disclosure.TLabel",
            padding=(2, 2),
            cursor="hand2",
        )
        self.unified_label.grid(row=0, column=0, sticky="w")
        self.unified_label.bind("<Button-1>", self._toggle_unified)

        # Active chip strip (search + filter chips combined)
        self.active_chip_frame = ttk.Frame(self.unified_header,
                                           style="UnifiedBarInner.TFrame")
        self.active_chip_frame.grid(row=0, column=1, sticky="w", padx=(10, 12))

        # Right-hand cluster: count chip + saved chip
        right = ttk.Frame(self.unified_header, style="UnifiedBarInner.TFrame")
        right.grid(row=0, column=2, sticky="e")

        self.saved_chip = ttk.Label(right, text="Saved", style="HeaderSubtle.TLabel")
        self.saved_chip.pack(side=tk.RIGHT, padx=(0, 8))

        # Conflict chip (hidden unless > 0 — packed in _refresh_dictionary_header)
        self.conflict_chip = ttk.Label(right, text="", style="HeaderDanger.TLabel")

        self.entry_count_var = tk.StringVar(value="0 entries")
        self.count_chip = ttk.Label(
            right, textvariable=self.entry_count_var, style="HeaderChip.TLabel"
        )
        self.count_chip.pack(side=tk.RIGHT, padx=(0, 8))
        self._count_tooltip = Tooltip(self.count_chip, self._info_tooltip_text)

        # ---------------------------------------------------------------
        # Body (animated)
        # ---------------------------------------------------------------
        self.unified_body = ttk.Frame(self.unified_container,
                                      style="UnifiedBarInner.TFrame")
        # Note: not packed until _open_immediately or _animate_unified runs.

        # ----- Search inputs -----
        self.searchbar = SearchBar(
            self.unified_body,
            on_search=self._on_local_search_changed,
        )
        self.searchbar.pack(fill=tk.X, padx=10, pady=(2, 0))

        ttk.Separator(self.unified_body, orient="horizontal").pack(
            fill=tk.X, padx=10, pady=(8, 8),
        )

        # ----- Filter checkboxes (grid keeps columns aligned) -----
        filters_box = ttk.Frame(self.unified_body, style="UnifiedBarInner.TFrame")
        filters_box.pack(fill=tk.X, padx=10, pady=(0, 10))
        for col in range(4):
            filters_box.columnconfigure(col, weight=1, uniform="filter_col")

        check_style = "UnifiedBar.TCheckbutton"

        def group(column, title):
            """A labelled column of checkboxes; returns its frame."""
            frame = ttk.Frame(filters_box, style="UnifiedBarInner.TFrame")
            frame.grid(row=0, column=column, sticky="nw", padx=(0, 14))
            ttk.Label(frame, text=title.upper(), style="FilterGroup.TLabel").pack(
                anchor="w", pady=(0, 2))
            return frame

        def check(parent, text, variable, command=self._apply_filters):
            ttk.Checkbutton(
                parent, text=text, variable=variable,
                style=check_style, command=command,
            ).pack(anchor="w", pady=3)

        entries = group(0, "Entries")
        check(entries, "Has comments", self.filter_has_comments)
        check(entries, "Is brief", self.filter_is_brief)
        check(entries, "Bookmarked", self.filter_bookmarked)
        check(entries, "Conflicts", self.filter_conflicts)

        text = group(1, "Translation")
        check(text, "Capitalised", self.filter_capitalised)
        check(text, "Numbers (0–9)", self.filter_has_digits)
        check(text, "Numbers (written)", self.filter_has_written_numbers)
        check(text, "Punctuation", self.filter_has_punctuation)

        frequency = group(2, "Frequency")
        check(frequency, "Has frequency", self.filter_has_frequency)
        top_group = ttk.Frame(frequency, style="UnifiedBarInner.TFrame")
        top_group.pack(anchor="w", pady=3)
        ttk.Checkbutton(
            top_group, text="Top", variable=self.filter_top_freq,
            style=check_style, command=self._apply_filters,
        ).pack(side=tk.LEFT)
        ttk.Entry(
            top_group, textvariable=self.filter_top_freq_n_var, width=5,
        ).pack(side=tk.LEFT, padx=(6, 6))
        ttk.Label(
            top_group, text="by frequency", style="UnifiedBar.TLabel",
        ).pack(side=tk.LEFT)

        # Not filters: these change what the table shows, not which rows.
        view = group(3, "View")
        check(view, "Focus mode", self.focus_mode, self._toggle_focus_mode)
        check(view, "Show frequency column", self.show_freq_column,
              self._toggle_freq_column)

        # Establish initial expanded / collapsed visual.
        if self.unified_expanded:
            self.unified_body.pack(fill=tk.X, padx=0, pady=(0, 0))
        else:
            self.unified_label.config(text="▶  Search & Filters")
        self._refresh_dictionary_header()

    def _toggle_unified(self, _event=None):
        if self.unified_expanded:
            self.collapse_unified()
        else:
            self.expand_unified()

    def expand_unified(self, focus_field: str | None = None,
                       append_char: str | None = None):
        if not self.unified_expanded:
            self.unified_expanded = True
            self.unified_label.config(text="▼  Search & Filters")
            if not self.unified_body.winfo_ismapped():
                self.unified_body.pack(fill=tk.X, padx=0, pady=(0, 0))
            self._notify_collapse_state(False)
        if focus_field == "text":
            self.searchbar.focus_text_entry(append_char=append_char)
        elif focus_field == "steno":
            self.searchbar.focus_steno_entry(append_char=append_char)

    def collapse_unified(self):
        if not self.unified_expanded:
            return
        # Flush any pending debounced search before the panel disappears
        if hasattr(self, "searchbar"):
            self.searchbar.flush_pending()
        self.unified_expanded = False
        self.unified_label.config(text="▶  Search & Filters")
        if self.unified_body.winfo_ismapped():
            self.unified_body.pack_forget()
        self._notify_collapse_state(True)

    def _notify_collapse_state(self, collapsed: bool):
        if callable(self._on_search_collapse_changed):
            try:
                self._on_search_collapse_changed(collapsed)
            except Exception:
                pass

    def _on_local_search_changed(self, config):
        """Apply locally, then broadcast if scope is 'All Dictionaries'."""
        self.search_config = config or {}
        self._apply_filters()
        if (config or {}).get("scope") == "All Dictionaries" and callable(
            self._on_search_broadcast
        ):
            try:
                self._on_search_broadcast(self, config)
            except Exception:
                pass

    def set_search_quietly(self, config: dict):
        """Receive a sibling's broadcast: mirror its query inputs and re-filter."""
        if not hasattr(self, "searchbar"):
            return
        self.searchbar.set_config_quietly(config or {})
        merged = self.searchbar.get_config()
        self.search_config = merged
        self._apply_filters()

    def type_ahead(self, char=None, backspace=False) -> bool:
        """
        Route a keystroke typed outside any input field into the text search.

        With the Search & Filters panel open, the text field takes focus and
        the character.  With it closed, the panel stays closed: the query is
        edited directly (the header's search chip shows it) and focus stays
        on the table, so further keystrokes keep arriving here.  Returns True
        if the keystroke was used.
        """
        if not hasattr(self, "searchbar"):
            return False
        if self.unified_expanded:
            if backspace:
                return False
            self.searchbar.focus_text_entry(append_char=char)
            return True
        query = self.searchbar.text_query_var
        if backspace:
            if not query.get():
                return False
            query.set(query.get()[:-1])
        else:
            query.set(query.get() + char)
        return True

    def _update_no_match_hint(self, *, showing: int, search_active: bool):
        """Append a "no matches" indicator + a Clear-search affordance to
        the active chip strip.  Runs after ``_refresh_filter_chips`` so
        the hint always sits to the right of the chips."""
        if not hasattr(self, "active_chip_frame"):
            return
        if not (search_active and showing == 0):
            return
        ttk.Label(
            self.active_chip_frame,
            text="no matches",
            style="WarningBadge.TLabel",
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            self.active_chip_frame,
            text="Clear search ✕",
            style="Chip.TButton",
            command=self.searchbar.clear,
        ).pack(side=tk.LEFT, padx=(0, 6))

    def _clear_active_filters_local(self):
        """Clear all active filter toggles on this tab."""
        for attr in (
            "filter_has_comments", "filter_is_brief", "filter_bookmarked",
            "filter_capitalised", "filter_has_digits", "filter_has_written_numbers",
            "filter_has_punctuation", "filter_conflicts",
            "filter_has_frequency", "filter_top_freq",
        ):
            var = getattr(self, attr, None)
            if var is not None:
                try:
                    var.set(False)
                except Exception:
                    pass
        self._apply_filters()

    def _filter_chip_defs(self):
        return [
            ("Comments", self.filter_has_comments),
            ("Brief", self.filter_is_brief),
            ("Bookmarked", self.filter_bookmarked),
            ("Conflicts", self.filter_conflicts),
            ("Capitalised", self.filter_capitalised),
            ("Digits", self.filter_has_digits),
            ("Written numbers", self.filter_has_written_numbers),
            ("Punctuation", self.filter_has_punctuation),
            ("Frequency", self.filter_has_frequency),
            (f"Top {self.filter_top_freq_n_var.get().strip() or '500'}", self.filter_top_freq),
        ]

    def _refresh_filter_chips(self):
        """Render the combined search + filter active-chip row inside
        the unified bar's header.  Clears all children unconditionally —
        any no-match hint will be re-added afterwards by
        ``_update_no_match_hint`` so it always appears to the right of
        the chips."""
        if not hasattr(self, "active_chip_frame"):
            return
        for child in list(self.active_chip_frame.winfo_children()):
            child.destroy()

        search_chips = self.searchbar.chip_defs() if hasattr(self, "searchbar") else []
        filter_chips = [(label, lambda v=var: self._clear_filter_var(v))
                        for label, var in self._filter_chip_defs() if var.get()]

        chips = search_chips + filter_chips
        if not chips:
            return

        for label, callback in chips:
            btn = ttk.Button(
                self.active_chip_frame,
                text=f"{label} ✕",
                style="Chip.TButton",
                command=callback,
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))

    def _clear_filter_var(self, var):
        var.set(False)
        self._apply_filters()

    # ------------------------------------------------------------------
    # Treeview
    # ------------------------------------------------------------------
    def _build_tree(self):
        # Conflict warning banner - hidden until a conflict is detected on
        # add/edit/receive.  Sits above the tree, can be dismissed.
        self._conflict_banner = ttk.Frame(self)
        self._conflict_banner_label = ttk.Label(
            self._conflict_banner,
            text="",
            anchor="w",
            padding=(10, 5),
        )
        self._conflict_banner_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._conflict_banner_close = ttk.Label(
            self._conflict_banner,
            text="✕",
            cursor="hand2",
            padding=(8, 5),
        )
        self._conflict_banner_close.pack(side=tk.RIGHT)
        self._conflict_banner_close.bind(
            "<Button-1>", lambda e: self._hide_conflict_banner()
        )
        # Don't pack the banner itself - shown on demand by _show_conflict_banner

        # Table: a virtualized tksheet.Sheet replaces ttk.Treeview so the
        # entire filtered dictionary (100k+ rows) can be shown at once with no
        # pagination — only the on-screen cells are ever drawn.  It manages its
        # own vertical and horizontal scrollbars.
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.sheet = Sheet(
            tree_frame,
            headers=[self.HEADINGS[c] for c in self.column_order],
            data=[],
            theme="dark",
            show_row_index=False,
            header_font=("Segoe UI", 10, "bold"),
            font=("Segoe UI", 10, "normal"),
            default_column_width=120,
            alternate_color=C["bg_alt"],
            outline_thickness=0,
        )
        self.sheet.grid(row=0, column=0, sticky="nsew")

        # Read-only but fully navigable: no cell-editing bindings are enabled,
        # so the user can select, scroll, resize columns and copy, but not edit
        # in place (edits go through the dialogs, as before).
        self.sheet.enable_bindings(
            "single_select", "row_select", "drag_select", "column_select",
            "arrowkeys", "column_width_resize", "double_click_column_resize",
            "copy",
        )

        self._configure_columns()
        self._configure_tree_tags()

        # Map the old Treeview interactions onto the sheet.
        self.sheet.extra_bindings("column_select",       self._on_header_click)
        self.sheet.extra_bindings("column_width_resize", self._on_column_resized)
        self._header_tooltip = HoverTooltip(self.sheet.CH, self._header_tooltip_text)
        self.sheet.bind("<<SheetSelect>>", self._update_current_row, add="+")
        self.sheet.MT.bind("<Configure>", self._fit_flex_column, add="+")
        self.sheet.MT.bind("<Double-Button-1>", self._on_double_click, add="+")
        self.sheet.MT.bind("<Button-3>",        self._on_right_click,  add="+")
        self.sheet.MT.bind("<Return>",          self._on_enter,        add="+")
        self.sheet.MT.bind("<Control-e>",       self._on_ctrl_e,       add="+")
        self.sheet.MT.bind("<Delete>", lambda e: self.delete_selected(), add="+")

    def _configure_tree_tags(self):
        """Apply sheet colours from the live palette.  Re-callable on theme
        switch.  Per-row state colours (bookmark / conflict / find) are applied
        separately in _apply_row_highlights; zebra striping is handled by the
        sheet's alternate_color option."""
        if not hasattr(self, "sheet"):
            return
        self.sheet.set_options(
            table_bg=C["bg_panel"], table_fg=C["fg"],
            # The header sits on a slightly darker band with one rule
            # under it; zebra striping alone separates the rows, without
            # grid lines.
            header_bg=C["bg"], header_fg=C["fg_dim"],
            header_border_fg=C["border"],
            show_vertical_grid=False, show_horizontal_grid=False,
            # No blank scroll space past the last column: the flexible
            # column (_fit_flex_column) fills the width exactly.
            empty_horizontal=0,
            table_grid_fg=C["border"], header_grid_fg=C["border"],
            index_bg=C["bg_panel"], index_fg=C["fg_dim"], index_grid_fg=C["border"],
            table_selected_cells_bg=C["accent"], table_selected_cells_fg="white",
            table_selected_rows_bg=C["accent"], table_selected_rows_fg="white",
            table_selected_columns_bg=C["accent"], table_selected_columns_fg="white",
            table_selected_box_cells_fg=C["accent_hover"],
            # Do NOT highlight the header above the selection: paint the
            # "selected" header states the same as a normal header so nothing
            # lights up under the selection box.
            header_selected_cells_bg=C["bg"], header_selected_cells_fg=C["fg_dim"],
            header_selected_columns_bg=C["bg"], header_selected_columns_fg=C["fg_dim"],
            frame_bg=C["bg_panel"], outline_color=C["border"],
            alternate_color=C["bg_alt"],
            # Scrollbars (tksheet's own ttk widgets) — track the palette so
            # they are not stuck on the seed theme's dark colours in light mode.
            vertical_scroll_background=C["bg_panel"], horizontal_scroll_background=C["bg_panel"],
            vertical_scroll_troughcolor=C["bg_panel"], horizontal_scroll_troughcolor=C["bg_panel"],
            vertical_scroll_bordercolor=C["bg_panel"], horizontal_scroll_bordercolor=C["bg_panel"],
            vertical_scroll_lightcolor=C["bg_panel"], horizontal_scroll_lightcolor=C["bg_panel"],
            vertical_scroll_darkcolor=C["bg_panel"], horizontal_scroll_darkcolor=C["bg_panel"],
            vertical_scroll_not_active_bg=C["border"], horizontal_scroll_not_active_bg=C["border"],
            vertical_scroll_not_active_fg=C["border"], horizontal_scroll_not_active_fg=C["border"],
            vertical_scroll_active_bg=C["fg_dim"], horizontal_scroll_active_bg=C["fg_dim"],
            vertical_scroll_active_fg=C["fg_dim"], horizontal_scroll_active_fg=C["fg_dim"],
            vertical_scroll_pressed_bg=C["fg_dim"], horizontal_scroll_pressed_bg=C["fg_dim"],
            vertical_scroll_pressed_fg=C["fg_dim"], horizontal_scroll_pressed_fg=C["fg_dim"],
            redraw=False,
        )

    # ------------------------------------------------------------------
    # Row highlighting (bookmark / conflict / find)
    # ------------------------------------------------------------------
    def _apply_row_highlights(self, redraw: bool = True):
        """Re-apply all per-row state highlights to the sheet.

        Order matters: bookmark/conflict first, find-matches on top so they
        win when a row is both — mirroring the old Treeview tag priority."""
        if not hasattr(self, "sheet"):
            return
        self.sheet.dehighlight_all(redraw=False)
        if self._bm_rows:
            self.sheet.highlight_rows(self._bm_rows, bg=C["bookmark_bg"],
                                      fg=C["bookmark_fg"], redraw=False)
        if self._cf_rows:
            self.sheet.highlight_rows(self._cf_rows, bg=C["conflict_bg"],
                                      fg=C["conflict_fg"], redraw=False)
        if self._both_rows:
            self.sheet.highlight_rows(self._both_rows,
                                      bg=C["bookmarked_conflict_bg"],
                                      fg=C["bookmarked_conflict_fg"], redraw=False)
        if self._find_rows:
            self.sheet.highlight_rows(self._find_rows, bg=C["find_match_bg"],
                                      fg=C["find_match_fg"], redraw=False)
        if self._current_row is not None:
            self._paint_row(self._current_row)
        if redraw:
            self.sheet.refresh()

    def _paint_row(self, row: int) -> None:
        """Give one row the highlight it should have: the soft accent tint
        when it holds the selection, otherwise its find / bookmark /
        conflict colour, or none."""
        if not (0 <= row < len(self.filtered_entries)):
            return
        self.sheet.dehighlight_rows([row], redraw=False)
        if row == self._current_row:
            bg, fg = C["accent_soft"], C["fg"]
        elif row in self._find_rows:
            bg, fg = C["find_match_bg"], C["find_match_fg"]
        elif row in self._both_rows:
            bg, fg = C["bookmarked_conflict_bg"], C["bookmarked_conflict_fg"]
        elif row in self._cf_rows:
            bg, fg = C["conflict_bg"], C["conflict_fg"]
        elif row in self._bm_rows:
            bg, fg = C["bookmark_bg"], C["bookmark_fg"]
        else:
            return
        self.sheet.highlight_rows([row], bg=bg, fg=fg, redraw=False)

    def _update_current_row(self, _event=None) -> None:
        """Tint the whole row holding the selection, so it is easy to spot
        rather than only a thin outline around one cell."""
        if not hasattr(self, "sheet"):
            return
        selected = self.sheet.get_currently_selected()
        row = selected.row if selected else None
        if row == self._current_row:
            return
        previous, self._current_row = self._current_row, row
        if previous is not None:
            self._paint_row(previous)
        if row is not None:
            self._paint_row(row)
        self.sheet.refresh()

    def refresh_theme(self):
        """Re-apply colour-dependent settings after a theme switch."""
        if hasattr(self, "sheet"):
            self._configure_tree_tags()
            self._apply_row_highlights()
        # Conflict banner uses palette colours; recolour if currently shown
        if hasattr(self, "_conflict_banner_label"):
            try:
                self._conflict_banner_label.configure(
                    background=C["conflict_bg"], foreground=C["conflict_fg"])
                self._conflict_banner_close.configure(
                    background=C["conflict_bg"], foreground=C["conflict_fg"])
            except (tk.TclError, AttributeError):
                pass
        self._refresh_dictionary_header()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_entries(self, entries, metadata=None):
        self.entries = entries
        self.metadata = ensure_metadata(entries, metadata or {})
        self._metadata_dirty = False
        self.invalidate_all_cached()
        self._rebuild_conflict_stenos()
        self._undo_stack.clear()
        self._refresh_dictionary_header()
        # Note: we don't call _apply_filters() here.  The caller almost always
        # follows up with apply_search() (main.py does), and that triggers
        # _apply_filters internally — running it twice on a 100k-entry
        # dictionary doubles the load time for no benefit.  The one path
        # that doesn't is direct test-harness usage; tests call _apply_filters
        # explicitly when they need it.
        self.filtered_entries = list(entries)

    def _begin_change(self, label: str) -> _Change:
        """Start an undoable edit; see _Change."""
        return _Change(self, label)

    def _after_entries_changed(self, conflicts_before: set | None):
        """Refresh derived state and the table after entries changed.
        Pass the conflict set from before the change to announce new
        conflicts, or None (undo / redo) to stay quiet."""
        self._rebuild_conflict_stenos()
        if conflicts_before is not None:
            new_conflicts = self.conflict_stenos - conflicts_before
            if new_conflicts:
                self._show_conflict_banner(new_conflicts)
        self._refresh_dictionary_header()
        self._apply_filters()
        if self.on_entries_changed:
            self.on_entries_changed(len(self.entries))

    def _retarget_metadata(self, change: _Change, entry: dict, old_steno: str,
                           modified: str, brief: bool | None = None,
                           comments: str | None = None) -> None:
        """
        Update metadata after `entry` was edited, possibly moving from
        old_steno to a new steno.  The caller drops old_steno's metadata
        with change.drop_unused_meta once no row uses it; it is kept while
        another row still shares it.
        """
        new_steno = entry["steno"]
        source = self.metadata.get(old_steno) or default_metadata(
            entry.get("date_added", modified), modified)
        target = self.metadata.get(new_steno) if new_steno != old_steno else None

        if target is not None:
            meta = merge_metadata(target, modified=modified,
                                    brief=brief, comments=comments)
        else:
            meta = dict(source)
            meta["modified"] = modified
            if brief is not None:
                meta["brief"] = brief
            if comments is not None:
                meta["comments"] = comments
        change.set_meta(new_steno, meta)

    def apply_search(self, config):
        self.search_config = config
        self._apply_filters()

    # ------------------------------------------------------------------
    # Save JSON
    # ------------------------------------------------------------------
    def save_json(self) -> bool:
        """Write steno→english pairs back to the .json or .rtf file (no metadata).

        Before writing, snapshot the existing on-disk file into the backup
        folder so the previous version is recoverable if this save turns
        out to be wrong.
        """
        if not self.dict_path:
            return False

        # Pre-save backup.  If it fails, ask the user whether to proceed -
        # they may not want to overwrite a known-good file when the safety
        # net is unavailable.
        try:
            from logic.backup_store import backup_dictionary
            ok, msg = backup_dictionary(self.dict_path, kind="save")
        except Exception as e:
            ok, msg = False, str(e)

        if not ok:
            proceed = messagebox.askyesno(
                "Backup Failed",
                f"Could not write a backup of "
                f"{os.path.basename(self.dict_path)}:\n\n{msg}\n\n"
                f"Save anyway?",
            )
            if not proceed:
                return False

        try:
            write_dictionary(self.entries, self.dict_path)
            if not self._save_metadata_if_dirty():
                return False
            self._set_dirty(False)
            self._undo_stack.mark_saved()
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save dictionary:\n{e}")
            return False

    def _save_metadata_if_dirty(self) -> bool:
        """Persist sidecar metadata when an edit changed it in memory."""
        if not self._metadata_dirty or not self.dict_path or self.metadata is None:
            return True
        try:
            save_metadata(self.dict_path, self.metadata)
            self._metadata_dirty = False
            return True
        except Exception as e:
            messagebox.showerror(
                "Metadata Save Error",
                f"Failed to save entry metadata:\n{e}",
            )
            return False

    # ------------------------------------------------------------------
    # Bookmarks (session-only)
    # ------------------------------------------------------------------
    def toggle_bookmark_selected(self):
        stenos = self._selected_stenos()
        if not stenos:
            return
        all_bm = all(s in self.bookmarked_stenos for s in stenos)
        if all_bm:
            self.bookmarked_stenos -= stenos
        else:
            self.bookmarked_stenos |= stenos
        self._refresh_tree()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    def delete_selected(self, confirm=True):
        selected = self._selected_entries()
        if not selected:
            return
        if confirm:
            n     = len(selected)
            label = (f'"{selected[0]["steno"]}"'
                     if n == 1 else f"{n} selected entries")
            if not messagebox.askyesno("Delete", f"Delete {label}?"):
                return

        # Entries are removed by object identity rather than by (steno,
        # english) pair: when two rows are literal duplicates, pair-based
        # identity can't tell which row the user actually clicked.  Metadata
        # is only dropped for stenos no remaining row shares.
        n = len(selected)
        change = self._begin_change("Delete Entry" if n == 1 else f"Delete {n} Entries")
        change.remove(selected)
        change.drop_unused_meta(e["steno"] for e in selected)
        change.commit()

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------
    def undo(self) -> None:
        """Reverse the most recent undoable operation."""
        frame = self._undo_stack.pop_undo()
        if frame is None:
            return
        self._apply_undo_redo_frame(frame, direction="undo")

    def redo(self) -> None:
        """Replay the most recently undone operation."""
        frame = self._undo_stack.pop_redo()
        if frame is None:
            return
        self._apply_undo_redo_frame(frame, direction="redo")

    def _apply_undo_redo_frame(self, frame: dict, direction: str) -> None:
        """Reverse (undo) or replay (redo) a frame recorded by _Change.commit."""
        if direction == "undo":
            added = {id(e) for e in frame["added"]}
            if added:
                self.entries = [e for e in self.entries if id(e) not in added]
            for ref, old, _new in frame["changed"]:
                ref.clear()
                ref.update(old)
            # Re-insert removed entries at their recorded positions.  Sort
            # ascending so earlier insertions don't shift later ones.
            for ref, pos in sorted(frame["removed"], key=lambda x: x[1]):
                self.entries.insert(min(pos, len(self.entries)), ref)
            meta_state = frame["meta_before"]
        else:
            removed = {id(ref) for ref, _pos in frame["removed"]}
            if removed:
                self.entries = [e for e in self.entries if id(e) not in removed]
            for ref, _old, new in frame["changed"]:
                ref.clear()
                ref.update(new)
            self.entries.extend(frame["added"])
            meta_state = frame["meta_after"]

        for steno, meta in meta_state.items():
            if meta is None:
                self.metadata.pop(steno, None)
            else:
                self.metadata[steno] = copy.deepcopy(meta)

        self._metadata_dirty = True
        self._invalidate_frame_cache(frame, direction)
        self._set_dirty(self._undo_stack.is_dirty)
        self._after_entries_changed(None)

    def _invalidate_frame_cache(self, frame: dict, direction: str) -> None:
        """Drop cached state touched by an undo frame that was just applied
        ("redo", which is also how a new change is first applied) or
        reversed ("undo")."""
        removed = [ref for ref, _pos in frame["removed"]]
        self._invalidate_cached(
            entries=[*frame["added"], *removed,
                     *(ref for ref, _old, _new in frame["changed"])],
            stenos=frame["meta_before"].keys(),
            gone=frame["added"] if direction == "undo" else removed,
        )

    # ------------------------------------------------------------------
    # Cross-dictionary receive (copy / move)
    # ------------------------------------------------------------------
    def receive_entries(self, entries_with_meta, label="Copy Entries"):
        """Add copies of entries from another tab, as one undoable change.
        Existing metadata for a steno is kept; otherwise the sender's is copied."""
        change = self._begin_change(label)
        today = _today()
        for entry, meta in entries_with_meta:
            steno = change.add(dict(entry))["steno"]
            if steno not in self.metadata:
                change.set_meta(steno, dict(meta) if meta else default_metadata(today, today))
        change.commit()

    # ------------------------------------------------------------------
    # Right-click context menu
    # ------------------------------------------------------------------
    def _on_right_click(self, event):
        row = self.sheet.identify_row(event)
        if row is None:
            return
        if row not in self._selected_rows():
            self._select_rows([row])
        n = len(self._selected_rows())

        menu = tk.Menu(self, tearoff=0)
        if n == 1:
            menu.add_command(label="Edit Entry", command=self._open_edit_dialog_for_selected)
            menu.add_separator()
        menu.add_command(
            label=f"Delete {'entry' if n == 1 else f'{n} entries'}",
            command=self.delete_selected,
        )
        menu.add_separator()
        menu.add_command(label="Toggle Bookmark ★", command=self.toggle_bookmark_selected)

        other = self._get_other_tabs()
        if other:
            menu.add_separator()
            cm = tk.Menu(menu, tearoff=0)
            mm = tk.Menu(menu, tearoff=0)
            for tname, tab in other.items():
                cm.add_command(label=tname, command=lambda t=tab: self._copy_selected_to(t))
                mm.add_command(label=tname, command=lambda t=tab: self._move_selected_to(t))
            menu.add_cascade(label="Copy to →", menu=cm)
            menu.add_cascade(label="Move to →", menu=mm)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _get_other_tabs(self) -> dict:
        """Other open tabs keyed by menu label: the tab name, plus its folder
        when two open dictionaries share a name."""
        app = self.winfo_toplevel()
        if not hasattr(app, "tabs"):
            return {}
        others = [t for t in app.tabs.values() if t is not self]
        names = [t.name for t in app.tabs.values()]
        labels = {}
        for tab in others:
            label = tab.name
            if names.count(tab.name) > 1 and tab.dict_path:
                label = f"{tab.name}  ({os.path.basename(os.path.dirname(tab.dict_path))})"
            labels[label] = tab
        return labels

    def _copy_selected_to(self, target_tab, label="Copy Entries"):
        payload = []
        for entry in self._selected_entries():
            payload.append((entry, (self.metadata or {}).get(entry["steno"], {})))
        target_tab.receive_entries(payload, label=label)

    def _move_selected_to(self, target_tab):
        self._copy_selected_to(target_tab, label="Move Entries")
        self.delete_selected(confirm=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _selected_rows(self) -> list:
        """Sorted list of selected row indices (indices into filtered_entries).

        get_cells_as_rows=True means a plain cell click counts as selecting its
        row, so edit / delete / bookmark work whether the user selected a whole
        row or just clicked a cell."""
        if not hasattr(self, "sheet"):
            return []
        try:
            return sorted(self.sheet.get_selected_rows(get_cells_as_rows=True))
        except Exception:
            return []

    def _entry_for_row(self, row):
        """Return the filtered entry at a sheet row index, or None."""
        if 0 <= row < len(self.filtered_entries):
            return self.filtered_entries[row]
        return None

    def _selected_entries(self) -> list:
        return [self.filtered_entries[r] for r in self._selected_rows()
                if 0 <= r < len(self.filtered_entries)]

    def _selected_stenos(self) -> set:
        return {e["steno"] for e in self._selected_entries()}

    def selected_entries(self) -> list:
        """Public: filtered entries for the current selection (used by dialogs)."""
        return self._selected_entries()

    def _select_rows(self, rows):
        """Replace the selection with the given row indices and scroll to the
        first one."""
        if not hasattr(self, "sheet"):
            return
        rows = sorted(r for r in rows if 0 <= r < len(self.filtered_entries))
        self.sheet.deselect("all", redraw=False)
        for i, r in enumerate(rows):
            self.sheet.add_row_selection(
                r, redraw=False, run_binding_func=False, set_as_current=(i == 0)
            )
        if rows:
            self.sheet.see(rows[0], redraw=False)
        self.sheet.refresh()
        self._update_current_row()

    # ------------------------------------------------------------------
    # Following a selection across tabs
    # ------------------------------------------------------------------
    def follow_target(self):
        """
        What the current selection asks other tabs to find, as
        (field, text, whole_row), or None.  A selected steno cell is
        matched by steno; a translation cell, a whole row or any other
        column's cell by translation.
        """
        if not hasattr(self, "sheet"):
            return None
        selected = self.sheet.get_currently_selected()
        if not selected:
            return None
        entry = self._entry_for_row(selected.row)
        if entry is None:
            return None
        whole_row = selected.type_ == "rows"
        column = None
        if not whole_row and 0 <= selected.column < len(self.column_order):
            column = self.column_order[selected.column]
        field = "steno" if column == "steno" else "english"
        text = (entry.get(field) or "").strip()
        return (field, text, whole_row) if text else None

    def follow(self, target) -> bool:
        """
        Select and scroll to the row matching `target` (from another tab's
        follow_target), looking only among the rows this tab currently
        shows: its search and filters are left as they are.  An exact
        match, ignoring case, wins; otherwise the first row that begins
        with the text.  With no match nothing changes and False is returned.
        """
        field, text, whole_row = target
        needle = text.lower()
        values = [(e.get(field) or "").strip().lower() for e in self.filtered_entries]
        try:
            row = values.index(needle)
        except ValueError:
            row = next((i for i, v in enumerate(values) if v.startswith(needle)), None)
        if row is None:
            return False
        if whole_row:
            self._select_rows([row])
        else:
            column = self.column_order.index(field)
            self.sheet.deselect("all", redraw=False)
            self.sheet.select_cell(row, column, redraw=False, run_binding_func=False)
            self.sheet.see(row, column, redraw=False)
            self.sheet.refresh()
            self._update_current_row()
        return True

    def select_and_see_row(self, row):
        """Public: select a single filtered-row index and scroll it into view."""
        self._select_rows([row])

    # ------------------------------------------------------------------
    # Selection handlers
    # ------------------------------------------------------------------
    def _on_double_click(self, event=None): self._open_edit_dialog_for_selected()
    def _on_enter(self,        event=None): self._open_edit_dialog_for_selected()
    def _on_ctrl_e(self,       event=None): self._open_edit_dialog_for_selected()

    # ------------------------------------------------------------------
    # Header click → sort;  column resize → persist widths
    # ------------------------------------------------------------------
    def _on_header_click(self, event=None):
        """Clicking a column header sorts by that column (toggling direction)."""
        col_idx = None
        try:
            col_idx = event.selected.column
        except Exception:
            try:
                col_idx = event["selected"].column
            except Exception:
                col_idx = None
        if col_idx is None or not (0 <= col_idx < len(self.column_order)):
            return
        self._sort_by(self.column_order[col_idx])
        self.sheet.deselect("all", redraw=True)

    def _header_tooltip_text(self, event):
        """Explain the column under the pointer (S, W, B and F are cryptic)."""
        try:
            col_idx = self.sheet.identify_column(event)
        except Exception:
            return None
        if col_idx is None or not (0 <= col_idx < len(self.column_order)):
            return None
        return self.COLUMN_TOOLTIPS.get(self.column_order[col_idx])

    def _on_column_resized(self, event=None):
        self._save_column_widths()
        self._fit_flex_column()

    # ------------------------------------------------------------------
    # Filters + search
    # ------------------------------------------------------------------
    def _apply_filters(self):
        """
        Walk self.entries and produce self.filtered_entries.

        With 100k+ entry dictionaries this is the hot path on every keystroke,
        so the loop is structured to do the minimum work per row:
        - Tk variable values are pulled once before the loop, not 100k times.
        - Per-entry work is gated on whether the relevant filter is active,
          so an unfiltered open-the-dictionary case skips lower(), metadata
          lookups, and regex compilation entirely.
        - Punctuation regex is compiled once and cached on the class.
        """
        # Guard: this may be called via StringVar trace during __init__ before
        # the sheet is built.  Nothing to do yet in that case.
        if not hasattr(self, "sheet"):
            return
        self._refresh_filter_chips()

        cfg = getattr(self, "search_config", {}) or {}
        steno_q       = cfg.get("steno_query", "").strip()
        steno_method  = cfg.get("steno_method", "Contains")
        whole_strokes = cfg.get("steno_whole_strokes", False)
        match_case    = cfg.get("text_match_case", False)
        text_q_raw    = cfg.get("text_query", "").strip()
        text_q        = text_q_raw if match_case else text_q_raw.lower()
        text_method   = cfg.get("text_method", "Begins With")

        steno_active = bool(steno_q)
        text_active  = bool(text_q)

        # Hoist tk var reads - one Tk call instead of 101k
        f_comments    = self.filter_has_comments.get()
        f_brief       = self.filter_is_brief.get()
        f_bookmarked  = self.filter_bookmarked.get()
        f_capitalised = self.filter_capitalised.get()
        f_digits      = self.filter_has_digits.get()
        f_written     = self.filter_has_written_numbers.get()
        f_punct       = self.filter_has_punctuation.get()
        f_conflict    = self.filter_conflicts.get()
        f_has_freq    = self.filter_has_frequency.get()
        f_top_freq    = self.filter_top_freq.get()

        any_meta_filter = f_comments or f_brief or f_has_freq
        any_filter      = (f_comments or f_brief or f_bookmarked or
                           f_capitalised or f_digits or f_written or
                           f_punct or f_conflict or f_has_freq or f_top_freq)

        # Local refs - faster lookup than self.X in the loop.
        # metadata must be assigned before the f_top_freq block below, which
        # needs it to compute the ranked steno set.
        metadata          = self.metadata or {}
        bookmarked_stenos = self.bookmarked_stenos
        conflict_stenos   = self.conflict_stenos
        steno_matches     = self._steno_matches
        text_matches      = self._text_matches
        digit_re          = _DIGIT_RE
        punct_re          = _PUNCT_RE
        word_re           = _WORD_RE
        written_numbers   = WRITTEN_NUMBERS

        # Pre-compute the top-N steno set when that filter is active.
        # Done once here — outside the per-entry loop — so the hot path
        # only does a fast set-membership test per row.
        if f_top_freq:
            try:
                top_n = max(1, int(self.filter_top_freq_n_var.get()))
            except (ValueError, TypeError):
                top_n = 500
            scored = heapq.nlargest(
                top_n,
                (
                    (e["steno"], (metadata.get(e["steno"]) or {}).get("frequency", 0))
                    for e in self.entries
                ),
                key=itemgetter(1),
            )
            # Entries with score 0 are never included regardless of N
            top_n_stenos = {steno for steno, score in scored if score > 0}
        else:
            top_n_stenos = None

        # Walking the entries in sort order means the results come out
        # already sorted, so typing a search never re-sorts.
        if not (text_active or steno_active or any_filter):
            results = list(self._entries_in_sort_order())
        elif text_active and not match_case and not steno_active and not any_filter:
            # The usual case while typing: one comparison per entry against
            # cached lowered translations.
            match = {"Contains": str.__contains__, "Begins With": str.startswith,
                     "Ends With": str.endswith}.get(text_method)
            pairs = zip(self._entries_in_sort_order(), self._lowered_texts())
            results = [e for e, text in pairs if match and match(text, text_q)]
        else:
            results = []
            for entry in self._entries_in_sort_order():
                steno   = entry["steno"]
                # Guard against null English values (used in some steno dictionaries
                # as stroke suppressors).  Treat them as empty strings throughout.
                english = entry["english"] or ""

                # Steno axis
                if steno_active and not steno_matches(
                    steno, steno_q, steno_method, whole_strokes
                ):
                    continue

                # The text axis can run case-sensitively or not.  The lowered
                # form is also used by the written-numbers filter, so we may
                # need it even when match_case is on for the text search.
                need_lower = (text_active and not match_case) or f_written
                english_lower = english.lower() if need_lower else None

                # Text axis
                if text_active:
                    haystack = english.strip() if match_case else english_lower.strip()
                    if not text_matches(haystack, text_q, text_method):
                        continue

                # Predicate filters
                if any_filter:
                    # Metadata-based predicates only fetch metadata if needed
                    if any_meta_filter:
                        meta = metadata.get(steno, {})
                        if f_comments and not meta.get("comments", "").strip():
                            continue
                        if f_brief and not meta.get("brief", False):
                            continue
                        if f_has_freq and not meta.get("frequency", 0):
                            continue

                    if f_bookmarked and steno not in bookmarked_stenos:
                        continue
                    if f_capitalised and not (english and english[0].isupper()):
                        continue
                    if f_digits and not digit_re.search(english):
                        continue
                    if f_written:
                        if not (set(word_re.findall(english_lower)) & written_numbers):
                            continue
                    if f_punct and not punct_re.search(english):
                        continue
                    if f_conflict and steno not in conflict_stenos:
                        continue
                    if f_top_freq and steno not in top_n_stenos:
                        continue

                results.append(entry)

        self.filtered_entries = results

        # Update entry-count chip — total when nothing filtered, otherwise
        # "X of Y".  Style changes (rather than fg overrides) when a search
        # returns zero matches so the chip lights up red.
        total   = len(self.entries)
        showing = len(results)
        search_active = steno_active or text_active

        if showing < total:
            self.entry_count_var.set(f"{showing:,} of {total:,}")
        else:
            self.entry_count_var.set(f"{total:,} entries")

        if hasattr(self, "count_chip"):
            if search_active and showing == 0:
                self.count_chip.configure(style="HeaderDanger.TLabel")
            else:
                self.count_chip.configure(style="HeaderChip.TLabel")

        self._update_no_match_hint(showing=showing, search_active=search_active)

        # Notify owner of result count - lets main.py react if interested.
        if callable(getattr(self, "_on_filter_count_changed", None)):
            try:
                self._on_filter_count_changed(showing, total,
                                              search_active=search_active)
            except Exception:
                pass

        self._refresh_tree()
        self._update_sort_headings()

    def _lowered_texts(self) -> list:
        """Lowered, stripped translations parallel to _entries_in_sort_order(),
        cached until that order is rebuilt."""
        ordered = self._entries_in_sort_order()
        cached = self._lowered_cache
        if cached is None or cached[0] is not ordered:
            texts = [(e["english"] or "").lower().strip() for e in ordered]
            cached = self._lowered_cache = (ordered, texts)
        return cached[1]

    def _text_matches(self, english_lower: str, query: str, method: str) -> bool:
        """Match the English translation against the query using the given method."""
        if method == "Contains":    return query in english_lower
        if method == "Begins With": return english_lower.startswith(query)
        if method == "Ends With":   return english_lower.endswith(query)
        return False

    def _steno_matches(self, steno_value: str, query: str,
                       method: str, whole_strokes_only: bool) -> bool:
        """
        Match a steno entry against the query.

        Free-form mode (whole_strokes_only=False): treat steno as a single
        string and apply contains/starts/ends to its full text.

        Whole-strokes mode: split both steno and query on '/' and require
        the query strokes to appear at the right position as complete strokes.
        Example: query 'AL' with method 'Ends With' matches 'TPORPL/AL' but
        not 'TPAL' (which contains AL only as a substring of one stroke).
        """
        sv = steno_value.upper().strip()
        q  = query.upper().strip()

        if not whole_strokes_only:
            if method == "Contains":    return q in sv
            if method == "Begins With": return sv.startswith(q)
            if method == "Ends With":   return sv.endswith(q)
            return False

        strokes   = sv.split("/")
        q_strokes = q.split("/")
        n         = len(q_strokes)
        if n == 0 or n > len(strokes):
            return False

        if method == "Contains":
            for i in range(len(strokes) - n + 1):
                if strokes[i:i + n] == q_strokes:
                    return True
            return False
        if method == "Begins With":
            return strokes[:n] == q_strokes
        if method == "Ends With":
            return strokes[-n:] == q_strokes
        return False

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------
    def _sort_by(self, column, remember=True):
        """Sort by column (a header click toggles direction) and redisplay."""
        if self.sort_column == column and remember:
            self.sort_reverse = not self.sort_reverse
        elif remember:
            self.sort_column  = column
            self.sort_reverse = False
        self._sorted_entries = None
        self._apply_filters()

    def _entries_in_sort_order(self) -> list:
        """Every entry in the current sort order.  Kept between filter passes
        and rebuilt only after a change or a new sort (see _invalidate_cached)."""
        if self._sorted_entries is None:
            self._sorted_entries = sorted(
                self.entries, key=self._sort_key(self.sort_column),
                reverse=self.sort_reverse,
            )
        return self._sorted_entries

    def _sort_key(self, column):
        metadata = self.metadata or {}
        empty = {}
        if column == "S":
            return lambda e: e["steno"].count("/") + 1
        if column == "W":
            return lambda e: len((e.get("english") or "").split())
        if column == "F":
            return lambda e: metadata.get(e["steno"], empty).get("frequency", 0)
        if column == "B":
            return lambda e: 1 if metadata.get(e["steno"], empty).get("brief") else 0
        if column in ("added", "modified", "comments"):
            field = "date_added" if column == "added" else column
            return lambda e: (metadata.get(e["steno"], empty).get(field) or "").lower()

        def key(e):
            v = e.get(column, "") or ""
            return v.lower() if isinstance(v, str) else v
        return key

    def _heading_text(self, col) -> str:
        base = self.HEADINGS[col]
        if col == self.sort_column:
            return f"{base} {'▼' if self.sort_reverse else '▲'}"
        return base

    def _update_sort_headings(self):
        if not hasattr(self, "sheet"):
            return
        self.sheet.set_header_data(
            [self._heading_text(c) for c in self.column_order]
        )

    # ------------------------------------------------------------------
    # Tree refresh (zebra stripes + tags)
    # ------------------------------------------------------------------
    def _refresh_tree(self, reset_columns: bool = False):
        """
        Rebuild the sheet from self.filtered_entries.

        The sheet is virtualized, so every filtered row is loaded (no cap, no
        pagination) and only the on-screen cells are drawn.  Each entry's
        display row is built once and cached (_display_row), so redrawing
        after a search only gathers rows.  Bookmark / conflict highlights are
        applied as row-index sets (zebra striping is the sheet's alternate_color).

        reset_columns=True recreates the column positions, which is required
        when the number of columns changes (freq / focus toggle); normal
        refreshes keep them so user-resized widths survive searches.
        """
        if not hasattr(self, "sheet"):
            return

        prev_selected = self._selected_stenos()
        filtered = self.filtered_entries

        cache = self._row_cache

        def build(entry):
            row = self._display_row(entry)
            cache[id(entry)] = (entry, row)
            return row

        # The identity check guards against a recycled id() after an entry
        # object was freed.  Comprehensions keep these 100k-row passes fast.
        rows = [
            hit[1] if hit is not None and hit[0] is entry else build(entry)
            for entry, hit in zip(filtered, map(cache.get, map(id, filtered)))
        ]

        bm_rows, cf_rows, both_rows, to_reselect = [], [], [], []
        bookmarked_stenos = self.bookmarked_stenos
        conflict_stenos   = self.conflict_stenos
        if bookmarked_stenos or conflict_stenos or prev_selected:
            stenos = list(map(itemgetter("steno"), filtered))
            if bookmarked_stenos and conflict_stenos:
                both_rows = [i for i, s in enumerate(stenos)
                             if s in bookmarked_stenos and s in conflict_stenos]
            if bookmarked_stenos:
                bm_rows = [i for i, s in enumerate(stenos)
                           if s in bookmarked_stenos and s not in conflict_stenos]
            if conflict_stenos:
                cf_rows = [i for i, s in enumerate(stenos)
                           if s in conflict_stenos and s not in bookmarked_stenos]
            if prev_selected:
                to_reselect = [i for i, s in enumerate(stenos) if s in prev_selected]

        self.sheet.set_sheet_data(
            rows, reset_highlights=True, redraw=False,
            reset_col_positions=reset_columns, reset_row_positions=True,
        )
        self._bm_rows, self._cf_rows, self._both_rows = bm_rows, cf_rows, both_rows
        # A fresh data set drops any stale find highlights and selection.
        self._find_rows = []
        self._current_row = None
        self._apply_row_highlights(redraw=False)

        if to_reselect:
            self._select_rows(to_reselect)
        else:
            self.sheet.refresh()

    def _display_row(self, entry) -> list:
        """The table cells for one entry, in column_order."""
        steno   = entry["steno"]
        english = entry.get("english") or ""
        meta    = (self.metadata or {}).get(steno, {})
        row = []
        for col in self.column_order:
            if col == "steno":
                row.append(steno)
            elif col == "english":
                row.append(english)
            elif col == "S":
                row.append(steno.count("/") + 1)
            elif col == "W":
                row.append(len(english.split()))
            elif col == "B":
                row.append("✓" if meta.get("brief", False) else "")
            elif col == "F":
                freq = meta.get("frequency", 0)
                row.append(f"{freq:,}" if freq else "")
            elif col == "added":
                row.append(meta.get("date_added", entry.get("date_added", "")))
            elif col == "modified":
                row.append(meta.get("modified", entry.get("modified", "")))
            elif col == "comments":
                comments = meta.get("comments", "")
                if comments and len(comments) > MAX_COMMENT_CHARS:
                    comments = comments[:MAX_COMMENT_CHARS - 3] + "..."
                row.append(comments)
        return row

    # ------------------------------------------------------------------
    # Conflict warning banner
    # ------------------------------------------------------------------
    def _show_conflict_banner(self, new_conflict_stenos):
        """
        Display a non-blocking warning above the tree when add/edit/receive
        creates one or more new conflicts.  Auto-ticks the Conflicts filter
        so the user can immediately see which rows are involved.
        """
        if not new_conflict_stenos:
            return

        n = len(new_conflict_stenos)
        if n == 1:
            steno = next(iter(new_conflict_stenos))
            text = (f"Conflict: \"{steno}\" now has multiple translations. "
                    f"The Conflicts filter has been turned on so you can review.")
        else:
            text = (f"{n} new conflicts created. "
                    f"The Conflicts filter has been turned on so you can review.")

        self._conflict_banner_label.config(
            text=text,
            background=C["conflict_bg"],
            foreground=C["conflict_fg"],
        )
        self._conflict_banner_close.config(
            background=C["conflict_bg"],
            foreground=C["conflict_fg"],
        )
        # Apply background to the frame itself via style
        try:
            self._conflict_banner.configure(style="Conflict.TFrame")
        except tk.TclError:
            pass

        self._conflict_banner.pack(fill=tk.X, side=tk.TOP, padx=2, pady=(0, 2))

        # Auto-toggle the Conflicts filter on
        if not self.filter_conflicts.get():
            self.filter_conflicts.set(True)  # triggers _apply_filters via trace

    def _hide_conflict_banner(self):
        try:
            self._conflict_banner.pack_forget()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Column width persistence
    # ------------------------------------------------------------------
    def _save_column_widths(self, event=None):
        """Persist current sheet column widths.  Called when the user finishes
        dragging a column border (the column_width_resize binding)."""
        if not hasattr(self, "sheet"):
            return
        try:
            widths = self.sheet.get_column_widths()
        except Exception:
            return
        for i, col in enumerate(self.column_order):
            if i < len(widths):
                # The flexible column's fitted width is the table's doing,
                # not the user's choice, so it isn't kept.
                flex_col, flex_width = self._fitted_flex
                if col == flex_col and abs(widths[i] - flex_width) <= 1:
                    continue
                self.column_widths[col] = int(widths[i])
        settings = load_settings()
        settings["column_widths"] = self.column_widths
        save_settings(settings)
        self.settings = settings

    # ------------------------------------------------------------------
    # Edit / Add dialog
    # ------------------------------------------------------------------
    def _open_edit_dialog_for_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        entry = self._entry_for_row(rows[0])
        if entry is None:
            return
        self._open_edit_dialog(entry)

    def _open_add_dialog(self):
        self._open_edit_dialog({
            "steno": "", "english": "",
            "date_added": datetime.now().strftime("%Y-%m-%d"),
            "modified":   datetime.now().strftime("%Y-%m-%d"),
            "brief": False, "comments": "",
        }, is_new=True)

    def _open_edit_dialog(self, entry, is_new=False):
        dlg = tk.Toplevel(self)
        dlg.title("Add Entry" if is_new else "Edit Entry")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        _style_dialog(dlg)

        con = ttk.Frame(dlg, padding=12)
        con.pack(fill=tk.BOTH, expand=True)

        ttk.Label(con, text="Add Entry" if is_new else "Edit Entry",
                  font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(con, text="Steno:").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        steno_var   = tk.StringVar(value=entry.get("steno", ""))
        steno_entry = ttk.Entry(con, textvariable=steno_var, width=40)
        steno_entry.grid(row=1, column=1, sticky="w", pady=4)

        # Validation message slot just under the steno field.  Hidden until
        # validation fails on save attempt - we don't validate as the user
        # types because briefs are entered key-by-key and would flicker
        # errors mid-word.  When validation fails, both an inline message
        # and a red border on the field draw the eye to the problem.
        steno_error_var = tk.StringVar(value="")
        steno_error = ttk.Label(
            con, textvariable=steno_error_var,
            foreground=C["conflict_fg"], wraplength=320,
            font=("Segoe UI", 9, "bold"),
        )
        steno_error.grid(row=2, column=1, sticky="w", pady=(0, 2))

        # An invalid-state style for the entry that tints the border red.
        # Style is keyed off the standard 'invalid' state so we can flip it
        # by setting/clearing that state on the entry.
        style = ttk.Style()
        style.map(
            "Invalid.TEntry",
            fieldbackground=[("invalid", C["bg_input"])],
            bordercolor=[("invalid", C["conflict_fg"])],
            lightcolor=[("invalid", C["conflict_fg"])],
            darkcolor=[("invalid", C["conflict_fg"])],
        )
        steno_entry.configure(style="Invalid.TEntry")

        # Clear the error state as soon as the user edits the field, so
        # they see immediate feedback that they're addressing the problem.
        # Also auto-uppercase steno - it's conventional and saves the user
        # reaching for Caps Lock or holding Shift while typing every key.
        upcasing = {"flag": False}
        def on_steno_edit(*_):
            if steno_error_var.get():
                steno_error_var.set("")
                steno_entry.state(["!invalid"])
            # Auto-uppercase, guarded against the recursive trace fire
            if upcasing["flag"]:
                return
            current = steno_var.get()
            upper   = current.upper()
            if upper != current:
                upcasing["flag"] = True
                try:
                    # Preserve the cursor position - .set() resets it to 0
                    cursor = steno_entry.index(tk.INSERT)
                    steno_var.set(upper)
                    steno_entry.icursor(cursor)
                finally:
                    upcasing["flag"] = False
        steno_var.trace_add("write", on_steno_edit)

        ttk.Label(con, text="Translation:").grid(row=3, column=0, sticky="e", padx=(0, 8), pady=4)
        english_var = tk.StringVar(value=entry.get("english") or "")
        ttk.Entry(con, textvariable=english_var, width=40).grid(row=3, column=1, sticky="w", pady=4)

        edit_meta = (self.metadata or {}).get(entry.get("steno", ""), {})
        brief_var  = tk.BooleanVar(value=edit_meta.get("brief", entry.get("brief", False)))
        ttk.Checkbutton(con, text="Brief outline", variable=brief_var).grid(
            row=4, column=1, sticky="w", pady=(4, 4))

        ttk.Label(con, text="Comments:").grid(row=5, column=0, sticky="ne", padx=(0, 8), pady=(4, 2))
        cf = ttk.Frame(con)
        cf.grid(row=5, column=1, sticky="nsew", pady=(4, 2))
        ct = tk.Text(cf, height=4, wrap="word", borderwidth=1, relief="solid", font=("Segoe UI", 9))
        ct.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        csb = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=ct.yview)
        csb.pack(side=tk.RIGHT, fill=tk.Y)
        ct.configure(yscrollcommand=csb.set)
        ct.insert("1.0", edit_meta.get("comments", entry.get("comments", "")))

        con.rowconfigure(5, weight=1)
        con.columnconfigure(1, weight=1)

        bf = ttk.Frame(con)
        bf.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")

        # The validator knows Plover's English layout only, so a failure is a
        # warning: pressing Save again with the same steno keeps it.  This is
        # what lets Palantype and other CAT systems' entries be edited.
        warned_for = {"steno": None}

        def on_save():
            from logic.steno_validator import validate_steno
            steno_input = steno_var.get().strip()
            if not steno_input:
                steno_error_var.set("Steno cannot be empty.")
                steno_entry.state(["invalid"])
                steno_entry.focus_set()
                return
            # An unchanged steno was accepted when it was first written; only
            # check new or changed ones.
            if is_new or steno_input != entry.get("steno"):
                ok, msg = validate_steno(steno_input)
                if not ok and warned_for["steno"] != steno_input:
                    warned_for["steno"] = steno_input
                    steno_error_var.set(f"{msg}  Press Save again to keep it anyway.")
                    steno_entry.state(["invalid"])
                    steno_entry.focus_set()
                    return
            steno_error_var.set("")
            steno_entry.state(["!invalid"])

            english  = english_var.get().strip()
            brief    = brief_var.get()
            comments = ct.get("1.0", "end-1c").strip()
            today    = _today()

            # Metadata is only written to disk together with the dictionary
            # (save_json), so discarding unsaved changes discards both.
            if is_new:
                change = self._begin_change("Add Entry")
                change.add({
                    "steno": steno_input, "english": english,
                    "date_added": today, "modified": today,
                })
                existing = self.metadata.get(steno_input)
                if existing is None:
                    meta = default_metadata(today, today)
                    meta.update(brief=brief, comments=comments)
                else:
                    meta = merge_metadata(existing, modified=today,
                                            brief=brief, comments=comments)
                change.set_meta(steno_input, meta)
            else:
                old_steno = entry["steno"]
                change = self._begin_change("Edit Entry")
                change.update(entry, steno=steno_input, english=english, modified=today)
                self._retarget_metadata(change, entry, old_steno, today,
                                        brief=brief, comments=comments)
                change.drop_unused_meta([old_steno])
            change.commit()
            dlg.destroy()

        ttk.Button(bf, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(bf, text="Save",   command=on_save).pack(side=tk.RIGHT)

        dlg.update_idletasks()
        center_on_parent(dlg, self.winfo_toplevel())
        steno_entry.focus_set()
