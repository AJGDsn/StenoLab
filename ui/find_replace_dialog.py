# ui/find_replace_dialog.py
import re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from ui.theme import C


def _style(d):
    d.configure(bg=C["bg_panel"])


class FindReplaceDialog(tk.Toplevel):
    """
    Non-modal Find & Replace dialog.

    Always operates on the tab returned by get_tab_fn() at the moment each
    action fires, so switching tabs mid-session naturally targets the
    active dictionary.

    Find searches the currently visible (filtered) rows.
    Replace All operates on ALL entries regardless of any active filter.
    """

    def __init__(self, parent, get_tab_fn):
        super().__init__(parent)
        self.get_tab = get_tab_fn
        self.title("Find & Replace")
        self.resizable(False, False)
        _style(self)
        self.transient(parent)          # sits above main window, not modal

        self._matches:   list = []      # treeview item IDs matching current query
        self._match_idx: int  = -1

        self._build()
        self._position()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda e: self._on_close())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build(self):
        f = ttk.Frame(self, padding=14)
        f.pack(fill=tk.BOTH, expand=True)

        kw = {"padx": 8, "pady": 4}

        # Find
        ttk.Label(f, text="Find:", width=9, anchor="e").grid(row=0, column=0, **kw)
        self.find_var = tk.StringVar()
        self.find_entry = ttk.Entry(f, textvariable=self.find_var, width=36)
        self.find_entry.grid(row=0, column=1, columnspan=2, sticky="ew", **kw)
        self.find_var.trace_add("write", lambda *_: self._update_matches())

        # Replace
        ttk.Label(f, text="Replace:", width=9, anchor="e").grid(row=1, column=0, **kw)
        self.replace_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.replace_var, width=36).grid(
            row=1, column=1, columnspan=2, sticky="ew", **kw
        )

        # Options
        ttk.Label(f, text="In:", width=9, anchor="e").grid(row=2, column=0, **kw)
        self.field_var = tk.StringVar(value="Translation")
        ttk.Combobox(
            f, textvariable=self.field_var,
            values=["Translation", "Steno", "Both"],
            state="readonly", width=16,
        ).grid(row=2, column=1, sticky="w", **kw)
        self.field_var.trace_add("write", lambda *_: self._update_matches())

        self.case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="Match case",
            variable=self.case_var,
            command=self._update_matches,
        ).grid(row=2, column=2, sticky="w", **kw)

        # Match count / status
        self.status_label = ttk.Label(f, text="", foreground=C["fg_dim"])
        self.status_label.grid(row=3, column=0, columnspan=3, sticky="w",
                               padx=8, pady=(6, 2))

        ttk.Separator(f, orient="horizontal").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=6, padx=2
        )

        # Buttons
        btn = ttk.Frame(f)
        btn.grid(row=5, column=0, columnspan=3, pady=(0, 2))
        ttk.Button(btn, text="◀ Prev",     command=self._find_prev).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn, text="Next ▶",     command=self._find_next).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn, text="Replace",    command=self._replace).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn, text="Replace All",command=self._replace_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn, text="Close",      command=self._on_close).pack(side=tk.LEFT, padx=(14, 3))

        f.columnconfigure(1, weight=1)

        self.bind("<Return>",       lambda e: self._find_next())
        self.bind("<Shift-Return>", lambda e: self._find_prev())
        self.find_entry.focus_set()

    def _position(self):
        """Place the dialog in the top-right of the main window."""
        self.update_idletasks()
        px = self.master.winfo_rootx()
        py = self.master.winfo_rooty()
        pw = self.master.winfo_width()
        dw = self.winfo_width()
        self.geometry(f"+{px + pw - dw - 20}+{py + 80}")

    def refresh_theme(self):
        """Re-apply colour-dependent settings after a theme switch."""
        try:
            self.configure(bg=C["bg_panel"])
            if hasattr(self, "status_label"):
                self.status_label.configure(foreground=C["fg_dim"])
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Match logic
    # ------------------------------------------------------------------
    def _update_matches(self):
        tab = self.get_tab()
        if not tab:
            self._clear(tab)
            return

        find_text = self.find_var.get()
        if not find_text:
            self._clear(tab)
            return

        flags   = 0 if self.case_var.get() else re.IGNORECASE
        field   = self.field_var.get()
        pattern = re.compile(re.escape(find_text), flags)

        matches = [
            i for i, entry in enumerate(tab.filtered_entries)
            if self._row_matches(tab, entry, pattern, field)
        ]

        self._matches   = matches
        self._match_idx = -1
        tab.apply_find_highlights(set(matches))

        n = len(matches)
        self.status_label.config(
            text=f"{n} match{'es' if n != 1 else ''}" if n else "No matches"
        )

    def _clear(self, tab):
        if tab:
            tab.clear_find_highlights()
        self._matches   = []
        self._match_idx = -1
        self.status_label.config(text="")

    def _row_matches(self, tab, entry, pattern, field):
        if field in ("Translation", "Both") and pattern.search(entry.get("english") or ""):
            return True
        if field in ("Steno",       "Both") and pattern.search(entry.get("steno", "")):
            return True
        return False

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _find_next(self):
        if not self._matches:
            self._update_matches()
        if not self._matches:
            return
        self._match_idx = (self._match_idx + 1) % len(self._matches)
        self._jump()

    def _find_prev(self):
        if not self._matches:
            self._update_matches()
        if not self._matches:
            return
        self._match_idx = (self._match_idx - 1) % len(self._matches)
        self._jump()

    def _jump(self):
        tab = self.get_tab()
        if not tab or not self._matches:
            return
        row = self._matches[self._match_idx]
        tab.select_and_see_row(row)
        n   = len(self._matches)
        idx = self._match_idx + 1
        self.status_label.config(text=f"{idx} of {n} match{'es' if n != 1 else ''}")

    # ------------------------------------------------------------------
    # Replace (single)
    # ------------------------------------------------------------------
    def _replace(self):
        tab = self.get_tab()
        if not tab:
            return

        find_text    = self.find_var.get()
        replace_text = self.replace_var.get()
        field        = self.field_var.get()
        if not find_text:
            return

        pattern = self._pattern(find_text)

        selected = tab.selected_entries()
        if not selected:
            self._find_next()
            return

        change = tab._begin_change("Replace")
        if self._replace_in_entry(tab, change, selected[0], pattern,
                                  replace_text, field, date.today().strftime("%Y-%m-%d")):
            change.commit()
            self._update_matches()

        self._find_next()

    # ------------------------------------------------------------------
    # Replace All
    # ------------------------------------------------------------------
    def _replace_all(self):
        tab = self.get_tab()
        if not tab:
            return

        find_text    = self.find_var.get()
        replace_text = self.replace_var.get()
        field        = self.field_var.get()
        if not find_text:
            return

        pattern = self._pattern(find_text)

        # Operate on ALL entries (not just the filtered view)
        targets = [e for e in tab.entries if self._row_matches(tab, e, pattern, field)]
        if not targets:
            messagebox.showinfo("Replace All", "No matches found.", parent=self)
            self._update_matches()
            return

        n = len(targets)
        proceed = messagebox.askyesno(
            "Replace All",
            f"Replace matches in {n:,} entr{'y' if n == 1 else 'ies'}?\n\n"
            f"You can undo this with Ctrl+Z.",
            parent=self,
        )
        if not proceed:
            return

        today = date.today().strftime("%Y-%m-%d")
        change = tab._begin_change("Replace All")
        for entry in targets:
            self._replace_in_entry(tab, change, entry, pattern, replace_text,
                                   field, today, drop_old_meta=False)
        # One pass over the dictionary for all renamed stenos, rather than
        # one per entry.
        change.drop_unused_meta(old.get("steno") for old in change.old_values())
        change.commit()
        messagebox.showinfo(
            "Replace All",
            f"Replaced matches in {n:,} entr{'y' if n == 1 else 'ies'}.",
            parent=self,
        )
        self._update_matches()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pattern(self, find_text):
        flags = 0 if self.case_var.get() else re.IGNORECASE
        return re.compile(re.escape(find_text), flags)

    def _replace_in_entry(self, tab, change, entry, pattern, replace_text,
                          field, today, drop_old_meta=True) -> bool:
        """Apply the replacement to one entry within `change`.  Returns
        True if the entry changed."""
        # A function replacement inserts the text exactly as typed; a plain
        # string would be read as a regex template (\1, \n, ...).
        literal = lambda _m: replace_text  # noqa: E731
        old_steno   = entry["steno"]
        old_english = entry.get("english") or ""
        new_english = old_english
        new_steno   = old_steno
        if field in ("Translation", "Both"):
            new_english = pattern.sub(literal, old_english)
        if field in ("Steno", "Both"):
            new_steno = pattern.sub(literal, old_steno)
        if new_english == old_english and new_steno == old_steno:
            return False

        fields = {"modified": today}
        if new_steno != old_steno:
            fields["steno"] = new_steno
        if new_english != old_english:
            fields["english"] = new_english
        change.update(entry, **fields)
        tab._retarget_metadata(change, entry, old_steno, today)
        if new_steno != old_steno:
            if old_steno in tab.bookmarked_stenos:
                tab.bookmarked_stenos.add(new_steno)
            if drop_old_meta:
                change.drop_unused_meta([old_steno])
        return True

    def _on_close(self):
        tab = self.get_tab()
        if tab:
            tab.clear_find_highlights()
        self.destroy()
