# StenoLab

A desktop editor for steno dictionaries. StenoLab opens Plover JSON and RTF/CRE dictionaries, lets you search, filter, edit and annotate them, and keeps large dictionaries (300,000+ entries) quick to work with. It is for curating dictionaries — building, cleaning up and comparing them — not for writing steno.

A companion **[iPad viewer](https://ajgdsn.github.io/StenoLab/)** lets you search and compare dictionaries, with your comments, away from the computer.

## Features

- **Plover JSON and RTF/CRE.** Open either format and save in the same one. RTF formatting is shown in Plover syntax (`{^ing}`, `{.}`, `{-|}`) and converted back on save; anything else is kept unchanged. Tools → Convert Dictionary converts between the two.
- **Fast with big dictionaries.** The table shows every entry at once, with no paging. On a 370,000-entry dictionary, searching responds within about 50 ms and an edit within about a second.
- **Search and filter.** Search translations and steno with Begins With, Contains or Ends With, optionally as whole strokes. Filter by comments, brief flag, bookmark, conflicts, capitals, numbers, punctuation and word frequency.
- **Comments and other metadata.** Each entry can have a comment, a brief flag and a frequency score, kept in a separate file so the dictionary itself stays clean. Metadata saves together with the dictionary.
- **Several dictionaries side by side.** Each opens in its own tab. Select a word and switch tabs to see how another dictionary writes it. Copy or move entries between tabs.
- **Conflicts.** Duplicate steno keys are kept rather than silently dropped, and highlighted so they can be resolved.
- **Undo any edit.** Adding, editing, deleting, copying or moving entries and Find & Replace across the whole dictionary can all be undone.
- **Safe saving.** Files are written atomically, and a backup is taken when a dictionary is opened and before every save. Tools → Restore Backup rolls back.
- **Steno-aware editing.** New or changed outlines are checked against the Plover English layout. Other systems (Palantype, CAT software conventions) are allowed after a warning.
- **Frequency tools.** Import a word-frequency list to score entries and find common words that have no outline yet.
- **Light and dark themes.**

## Getting started

StenoLab is a Python application built with Tkinter and [tksheet](https://github.com/ragardner/tksheet). It is developed and used on Windows; other platforms are untested.

1. Install [Python](https://www.python.org/downloads/) 3.10 or newer, including Tkinter (the standard Windows installer includes it).
2. Download this repository (Code → Download ZIP, or `git clone https://github.com/AJGDsn/StenoLab.git`).
3. Install the one dependency:

   ```
   py -m pip install -r requirements.txt
   ```

4. Start StenoLab by double-clicking `run.pyw`, or from a terminal:

   ```
   py main.py
   ```

Then choose File → Open Dictionary. The full user manual is under Help → User Manual, and [online](https://ajgdsn.github.io/StenoLab/manual.html).

### Where StenoLab keeps its data

Dictionaries are read and saved where they are; StenoLab never moves them. Its own files — metadata (comments, brief flags, frequencies, dates), backups and settings — live in a **StenoLab Data** folder inside your Documents folder. Tools → Open Metadata Folder and Tools → Open Backup Folder open them.

## iPad viewer

The viewer at **https://ajgdsn.github.io/StenoLab/** is a read-only companion that runs in Safari on an iPad (or any browser). Add it to the Home Screen and it works offline.

- It opens dictionaries from the Files app, so OneDrive, Dropbox and iCloud Drive all work. Files are read on the device; nothing is uploaded.
- It reads Plover JSON, RTF/CRE, and review files made with StenoLab's **File → Export for iPad**, which carry each entry's comment. The current search and filters decide what is exported, so you can take just the entries you are reviewing.
- Search, sort, read comments, and use **Compare** to look one word up in every open dictionary.

The viewer is plain HTML, CSS and JavaScript in [`web/`](web/), published by GitHub Actions to GitHub Pages.

## For developers

```
py -m pip install pytest
py -m pytest
```

The tests cover dictionary reading and writing, metadata, undo and unsaved-change tracking, backups and the table's caches. Two tests need [Node.js](https://nodejs.org/) and are skipped without it: they check that the viewer's JavaScript RTF reader reads files exactly as StenoLab does. To run that comparison on real dictionaries:

```
py tests/web/check_rtf_parity.py path\to\dictionaries
```

| Folder | Contents |
| --- | --- |
| `main.py`, `run.pyw` | Application window, menus and launcher |
| `ui/` | The dictionary tab and table, dialogs, toolbar, menu bar, theme |
| `logic/` | File formats, metadata, backups, undo, frequency import, review export |
| `web/` | The iPad viewer |
| `docs/` | The user manual (`user_manual.md`, built into `user_manual.html` by `build_manual.py`) |
| `tests/` | pytest suite |

Tools that build dictionaries can deliver metadata with them as `<dictionary>.stenolab-meta.json` beside the dictionary file; StenoLab merges it in when the dictionary is opened. See "Metadata delivered with a dictionary" in the user manual.

## Licence

StenoLab is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. It is distributed in the hope that it will be useful, but without any warranty. See [LICENSE](LICENSE) for the full text.

Copyright © 2026 AJGDsn.
