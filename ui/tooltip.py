# ui/tooltip.py
import tkinter as tk
from ui.theme import C


class Tooltip:
    """Hover tooltip for any Tk widget.  Appears after a short delay."""

    DELAY = 500   # ms before the tip appears

    def __init__(self, widget, text):
        """`text` is a string, or a function returning one, called each time
        the tip appears (for text that is costly to keep up to date)."""
        self.widget = widget
        self.text   = text
        self._tip   = None
        self._job   = None
        widget.bind("<Enter>",  self._schedule, add="+")
        widget.bind("<Leave>",  self._cancel,   add="+")
        widget.bind("<Button>", self._cancel,   add="+")

    def update_text(self, text):
        self.text = text

    # ------------------------------------------------------------------
    def _schedule(self, event=None):
        self._cancel()
        self._job = self.widget.after(self.DELAY, self._show)

    def _cancel(self, event=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        self._hide()

    def _position(self):
        """Screen position for the tip: just below the widget."""
        return (self.widget.winfo_rootx() + 8,
                self.widget.winfo_rooty() + self.widget.winfo_height() + 4)

    def _show(self):
        if self._tip:
            return
        x, y = self._position()
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        # Read C at show-time so tooltips always match the current theme,
        # even though Tooltip instances are long-lived.
        # Use a raised/inverted surface so the tip clearly floats above
        # whatever it sits next to.  In dark mode the parent is already
        # dark, so using C["bg"] alone made the tip nearly invisible.
        self._tip.configure(background=C["border"])
        tk.Label(
            self._tip,
            text=self.text() if callable(self.text) else self.text,
            background=C["bg_raised"],
            foreground=C["fg"],
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 9),
            padx=9,
            pady=5,
        ).pack(padx=1, pady=1)

    def _hide(self):
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class HoverTooltip(Tooltip):
    """
    Tooltip whose text depends on where the pointer is inside the widget,
    such as one tip per column of a table header.  `text_at(event)` returns
    the text for that spot, or None for no tip; the tip moves on when the
    text changes.
    """

    def __init__(self, widget, text_at):
        super().__init__(widget, "")
        self._text_at = text_at
        self._xy = (0, 0)
        widget.bind("<Motion>", self._on_motion, add="+")

    def _schedule(self, event=None):
        if event is not None:
            self._on_motion(event)

    def _on_motion(self, event):
        text = self._text_at(event)
        if text == self.text and (self._tip or self._job):
            return
        self._cancel()
        self.text = text
        if text:
            self._xy = (event.x_root + 12, event.y_root + 18)
            self._job = self.widget.after(self.DELAY, self._show)

    def _position(self):
        return self._xy
