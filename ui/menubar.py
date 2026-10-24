# ui/menubar.py
"""
Themed menu bar.

Windows draws a window's native menu bar itself, so it ignores Tk colours
and stays white in dark mode.  This bar is ordinary themed widgets instead:
a row of titles, each opening its tk.Menu as a drop-down underneath.  The
drop-down menus take the theme colours (see theme.style_menus).

Keyboard: Alt + the underlined letter opens a menu (bind_alt_keys).
Unlike the native bar, Left / Right inside an open menu don't move to the
neighbouring menu.
"""
import tkinter as tk
from tkinter import ttk


class MenuBar(ttk.Frame):
    def __init__(self, parent, menus):
        """`menus` is a list of (title, tk.Menu); each title's first letter
        is its Alt shortcut."""
        super().__init__(parent, style="MenuBar.TFrame")
        self._items = []
        for title, menu in menus:
            label = ttk.Label(self, text=title, style="MenuBar.TLabel",
                              underline=0, padding=(9, 3))
            label.pack(side=tk.LEFT)
            label.bind("<Button-1>", lambda _e, m=menu, w=label: self.open(m, w))
            label.bind("<Enter>", lambda _e, w=label: w.configure(style="MenuBarActive.TLabel"))
            label.bind("<Leave>", lambda _e, w=label: w.configure(style="MenuBar.TLabel"))
            self._items.append((title, menu, label))

    def open(self, menu, label):
        """Show `menu` under its title.  tk_popup waits until the menu
        closes, so the title stays highlighted only while it is open."""
        label.configure(style="MenuBarActive.TLabel")
        try:
            menu.tk_popup(label.winfo_rootx(), label.winfo_rooty() + label.winfo_height())
        finally:
            menu.grab_release()
            label.configure(style="MenuBar.TLabel")

    def bind_alt_keys(self, window):
        """Alt + first letter of a title opens that menu."""
        for title, menu, label in self._items:
            for key in {title[0].lower(), title[0].upper()}:
                window.bind(f"<Alt-KeyPress-{key}>",
                            lambda _e, m=menu, w=label: (self.open(m, w), "break")[1])
