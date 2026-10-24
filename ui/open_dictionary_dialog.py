# ui/open_dictionary_dialog.py
import tkinter as tk
from tkinter import filedialog

DICTIONARY_FILETYPES = [
    ("Steno Dictionary", "*.json *.rtf"),
    ("JSON Dictionary", "*.json"),
    ("RTF/CRE Dictionary", "*.rtf"),
]


def ask_open_dictionary(parent):
    return filedialog.askopenfilename(
        parent=parent,
        title="Open Dictionary",
        filetypes=DICTIONARY_FILETYPES,
        defaultextension=".json"
    )
