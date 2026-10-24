# main.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# UI components
from ui.theme import apply_steno_theme, apply_theme, set_titlebar_dark, get_mode
from ui.menubar import MenuBar
from ui.toolbar import Toolbar
from ui.dictionary_tab import DictionaryTab
from ui.statusbar import StatusBar
from ui.open_dictionary_dialog import ask_open_dictionary
from ui.missing_frequency_dialog import (
    MissingFrequencyDialog,
    IgnoredFrequencyWordsDialog,
    IGNORED_WORDS_KEY,
)

# Logic
from logic.dictionary_loader import load_dictionary_with_metadata
from logic.metadata_store import METADATA_ROOT, save_metadata
from logic.settings_store import load_settings, save_settings
from logic.frequency_importer import (
    DEFAULT_UK_FREQUENCY_URL,
    download_frequency_text,
    parse_frequency_text,
    parse_frequency_file,
)

from ui.find_replace_dialog import FindReplaceDialog

import os
import subprocess


class StenoApp(tk.Tk):
    def __init__(self):
        self._set_windows_app_id()
        super().__init__()

        self.title("StenoLab")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self._apply_window_icon()

        # Theme - read persisted choice (default: dark)
        settings = load_settings()
        self._theme_mode = settings.get("theme", "dark")
        self.theme_var = tk.StringVar(value=self._theme_mode)

        apply_steno_theme(self, mode=self._theme_mode)

        # Search panel collapse state - default to collapsed for a clean
        # opening view, same philosophy as the Filter panel.
        self._search_collapsed = settings.get("search_collapsed", True)

        self.tabs = {}
        self._find_replace_dlg = None   # singleton
        self._restoring_tabs = False

        # Track which dictionary paths have been backed up since the program
        # started.  Each path triggers exactly one open-time backup; saves
        # then add their own pre-save backups on top.
        self._backed_up_this_session: set = set()

        self._create_menu()
        self._create_layout()

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Keyboard shortcuts
        self.bind("<Control-s>", lambda e: self._save_current_dictionary())

        # Type-ahead: forward bare keystrokes to the Text search field when no
        # input widget currently has focus.
        self.bind_all("<KeyPress>", self._maybe_route_type_ahead, add="+")

        # Reopen tabs from previous session
        self._restore_open_tabs()
        self._refresh_undo_buttons()

        # Re-apply title bar after the window is mapped, so DWM has a real HWND
        # to operate on. This makes the dark title bar reliably stick on Windows.
        self.after(50, lambda: set_titlebar_dark(self, self._theme_mode == "dark"))
        self.after(400, self._poll_statusbar)

    @staticmethod
    def _set_windows_app_id():
        """Give pythonw-launched windows their own taskbar identity on Windows."""
        if os.name != "nt":
            return
        try:
            import ctypes
            app_id = "StenoLab.DictionaryEditor"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except (AttributeError, OSError, ImportError):
            pass

    def _apply_window_icon(self):
        """Use the bundled book icon for the window/taskbar when available."""
        asset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        png_path = os.path.join(asset_dir, "stenolab.png")
        ico_path = os.path.join(asset_dir, "stenolab.ico")
        try:
            if os.path.exists(png_path):
                self._icon_image = tk.PhotoImage(file=png_path)
                self.iconphoto(True, self._icon_image)
            if os.name == "nt" and os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except tk.TclError:
            pass

    # ------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------
    def _create_menu(self):
        menus = []   # (title, menu) for the themed MenuBar

        # ── File ──────────────────────────────────────────────────
        file_menu = tk.Menu(self, tearoff=0)
        file_menu.add_command(
            label="Open Dictionary...",
            command=self._open_dictionary,
            accelerator="Ctrl+O",
        )
        file_menu.add_command(
            label="Save Dictionary",
            command=self._save_current_dictionary,
            accelerator="Ctrl+S",
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Export for iPad...",
            command=self._export_for_ipad,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Close Dictionary",
            command=self._close_current_dictionary,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menus.append(("File", file_menu))

        # ── Edit ──────────────────────────────────────────────────
        edit_menu = tk.Menu(self, tearoff=0)
        edit_menu.add_command(
            label="Undo",
            command=self._undo,
            accelerator="Ctrl+Z",
        )
        edit_menu.add_command(
            label="Redo",
            command=self._redo,
            accelerator="Ctrl+Y",
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Add Entry",
            command=self._open_add_entry_dialog,
            accelerator="Ctrl+N",
        )
        edit_menu.add_command(
            label="Edit Entry",
            command=self._open_edit_entry_dialog,
            accelerator="Ctrl+E",
        )
        edit_menu.add_command(
            label="Delete Selected",
            command=self._delete_selected,
            accelerator="Del",
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Toggle Bookmark",
            command=self._toggle_bookmark,
            accelerator="Ctrl+B",
        )
        menus.append(("Edit", edit_menu))

        # ── Tools ─────────────────────────────────────────────────
        tools_menu = tk.Menu(self, tearoff=0)
        tools_menu.add_command(
            label="Restore Backup...",
            command=self._restore_backup,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Open Backup Folder",
            command=self._open_backup_folder,
        )
        tools_menu.add_command(
            label="Open Metadata Folder",
            command=self._open_metadata_folder,
        )
        tools_menu.add_separator()
        convert_menu = tk.Menu(tools_menu, tearoff=0)
        convert_menu.add_command(
            label="JSON to RTF...",
            command=lambda: self._convert_dictionary(".json", ".rtf"),
        )
        convert_menu.add_command(
            label="RTF to JSON...",
            command=lambda: self._convert_dictionary(".rtf", ".json"),
        )
        tools_menu.add_cascade(label="Convert Dictionary", menu=convert_menu)
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Import Frequency List...",
            command=self._import_frequency_list,
        )
        tools_menu.add_command(
            label="Review Missing Frequency Words...",
            command=self._review_missing_frequency_words,
        )
        tools_menu.add_command(
            label="Manage Ignored Frequency Words...",
            command=self._manage_ignored_frequency_words,
        )
        menus.append(("Tools", tools_menu))

        # ── View ──────────────────────────────────────────────────
        view_menu = tk.Menu(self, tearoff=0)
        # A radio pair, so exactly one of Light / Dark is always ticked.
        for label, mode in (("Light", "light"), ("Dark", "dark")):
            view_menu.add_radiobutton(
                label=label,
                variable=self.theme_var,
                value=mode,
                command=self._toggle_theme,
            )
        menus.append(("View", view_menu))

        # ── Help ──────────────────────────────────────────────────
        help_menu = tk.Menu(self, tearoff=0)
        help_menu.add_command(
            label="User Manual",
            command=self._open_user_manual,
        )
        menus.append(("Help", help_menu))

        # A themed bar instead of the native Windows one, which ignores the
        # theme and stays white in dark mode.
        self.menubar = MenuBar(self, menus)
        self.menubar.pack(fill=tk.X, side=tk.TOP)
        self.menubar.bind_alt_keys(self)

        # Keyboard accelerators
        self.bind("<Control-o>", lambda e: self._open_dictionary())
        self.bind("<Control-n>", lambda e: self._open_add_entry_dialog())
        self.bind("<Control-e>", lambda e: self._open_edit_entry_dialog())
        self.bind("<Control-b>", lambda e: self._toggle_bookmark())
        self.bind("<Control-f>", lambda e: self._open_find_replace())
        self.bind("<Control-z>", lambda e: self._undo())
        self.bind("<Control-y>", lambda e: self._redo())
        self.bind("<Control-Z>", lambda e: self._redo())   # Ctrl+Shift+Z
        self.bind("<F3>", lambda e: self._find_next_global())
        self.bind("<Shift-F3>", lambda e: self._find_prev_global())

    # ------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------
    def _create_layout(self):

        self.toolbar = Toolbar(
            self,
            callbacks={
                "add":       self._open_add_entry_dialog,
                "edit":      self._open_edit_entry_dialog,
                "find":      self._open_find_replace,
                "bookmarks": self._toggle_bookmark,
                "open":      self._open_dictionary,
                "save":      self._save_current_dictionary,
                "undo":      self._undo,
                "redo":      self._redo,
            }
        )
        self.toolbar.pack(fill=tk.X, padx=10, pady=(8, 0))

        self.content_frame = ttk.Frame(self, style="AppShell.TFrame")
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.bind("<Button-3>", self._on_tab_right_click)
        self.notebook.bind("<Button-2>", self._on_tab_middle_click)
        self.notebook.bind("<ButtonPress-1>", self._on_tab_drag_start, add="+")
        self.notebook.bind("<B1-Motion>", self._on_tab_drag_motion, add="+")
        self.notebook.bind("<ButtonRelease-1>", self._on_tab_drag_end, add="+")
        self._drag_tab_id = None
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.statusbar = StatusBar(self, on_save_all=self._save_all_dictionaries)
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)

        self.statusbar.update_status(entries=0, dictionaries=0, active="None", unsaved=0)

    # ------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------
    def _on_tab_changed(self, event=None):
        tab = self._get_active_tab()
        previous, self._last_active_tab = getattr(self, "_last_active_tab", None), tab
        if tab:
            tab.event_generate("<<DictionaryTabActivated>>")
            # Carry the word selected in the tab just left across, so one
            # word can be compared quickly between dictionaries.
            if previous is not None and previous is not tab and not self._restoring_tabs:
                try:
                    target = previous.follow_target() if previous.winfo_exists() else None
                except tk.TclError:
                    target = None
                if target:
                    tab.follow(target)
            self.statusbar.update_status(
                entries=len(tab.entries),
                active=tab.name,
            )
            if not self._restoring_tabs:
                self._save_open_tabs()
        self._refresh_undo_buttons()

    def _get_active_tab(self):
        try:
            selected = self.notebook.select()
            # With no tabs, select() is "" and nametowidget("") would return
            # the main window itself, not a tab.
            if not selected:
                return None
            widget = self.notebook.nametowidget(selected)
        except Exception:
            return None
        return widget if isinstance(widget, DictionaryTab) else None

    def _tab_id_at(self, x, y):
        try:
            if not self.notebook.identify(x, y):
                return None
            idx = self.notebook.index(f"@{x},{y}")
            return self.notebook.tabs()[idx]
        except (IndexError, tk.TclError):
            return None

    def _on_tab_drag_start(self, event):
        self._drag_tab_id = self._tab_id_at(event.x, event.y)

    def _on_tab_drag_motion(self, event):
        if not self._drag_tab_id:
            return
        target_id = self._tab_id_at(event.x, event.y)
        if not target_id or target_id == self._drag_tab_id:
            return
        try:
            current_index = self.notebook.index(self._drag_tab_id)
            target_index = self.notebook.index(target_id)
            bx, _, bw, _ = self.notebook.bbox(target_index)
            if event.x > bx + (bw / 2):
                target_index += 1
            if current_index < target_index:
                target_index -= 1
            if current_index == target_index:
                return
            self.notebook.insert(target_index, self._drag_tab_id)
            self.notebook.select(self._drag_tab_id)
        except tk.TclError:
            pass

    def _on_tab_drag_end(self, event):
        if self._drag_tab_id:
            self._save_open_tabs()
        self._drag_tab_id = None

    # ------------------------------------------------------------
    # Right-click on tab heading
    # ------------------------------------------------------------
    def _on_tab_middle_click(self, event):
        """Middle-click on a tab heading closes that tab (after the usual
        unsaved-changes prompt)."""
        try:
            element = self.notebook.identify(event.x, event.y)
        except tk.TclError:
            return
        if not element:
            return
        try:
            tab_index = self.notebook.index(f"@{event.x},{event.y}")
            tab_id = self.notebook.tabs()[tab_index]
        except (IndexError, tk.TclError):
            return
        self.notebook.select(tab_id)
        self._close_current_dictionary()

    def _on_tab_right_click(self, event):
        """
        Show a context menu when the user right-clicks a tab heading.
        We use ttk.Notebook.identify(x, y) to find which tab was clicked;
        when the click is on the tab area it returns 'label', otherwise
        an empty string (and we ignore it).
        """
        try:
            element = self.notebook.identify(event.x, event.y)
        except tk.TclError:
            return
        if not element:
            return

        # Find the tab index under the cursor
        try:
            tab_index = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return

        # Get the underlying widget for that tab
        try:
            tab_id = self.notebook.tabs()[tab_index]
            tab_widget = self.notebook.nametowidget(tab_id)
        except (IndexError, tk.TclError):
            return

        if not isinstance(tab_widget, DictionaryTab):
            return

        # Switch to the right-clicked tab so subsequent commands operate on it.
        # Without this the user might right-click tab B intending to close it
        # but the "active tab" is still A.
        self.notebook.select(tab_id)

        menu = tk.Menu(self, tearoff=0)
        is_dirty = bool(getattr(tab_widget, "_json_dirty", False))

        # Save - only meaningful if there are unsaved changes
        if is_dirty:
            menu.add_command(label="Save", command=self._save_current_dictionary)
        else:
            menu.add_command(label="Save", state="disabled")

        menu.add_command(label="Save As...", command=self._save_as_dictionary)
        menu.add_separator()
        menu.add_command(label="Open Containing Folder",
                         command=lambda w=tab_widget: self._open_containing_folder(w))
        menu.add_command(label="Restore Backup...", command=self._restore_backup)
        menu.add_separator()
        menu.add_command(label="Close", command=self._close_current_dictionary)
        other_count = max(0, len(self.notebook.tabs()) - 1)
        menu.add_command(
            label=f"Close Other Tabs ({other_count})",
            command=lambda w=tab_widget: self._close_other_tabs(w),
            state=("normal" if other_count else "disabled"),
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _close_other_tabs(self, keep_widget):
        """Close every tab except ``keep_widget``, prompting for unsaved changes."""
        others = []
        for tab_id in list(self.notebook.tabs()):
            try:
                w = self.notebook.nametowidget(tab_id)
            except tk.TclError:
                continue
            if w is not keep_widget:
                others.append(w)
        if not others:
            return
        for widget in others:
            try:
                self.notebook.select(widget)
            except tk.TclError:
                continue
            self._close_current_dictionary()
        try:
            self.notebook.select(keep_widget)
        except tk.TclError:
            pass

    def _open_containing_folder(self, tab_widget):
        """Reveal the tab's dictionary file in the system file browser."""
        path = getattr(tab_widget, "dict_path", None)
        if not path:
            messagebox.showinfo(
                "Open Containing Folder",
                "This dictionary has no file path yet (it hasn't been saved).",
            )
            return
        folder = os.path.dirname(path)
        if not folder:
            return
        self._open_folder_in_explorer(folder)

    def _save_as_dictionary(self):
        """Save the active tab's dictionary to a chosen new path."""
        from tkinter import filedialog
        tab = self._get_active_tab()
        if tab is None:
            return

        initial = os.path.basename(tab.dict_path) if tab.dict_path else "dictionary.json"
        new_path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Dictionary As",
            defaultextension=os.path.splitext(initial)[1] or ".json",
            filetypes=[("JSON Dictionary", "*.json"), ("RTF/CRE Dictionary", "*.rtf")],
            initialfile=initial,
        )
        if not new_path:
            return

        new_name, _ = os.path.splitext(os.path.basename(new_path))
        new_key = self._tab_key_for_path(new_path)
        if new_key in self.tabs and self.tabs[new_key] is not tab:
            messagebox.showerror(
                "Save As Failed",
                "That dictionary is already open in another tab.",
            )
            return

        # Repoint the tab at the new path and save.  The original file is
        # left untouched — this is "fork", not "rename".
        old_path = tab.dict_path
        tab.dict_path = new_path

        # Update the tab title and self.tabs key
        old_key = next((k for k, t in self.tabs.items() if t is tab), None)
        if old_key is not None and old_key != new_key:
            del self.tabs[old_key]
            self.tabs[new_key] = tab
            tab.name = new_name
            self.notebook.tab(tab, text=new_name)

        try:
            saved = tab.save_json()
        except Exception as e:
            messagebox.showerror(
                "Save As Failed",
                f"Could not save dictionary to {os.path.basename(new_path)}:\n\n{e}",
            )
            saved = False

        if not saved:
            # Roll back the path and key change so the user isn't left in a weird state
            tab.dict_path = old_path
            if old_key is not None and old_key != new_key:
                del self.tabs[new_key]
                self.tabs[old_key] = tab
                tab.name, _ = os.path.splitext(os.path.basename(old_path)) if old_path else (new_name, "")
                self.notebook.tab(tab, text=tab.name)
            return
        if hasattr(tab, "_refresh_dictionary_header"):
            tab._refresh_dictionary_header()

    # ------------------------------------------------------------
    # Export for iPad
    # ------------------------------------------------------------
    def _export_for_ipad(self):
        """Write the active tab's visible rows, with their comments, as a
        review file for the iPad viewer (web/).  The current search and
        filters decide what is exported."""
        from tkinter import filedialog
        from logic.review_export import build_review, write_review

        tab = self._get_active_tab()
        if tab is None:
            messagebox.showinfo("Export for iPad", "Open a dictionary first.")
            return
        entries = tab.visible_entries()
        if not entries:
            messagebox.showinfo("Export for iPad", "No entries are showing to export.")
            return

        description = tab.active_view_description()
        suffix = "all entries" if description == "All entries" else "review"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export for iPad",
            initialdir=os.path.dirname(tab.dict_path) if tab.dict_path else None,
            initialfile=f"{tab.name} - {suffix}.json",
            defaultextension=".json",
            filetypes=[("StenoLab review file", "*.json")],
        )
        if not path:
            return
        review = build_review(entries, tab.metadata, name=tab.name,
                              source=tab.dict_path, description=description)
        try:
            write_review(path, review)
        except OSError as e:
            messagebox.showerror("Export for iPad", f"Could not write the file:\n\n{e}")
            return
        messagebox.showinfo(
            "Export for iPad",
            f"Exported {len(entries):,} entries ({description}) to "
            f"{os.path.basename(path)}.\n\nOpen it in the StenoLab viewer on the iPad.",
        )

    # ------------------------------------------------------------
    # Convert Dictionary
    # ------------------------------------------------------------
    _FORMAT_FILETYPES = {
        ".json": ("JSON Dictionary", "*.json"),
        ".rtf": ("RTF/CRE Dictionary", "*.rtf"),
    }

    def _convert_dictionary(self, src_ext, dst_ext):
        """Convert a dictionary file on disk to the other format."""
        from tkinter import filedialog
        from logic.dictionary_writer import convert_dictionary
        from logic.backup_store import backup_dictionary

        src_label = self._FORMAT_FILETYPES[src_ext][0]
        src = filedialog.askopenfilename(
            parent=self,
            title=f"Convert {src_label}",
            filetypes=[self._FORMAT_FILETYPES[src_ext]],
            defaultextension=src_ext,
        )
        if not src:
            return

        # Conversion reads the file on disk, so unsaved edits are not included.
        src_tab = self.tabs.get(self._tab_key_for_path(src))
        if src_tab is not None and getattr(src_tab, "_json_dirty", False):
            if not messagebox.askyesno(
                "Unsaved Changes",
                f"{os.path.basename(src)} has unsaved changes, which will not "
                "be included in the conversion.\n\nConvert the saved version?",
            ):
                return

        name, _ = os.path.splitext(os.path.basename(src))
        dst = filedialog.asksaveasfilename(
            parent=self,
            title="Save Converted Dictionary As",
            initialdir=os.path.dirname(src),
            initialfile=name + dst_ext,
            filetypes=[self._FORMAT_FILETYPES[dst_ext]],
            defaultextension=dst_ext,
        )
        if not dst:
            return
        if self._tab_key_for_path(dst) in self.tabs:
            messagebox.showerror(
                "Convert Failed",
                f"{os.path.basename(dst)} is open in a tab. Close it before "
                "converting over it.",
            )
            return

        # The save dialog has already confirmed any overwrite; keep a backup
        # of the file being replaced, as a normal save would.
        ok, msg = backup_dictionary(dst, kind="save")
        if not ok and not messagebox.askyesno(
            "Backup Failed",
            f"Could not back up {os.path.basename(dst)}:\n\n{msg}\n\n"
            "Overwrite it anyway?",
        ):
            return

        try:
            count = convert_dictionary(src, dst)
        except Exception as e:
            messagebox.showerror(
                "Convert Failed",
                f"Could not convert {os.path.basename(src)}:\n\n{e}",
            )
            return

        if messagebox.askyesno(
            "Conversion Complete",
            f"Converted {count:,} entries to {os.path.basename(dst)}.\n\n"
            "Open it now?",
        ):
            self._open_dictionary_path(dst)

    # ------------------------------------------------------------
    # Open Dictionary
    # ------------------------------------------------------------
    def _open_dictionary(self):
        path = ask_open_dictionary(self)
        if not path:
            return
        if os.path.isdir(path):
            messagebox.showerror(
                "Invalid Selection",
                "Please select a JSON or RTF dictionary file, not a folder."
            )
            return
        self._open_dictionary_path(path)

    def _tab_key_for_path(self, path):
        """Stable key for tab bookkeeping; display names remain user-friendly."""
        return os.path.normcase(os.path.abspath(path))

    def _open_dictionary_path(self, path):
        """Load a dictionary from path and add it as a tab. Safe to call on startup."""
        if not os.path.isfile(path):
            return

        tab_key = self._tab_key_for_path(path)
        if tab_key in self.tabs:
            self.notebook.select(self.tabs[tab_key])
            return

        try:
            entries, metadata, _ = load_dictionary_with_metadata(path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load dictionary:\n{e}")
            return

        # Take an open-time backup so the user has a snapshot of the file as
        # it was when they started working today.  Done once per path per
        # session — reopening the same file later in the session won't
        # produce a redundant backup.
        if path not in self._backed_up_this_session:
            try:
                from logic.backup_store import backup_dictionary
                backup_dictionary(path, kind="open")
            except Exception:
                pass  # never let a backup failure block opening
            self._backed_up_this_session.add(path)

        base = os.path.basename(path)
        name, _ = os.path.splitext(base)

        tab = DictionaryTab(
            self.notebook,
            name=name,
            on_entries_changed=self._on_entries_changed,
            on_search_broadcast=self._broadcast_search_to_siblings,
            on_search_collapse_changed=self._on_search_collapse_changed,
            initial_search_collapsed=self._search_collapsed,
        )

        tab.dict_path = path
        tab.load_entries(entries, metadata)

        # If any open tab has scope='All Dictionaries' with an active query,
        # mirror it onto this new tab so the cross-dictionary view stays
        # consistent when the user opens another file.  That call also runs
        # _apply_filters as a side effect.  If no broadcast source exists we
        # still need an initial filter pass — load_entries deliberately skips
        # it on the assumption that the caller follows up with a search.
        if not self._sync_new_tab_with_broadcast_source(tab):
            try:
                tab.apply_search(tab.searchbar.get_config())
            except Exception:
                pass

        self.notebook.add(tab, text=name)
        self.tabs[tab_key] = tab
        self.notebook.select(tab)
        if hasattr(tab, "_refresh_dictionary_header"):
            tab._refresh_dictionary_header()

        self.statusbar.update_status(
            entries=len(entries),
            dictionaries=len(self.tabs),
            active=name
        )
        self._refresh_unsaved_status()

    # ------------------------------------------------------------
    # Save Dictionary
    # ------------------------------------------------------------
    def _save_current_dictionary(self):
        tab = self._get_active_tab()
        if not tab:
            return
        tab.save_json()
        self._refresh_unsaved_status()

    # ------------------------------------------------------------
    # Close Dictionary
    # ------------------------------------------------------------
    def _close_current_dictionary(self):
        if not self.tabs:
            return

        widget = self._get_active_tab()
        if widget is None:
            return

        # Prompt if dirty
        if getattr(widget, "_json_dirty", False) and widget.dict_path:
            from ui.save_changes_dialog import (
                ask_save_changes, RESULT_SAVE, RESULT_DISCARD, RESULT_CANCEL,
            )
            result, to_save = ask_save_changes(
                self, [widget.dict_path], context="close",
            )
            if result == RESULT_CANCEL:
                return
            if result == RESULT_SAVE and widget.dict_path in to_save:
                try:
                    saved = widget.save_json()
                except Exception as e:
                    messagebox.showerror(
                        "Save Failed",
                        f"Could not save {os.path.basename(widget.dict_path)}:\n\n{e}",
                    )
                    return
                if not saved:
                    return

        # Drop the tab (use widget identity, not title - the title may have a
        # ' *' suffix when dirty)
        name_to_remove = next(
            (n for n, t in self.tabs.items() if t is widget), None
        )
        if name_to_remove is not None:
            del self.tabs[name_to_remove]
        self.notebook.forget(widget)
        # forget() only unmaps the tab; destroying it frees its entries and
        # table, which otherwise stay in memory until the app exits.
        widget.destroy()

        active = self._get_active_tab() if self.tabs else None
        if active is not None:
            self.statusbar.update_status(
                entries=len(active.entries),
                dictionaries=len(self.tabs),
                active=active.name
            )
        else:
            self.statusbar.update_status(entries=0, dictionaries=0, active="None", unsaved=0)

    # ------------------------------------------------------------
    # Add Entry
    # ------------------------------------------------------------
    def _open_add_entry_dialog(self):
        if not self.tabs:
            return
        active_tab = self._get_active_tab()
        if not active_tab:
            return
        active_tab._open_add_dialog()

    # ------------------------------------------------------------
    # Edit Entry
    # ------------------------------------------------------------
    def _open_edit_entry_dialog(self):
        if not self.tabs:
            return
        active_tab = self._get_active_tab()
        if not active_tab:
            return
        active_tab._open_edit_dialog_for_selected()

    # ------------------------------------------------------------
    # Find & Replace
    # ------------------------------------------------------------
    def _open_find_replace(self):
        if self._find_replace_dlg and self._find_replace_dlg.winfo_exists():
            self._find_replace_dlg.lift()
            self._find_replace_dlg.focus()
            return
        self._find_replace_dlg = FindReplaceDialog(self, self._get_active_tab)

    # ------------------------------------------------------------
    # Toggle Bookmark
    # ------------------------------------------------------------
    def _toggle_bookmark(self):
        tab = self._get_active_tab()
        if tab:
            tab.toggle_bookmark_selected()

    # ------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------
    def _undo(self):
        tab = self._get_active_tab()
        if tab:
            tab.undo()
            self._refresh_undo_buttons()

    def _redo(self):
        tab = self._get_active_tab()
        if tab:
            tab.redo()
            self._refresh_undo_buttons()

    def _refresh_undo_buttons(self):
        """Sync the toolbar undo/redo and Save button states with the active tab."""
        tab = self._get_active_tab()
        if tab and hasattr(tab, "_undo_stack"):
            self.toolbar.refresh_undo_redo(
                can_undo=tab._undo_stack.can_undo,
                can_redo=tab._undo_stack.can_redo,
            )
            self.toolbar.set_save_enabled(bool(getattr(tab, "_json_dirty", False)))
        else:
            self.toolbar.refresh_undo_redo(can_undo=False, can_redo=False)
            self.toolbar.set_save_enabled(False)

    # ------------------------------------------------------------
    # Delete (menu / accelerator route)
    # ------------------------------------------------------------
    def _delete_selected(self):
        tab = self._get_active_tab()
        if tab:
            tab.delete_selected()

    # ------------------------------------------------------------
    # Entries changed (callback from DictionaryTab)
    # ------------------------------------------------------------
    def _on_entries_changed(self, count):
        self.statusbar.update_status(entries=count)
        self._refresh_unsaved_status()
        self._refresh_undo_buttons()

    def _count_dirty_tabs(self) -> int:
        return sum(1 for t in self.tabs.values() if getattr(t, "_json_dirty", False))

    def _refresh_unsaved_status(self):
        self.statusbar.update_status(unsaved=self._count_dirty_tabs())

    def _poll_statusbar(self):
        # Keep unsaved count and undo button states current even when edits
        # happen deep in tab/dialog logic.
        self._refresh_unsaved_status()
        self._refresh_undo_buttons()
        self.after(400, self._poll_statusbar)

    def _save_all_dictionaries(self):
        dirty_tabs = [t for t in self.tabs.values()
                      if getattr(t, "_json_dirty", False) and getattr(t, "dict_path", None)]
        if not dirty_tabs:
            return

        failed = []
        for tab in dirty_tabs:
            try:
                saved = tab.save_json()
            except Exception as e:
                failed.append((tab, str(e)))
                continue
            if not saved:
                failed.append((tab, "Save was cancelled or failed."))

        if failed:
            messagebox.showerror(
                "Save All",
                "Some dictionaries could not be saved:\n\n" +
                "\n".join(f"- {getattr(tab, 'name', 'dictionary')}: {err}" for tab, err in failed),
            )

        self._refresh_unsaved_status()

    def _find_next_global(self):
        if self._find_replace_dlg and self._find_replace_dlg.winfo_exists():
            self._find_replace_dlg._find_next()
            self._find_replace_dlg.lift()
            return "break"
        self._open_find_replace()
        if self._find_replace_dlg and self._find_replace_dlg.winfo_exists():
            self._find_replace_dlg._find_next()
        return "break"

    def _find_prev_global(self):
        if self._find_replace_dlg and self._find_replace_dlg.winfo_exists():
            self._find_replace_dlg._find_prev()
            self._find_replace_dlg.lift()
            return "break"
        self._open_find_replace()
        if self._find_replace_dlg and self._find_replace_dlg.winfo_exists():
            self._find_replace_dlg._find_prev()
        return "break"

    # ------------------------------------------------------------
    # Tab persistence
    # ------------------------------------------------------------
    def _save_open_tabs(self):
        paths = []
        active_path = None
        active_tab = self._get_active_tab()
        if active_tab is not None:
            active_path = getattr(active_tab, "dict_path", None)
        for tab_id in self.notebook.tabs():
            try:
                widget = self.notebook.nametowidget(tab_id)
                if hasattr(widget, "dict_path") and widget.dict_path:
                    paths.append(widget.dict_path)
            except Exception:
                continue
        settings = load_settings()
        settings["open_tabs"] = paths
        if active_path:
            settings["active_tab"] = active_path
        else:
            settings.pop("active_tab", None)
        save_settings(settings)

    def _restore_open_tabs(self):
        settings = load_settings()
        active_path = settings.get("active_tab")
        self._restoring_tabs = True
        try:
            for path in settings.get("open_tabs", []):
                try:
                    self._open_dictionary_path(path)
                except Exception:
                    pass
        finally:
            self._restoring_tabs = False

        if active_path:
            tab = self.tabs.get(os.path.normcase(os.path.abspath(active_path)))
            if tab is not None:
                try:
                    self.notebook.select(tab)
                except tk.TclError:
                    pass

    def _on_close(self):
        """
        Close the application.  Prompt about any tabs with unsaved JSON
        changes; the user can save the ones they want, discard everything,
        or cancel and stay open.

        Tabs with no unsaved changes never enter the prompt — their
        dictionary and metadata are already in sync with disk (metadata
        is saved together with the dictionary).
        """
        from ui.save_changes_dialog import (
            ask_save_changes, RESULT_SAVE, RESULT_DISCARD, RESULT_CANCEL,
        )

        # Find dirty tabs in the order they appear in the notebook
        dirty_widgets = []
        for tab_id in self.notebook.tabs():
            try:
                w = self.notebook.nametowidget(tab_id)
            except Exception:
                continue
            if getattr(w, "_json_dirty", False) and getattr(w, "dict_path", None):
                dirty_widgets.append(w)

        if dirty_widgets:
            paths = [w.dict_path for w in dirty_widgets]
            result, to_save = ask_save_changes(self, paths, context="exit")
            if result == RESULT_CANCEL:
                return  # user changed their mind; stay open
            if result == RESULT_SAVE:
                save_set = set(to_save)
                for w in dirty_widgets:
                    if w.dict_path in save_set:
                        try:
                            saved = w.save_json()
                        except Exception as e:
                            saved = False
                            err = str(e)
                        else:
                            err = "Save was cancelled or failed."
                        if not saved:
                            cont = messagebox.askyesno(
                                "Save Failed",
                                f"Could not save "
                                f"{os.path.basename(w.dict_path)}:\n\n{err}\n\n"
                                f"Continue closing anyway?",
                            )
                            if not cont:
                                return

        self._save_open_tabs()
        self._refresh_unsaved_status()
        self.destroy()

    # ------------------------------------------------------------
    # Search
    # ------------------------------------------------------------
    def _broadcast_search_to_siblings(self, source_tab, config):
        """
        Mirror a tab's search query to every other open tab.

        Called when the source tab has scope='All Dictionaries' and its
        search inputs change.  The receiving tabs adopt the same query
        without re-broadcasting (their on_search_changed is suppressed
        during the receive).  Each receiving tab keeps its own scope —
        only the source tab is in cross-dictionary mode.
        """
        if not self.tabs:
            return
        for tab in self.tabs.values():
            if tab is source_tab:
                continue
            try:
                tab.set_search_quietly(config)
            except Exception:
                pass

    def _sync_new_tab_with_broadcast_source(self, new_tab) -> bool:
        """When opening a new tab, inherit any active 'All Dictionaries' query.

        Returns True if a broadcast source was found and mirrored (which also
        triggers an initial filter pass), False otherwise — so the caller
        knows whether it still needs to run the initial filter itself.
        """
        for tab in self.tabs.values():
            if tab is new_tab:
                continue
            cfg = getattr(tab, "search_config", None) or {}
            if cfg.get("scope") == "All Dictionaries" and (
                cfg.get("text_query") or cfg.get("steno_query")
            ):
                try:
                    new_tab.set_search_quietly(cfg)
                except Exception:
                    return False
                return True
        return False

    def _on_search_collapse_changed(self, collapsed: bool):
        """Persist the search-panel collapse state as the default for new tabs."""
        self._search_collapsed = collapsed
        settings = load_settings()
        settings["search_collapsed"] = collapsed
        save_settings(settings)

    # ------------------------------------------------------------
    # Type-ahead routing
    # ------------------------------------------------------------
    # Keysyms we never want to route through to the search box - navigation,
    # editing, modifier, and function keys.
    _NON_TYPING_KEYSYMS = frozenset({
        "Tab", "ISO_Left_Tab",
        "Shift_L", "Shift_R", "Control_L", "Control_R",
        "Alt_L", "Alt_R", "Meta_L", "Meta_R",
        "Caps_Lock", "Num_Lock", "Scroll_Lock",
        "Escape", "Return", "KP_Enter", "BackSpace", "Delete",
        "Up", "Down", "Left", "Right",
        "Home", "End", "Page_Up", "Page_Down",
        "Insert", "Print", "Pause", "Menu",
    })

    def _maybe_route_type_ahead(self, event):
        """Route bare letter/digit keystrokes to the Text search field."""
        if not self.tabs:
            return None

        # Skip if focus is already in an input or the menu.  When no widget
        # has focus at all (e.g. after the window first appears, or briefly
        # when the user clicks on empty chrome), we still want to route the
        # keystroke - nothing else is going to consume it.
        focus = self.focus_get()
        if focus is not None:
            try:
                cls = focus.winfo_class()
            except tk.TclError:
                cls = None
            if cls in ("Entry", "TEntry", "Text", "TCombobox",
                       "Spinbox", "Listbox", "Menu"):
                return None

        keysym = event.keysym
        active_tab = self._get_active_tab()
        if active_tab is None or not hasattr(active_tab, "type_ahead"):
            return None

        # With the search panel closed there is no field to backspace in,
        # so Backspace edits the routed query too.
        if keysym == "BackSpace" and not (event.state & 0x0004):
            return "break" if active_tab.type_ahead(backspace=True) else None

        if keysym in self._NON_TYPING_KEYSYMS:
            return None
        if keysym.startswith("F") and keysym[1:].isdigit():   # F1–F12
            return None

        # Ignore Ctrl-* shortcuts (Control bit 0x4 is reliable on all
        # platforms).  We deliberately do NOT test the old "Alt" bits
        # (0x8 / 0x80 / 0x20000): on Windows a lock key such as Num Lock sets
        # 0x8 on every keystroke, which was being misread as Alt and killing
        # type-ahead whenever Num Lock was on.  A genuine Alt/Ctrl combo yields
        # an empty or non-printable char, which the isprintable() check rejects.
        if event.state & 0x0004:
            return None

        char = event.char
        if not char or not char.isprintable():
            return None

        # Route to the active tab's text search.  The tab inserts the char
        # itself (into the open field, or straight into the query when the
        # panel is closed), so we must NOT also insert it here.
        return "break" if active_tab.type_ahead(char) else None

    # ------------------------------------------------------------
    # Theme toggle
    # ------------------------------------------------------------
    def _toggle_theme(self):
        """Switch between dark and light mode and persist the choice."""
        if self.theme_var.get() == self._theme_mode:
            return  # the already-ticked mode was clicked again
        window_state, window_geometry = self._snapshot_window_geometry()

        self._theme_mode = self.theme_var.get()
        apply_theme(self, self._theme_mode)
        self.after_idle(lambda: self._restore_after_theme_switch(
            window_state, window_geometry,
        ))

        # Update Find & Replace if it happens to be open - apply_theme already
        # walked the main window's tree, but a non-modal Toplevel is a separate
        # tree, so we refresh it explicitly.
        if self._find_replace_dlg and self._find_replace_dlg.winfo_exists():
            from ui.theme import refresh_theme_recursive
            refresh_theme_recursive(self._find_replace_dlg)
            set_titlebar_dark(self._find_replace_dlg,
                              dark=(self._theme_mode == "dark"))

        # Persist
        settings = load_settings()
        settings["theme"] = self._theme_mode
        save_settings(settings)

    def _snapshot_window_geometry(self):
        try:
            return self.state(), self.geometry()
        except tk.TclError:
            return "normal", None

    def _restore_after_theme_switch(self, window_state, window_geometry):
        # Column widths need no restoring: the tksheet table keeps its own
        # widths across a theme switch.
        try:
            if window_state == "zoomed":
                self.state("zoomed")
            elif window_geometry:
                self.geometry(window_geometry)
        except tk.TclError:
            pass

    # ------------------------------------------------------------
    # Tools → Open Metadata Folder
    # ------------------------------------------------------------
    def _open_metadata_folder(self):
        self._open_folder_in_explorer(METADATA_ROOT)

    # ------------------------------------------------------------
    # Tools → Open Backup Folder
    # ------------------------------------------------------------
    def _open_backup_folder(self):
        from logic.backup_store import BACKUP_ROOT
        self._open_folder_in_explorer(BACKUP_ROOT)

    def _open_folder_in_explorer(self, path):
        """Cross-platform best-effort folder opener.  Silent on failure."""
        import platform
        try:
            os.makedirs(path, exist_ok=True)
            system = platform.system()
            if system == "Windows":
                os.startfile(path)  # type: ignore[attr-defined]
            elif system == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    # ------------------------------------------------------------
    # Help → User Manual
    # ------------------------------------------------------------
    def _open_user_manual(self):
        """Open the bundled HTML user manual in the default web browser."""
        import webbrowser
        from pathlib import Path
        manual = Path(__file__).resolve().parent / "docs" / "user_manual.html"
        if manual.exists():
            webbrowser.open(manual.as_uri())
        else:
            messagebox.showinfo(
                "User Manual",
                "The user manual could not be found. It should be installed "
                "at:\n\n" + str(manual),
            )

    # ------------------------------------------------------------
    # Tools → Restore Backup
    # ------------------------------------------------------------
    # ------------------------------------------------------------
    # Tools -> Import Frequency List
    # ------------------------------------------------------------
    def _load_frequency_map_from_user(self, title: str):
        choice = messagebox.askyesnocancel(
            title,
            "Use the default UK frequency list (BNC) from:\n\n"
            f"{DEFAULT_UK_FREQUENCY_URL}\n\n"
            "Choose Yes to download it now, No to pick a local file.",
        )
        if choice is None:
            return None, None

        if choice:
            text = download_frequency_text(DEFAULT_UK_FREQUENCY_URL)
            return parse_frequency_text(text), "UK BNC online list"

        path = filedialog.askopenfilename(
            parent=self,
            title="Select Frequency List",
            filetypes=[
                ("Text and CSV", "*.txt *.csv *.tsv"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return None, None
        return parse_frequency_file(path), os.path.basename(path)

    def _import_frequency_list(self):
        tab = self._get_active_tab()
        if tab is None or not getattr(tab, "dict_path", None):
            messagebox.showinfo(
                "Import Frequency List",
                "Open a dictionary first, then import frequency data.",
            )
            return

        try:
            freq_map, source = self._load_frequency_map_from_user("Import Frequency List")
        except Exception as e:
            messagebox.showerror(
                "Import Frequency List",
                f"Could not load frequency data:\n\n{e}",
            )
            return
        if freq_map is None:
            return

        if not freq_map:
            messagebox.showwarning(
                "Import Frequency List",
                "No usable frequency rows were found in that source.",
            )
            return

        updated = self._apply_frequency_map_to_tab(tab, freq_map)
        tab.invalidate_all_cached()
        # Metadata is saved together with the dictionary.  With unsaved
        # edits pending, writing it now would also write those edits'
        # metadata ahead of the dictionary, so the import waits for Save.
        deferred = bool(getattr(tab, "_json_dirty", False))
        if deferred:
            tab._metadata_dirty = True
        else:
            try:
                save_metadata(tab.dict_path, tab.metadata or {})
            except Exception as e:
                messagebox.showerror(
                    "Import Frequency List",
                    f"Imported frequencies but failed to save metadata:\n\n{e}",
                )
                return
        if hasattr(tab, "_refresh_dictionary_header"):
            tab._refresh_dictionary_header()

        try:
            tab._apply_filters()
        except Exception:
            pass

        messagebox.showinfo(
            "Import Frequency List",
            f"Imported frequencies from {source}.\n"
            f"Updated {updated:,} entries."
            + ("\n\nThey will be saved with your other unsaved changes."
               if deferred else ""),
        )

    def _apply_frequency_map_to_tab(self, tab, freq_map: dict[str, int]) -> int:
        import re

        token_re = re.compile(r"[a-z']+")

        # A scoreable entry is a plain word containing only letters and
        # apostrophes.  Entries with digits, hyphens, punctuation, or Plover
        # formatting commands (e.g. {^ing}, {-|}) are excluded — they either
        # don't appear in a word-frequency list or would get a misleading score.
        plain_word_re = re.compile(r"^[a-z']+$")

        updated = 0
        metadata = tab.metadata if tab.metadata is not None else {}
        tab.metadata = metadata

        for entry in tab.entries:
            steno   = entry.get("steno", "")
            english = (entry.get("english") or "").lower().strip()
            tokens  = token_re.findall(english)

            # Score only single plain-word entries.
            # The plain_word_re check on the raw string catches cases where
            # token_re would silently strip out disqualifying characters
            # (e.g. "Hello!" → token ["hello"] but the raw string fails the
            # check, so score stays 0).
            if len(tokens) == 1 and plain_word_re.match(english):
                score = freq_map.get(tokens[0], 0)
            else:
                score = 0

            meta = metadata.setdefault(steno, {
                "date_added": entry.get("date_added", ""),
                "modified": entry.get("modified", ""),
                "brief": False,
                "comments": "",
                "bookmarked": False,
                "frequency": 0,
            })
            if meta.get("frequency", 0) != score:
                meta["frequency"] = score
                updated += 1

        return updated

    def _review_missing_frequency_words(self):
        tab = self._get_active_tab()
        if tab is None or not getattr(tab, "dict_path", None):
            messagebox.showinfo(
                "Review Missing Frequency Words",
                "Open a dictionary first, then review missing frequency words.",
            )
            return

        try:
            freq_map, source = self._load_frequency_map_from_user(
                "Review Missing Frequency Words"
            )
        except Exception as e:
            messagebox.showerror(
                "Review Missing Frequency Words",
                f"Could not load frequency data:\n\n{e}",
            )
            return
        if freq_map is None:
            return
        if not freq_map:
            messagebox.showwarning(
                "Review Missing Frequency Words",
                "No usable frequency rows were found in that source.",
            )
            return

        candidates, omitted_count = self._missing_frequency_candidates(tab, freq_map)
        if not candidates:
            messagebox.showinfo(
                "Review Missing Frequency Words",
                "No missing frequency words were found.",
            )
            return

        dlg = MissingFrequencyDialog(
            self,
            tab,
            candidates,
            source or "frequency list",
            omitted_count=omitted_count,
        )
        dlg.focus_set()

    def _missing_frequency_candidates(self, tab, freq_map: dict[str, int]):
        import re

        max_candidates = 1000
        plain_word_re = re.compile(r"^[a-z']+$")
        settings = load_settings()
        ignored = {
            str(word).strip().lower()
            for word in settings.get(IGNORED_WORDS_KEY, [])
            if str(word).strip()
        }

        existing = set()
        for entry in tab.entries:
            english = (entry.get("english") or "").strip().lower()
            if plain_word_re.match(english):
                existing.add(english)

        missing = []
        for word, freq in freq_map.items():
            if word in existing or word in ignored or not plain_word_re.match(word):
                continue
            hint = self._possible_suffix_coverage(word, existing)
            item = {"word": word, "frequency": freq}
            if hint:
                item["status"] = "Possibly Covered"
                item["note"] = hint
            missing.append(item)
        missing.sort(key=lambda item: (-item["frequency"], item["word"]))
        omitted_count = max(0, len(missing) - max_candidates)
        return missing[:max_candidates], omitted_count

    def _possible_suffix_coverage(self, word: str, existing: set[str]) -> str:
        checks = []

        if word.endswith("ies") and len(word) > 3:
            checks.append((word[:-3] + "y", "y + ies suffix"))
        if word.endswith("es") and len(word) > 2:
            checks.append((word[:-2], "base + es suffix"))
        if word.endswith("s") and len(word) > 1:
            checks.append((word[:-1], "base + s suffix"))

        if word.endswith("ied") and len(word) > 3:
            checks.append((word[:-3] + "y", "y + ied suffix"))
        if word.endswith("ed") and len(word) > 2:
            checks.append((word[:-2], "base + ed suffix"))
            if len(word) > 3 and word[-3] == word[-4]:
                checks.append((word[:-3], "doubled consonant + ed suffix"))

        if word.endswith("ing") and len(word) > 3:
            checks.append((word[:-3], "base + ing suffix"))
            checks.append((word[:-3] + "e", "drop e + ing suffix"))
            if len(word) > 4 and word[-4] == word[-5]:
                checks.append((word[:-4], "doubled consonant + ing suffix"))

        for suffix in ("ly", "er", "est"):
            if word.endswith(suffix) and len(word) > len(suffix):
                checks.append((word[:-len(suffix)], f"base + {suffix} suffix"))

        seen = set()
        for base, label in checks:
            if not base or base in seen:
                continue
            seen.add(base)
            if base in existing:
                return f"{base} ({label})"
        return ""

    def _manage_ignored_frequency_words(self):
        dlg = IgnoredFrequencyWordsDialog(self)
        self.wait_window(dlg)

    def _restore_backup(self):
        """
        Show the restore dialog, then replace the active dictionary's file
        with the chosen backup and reload the tab.

        The current state is itself backed up first, so the user can undo
        a wrong restore by restoring the snapshot taken at the moment
        before the restore.
        """
        from ui.restore_backup_dialog import RestoreBackupDialog
        from logic.backup_store import (
            backup_dictionary, read_backup_contents, write_restored_contents,
        )

        tab = self._get_active_tab()
        if tab is None or not getattr(tab, "dict_path", None):
            messagebox.showinfo(
                "Restore Backup",
                "Open a dictionary first, then choose Tools → Restore Backup.",
            )
            return

        # Warn before overwriting unsaved JSON edits
        if getattr(tab, "_json_dirty", False):
            ok = messagebox.askyesno(
                "Unsaved Changes",
                f"{os.path.basename(tab.dict_path)} has unsaved changes that "
                f"will be lost if you restore a backup.\n\n"
                f"Continue?",
            )
            if not ok:
                return

        dlg = RestoreBackupDialog(self, tab.dict_path)
        self.wait_window(dlg)
        if dlg.selected_backup is None:
            return  # user cancelled

        # Confirmation - show the restore target so they know what they're doing
        backup = dlg.selected_backup
        confirm = messagebox.askyesno(
            "Confirm Restore",
            f"Replace {os.path.basename(tab.dict_path)} with the backup from "
            f"{backup['timestamp']}?\n\n"
            f"A new backup of the current state will be made first, so this "
            f"is reversible.",
        )
        if not confirm:
            return

        # Read the chosen backup first: the safety snapshot below prunes old
        # backups and could otherwise delete the one being restored.
        try:
            dict_bytes, meta_bytes = read_backup_contents(backup)
        except OSError as e:
            messagebox.showerror(
                "Restore Failed",
                f"Could not read the backup:\n\n{e}",
            )
            return

        # Snapshot current state before replacing
        try:
            ok, msg = backup_dictionary(tab.dict_path, kind="save")
        except Exception as e:
            ok, msg = False, str(e)
        if not ok:
            # If the safety backup fails, ask before continuing
            cont = messagebox.askyesno(
                "Backup Failed",
                f"Could not back up the current dictionary before restoring:\n\n{msg}\n\n"
                "Restore anyway?",
            )
            if not cont:
                return

        try:
            write_restored_contents(tab.dict_path, dict_bytes, meta_bytes)
        except OSError as e:
            messagebox.showerror(
                "Restore Failed",
                f"Could not restore backup:\n\n{e}",
            )
            return

        # Reload the tab from the restored file
        try:
            entries, metadata, _ = load_dictionary_with_metadata(tab.dict_path)
            tab.load_entries(entries, metadata)
            tab._set_dirty(False)
            try:
                tab.apply_search(tab.searchbar.get_config())
            except Exception:
                pass
            self.statusbar.update_status(
                entries=len(entries),
                dictionaries=len(self.tabs),
                active=tab.name,
            )
        except Exception as e:
            messagebox.showerror(
                "Reload Failed",
                f"The file was restored but could not be reloaded:\n\n{e}\n\n"
                f"Try closing and reopening the dictionary.",
            )
            return

        messagebox.showinfo(
            "Restore Complete",
            f"Restored {os.path.basename(tab.dict_path)} from backup "
            f"{backup['timestamp']}.",
        )


if __name__ == "__main__":
    app = StenoApp()
    app.mainloop()
