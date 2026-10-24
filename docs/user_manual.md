**StenoLab**

User Manual

_Reference for hobbyist users of Plover and on-keyboard steno engines_

# Contents

[Contents 2](#_Toc228778493)

[1\. Overview 5](#_Toc228778494)

[2\. The Main Window 6](#_Toc228778495)

[Menu bar 6](#_Toc228778496)

[Toolbar 6](#_Toc228778497)

[Search panel 6](#_Toc228778498)

[Dictionary tabs 6](#_Toc228778499)

[Tab context menu 6](#_Toc228778500)

[Status bar 7](#_Toc228778501)

[3\. Working with Dictionaries 8](#_Toc228778502)

[Opening a dictionary 8](#_Toc228778503)

[Multiple dictionaries 8](#_Toc228778504)

[Saving 8](#_Toc228778505)

[Closing a dictionary 8](#_Toc228778506)

[The unsaved-changes indicator 8](#_Toc228778507)

[4\. The Dictionary Table 9](#_Toc228778508)

[Sorting 9](#_Toc228778509)

[Selection 9](#_Toc228778510)

[Column widths 9](#_Toc228778511)

[Row colours 9](#_Toc228778512)

[Large dictionaries 10](#_Toc228778513)

[5\. Adding, Editing, and Deleting Entries 11](#_Toc228778514)

[Adding 11](#_Toc228778515)

[Editing 11](#_Toc228778516)

[Steno validation 11](#_Toc228778517)

[Deleting 11](#_Toc228778518)

[Cross-tab transfer 12](#_Toc228778519)

[Brief flag 12](#_Toc228778520)

[Comments 12](#_Toc228778521)

[6\. Searching 13](#_Toc228778522)

[The search panel 13](#_Toc228778523)

[Methods 13](#_Toc228778524)

[Combining the two axes 13](#_Toc228778525)

[Whole strokes only 13](#_Toc228778526)

[Scope 14](#_Toc228778527)

[Type-ahead filtering 14](#_Toc228778528)

[The active-search hint 14](#_Toc228778529)

[Clearing the search 14](#_Toc228778530)

[7\. Filtering 16](#_Toc228778531)

[Entry-state filters 16](#_Toc228778532)

[Content-predicate filters 16](#_Toc228778533)

[What "conflict" means 16](#_Toc228778534)

[Conflict warnings on edit 17](#_Toc228778535)

[Combining filters and search 17](#_Toc228778536)

[8\. Find & Replace 18](#_Toc228778537)

[Dialog layout 18](#_Toc228778538)

[Highlighting 18](#_Toc228778539)

[Find vs. Replace All scope 18](#_Toc228778540)

[Case sensitivity 18](#_Toc228778541)

[What gets stamped 18](#_Toc228778542)

[Renaming a steno key 19](#_Toc228778543)

[Closing 19](#_Toc228778544)

[9\. Bookmarks 20](#_Toc228778545)

[Toggling 20](#_Toc228778546)

[Visual indicator 20](#_Toc228778547)

[The Bookmarked filter 20](#_Toc228778548)

[Session-only 20](#_Toc228778549)

[10\. View Options 21](#_Toc228778550)

[Dark and light mode 21](#_Toc228778551)

[Panel collapse states 21](#_Toc228778552)

[Column widths 21](#_Toc228778553)

[Open tabs 21](#_Toc228778554)

[What does not persist 21](#_Toc228778555)

[11\. Keyboard Shortcuts 22](#_Toc228778556)

[12\. Files and Storage (Appendix) 23](#_Toc228778557)

[Dictionary files 23](#_Toc228778558)

[RTF/CRE dictionaries 23](#rtfcre-dictionaries)

[Metadata sidecar files 23](#_Toc228778559)

[Backup files 24](#_Toc228778560)

[Restoring from a backup 24](#_Toc228778561)

[Settings file 25](#_Toc228778562)

[The Tools menu 25](#_Toc228778563)

[Manual backups 26](#_Toc228778564)

[Sharing dictionaries 26](#_Toc228778565)

# 1\. Overview

StenoLab is a desktop application for managing steno dictionaries. It opens, edits, and saves dictionary files in the standard Plover JSON format or the RTF/CRE format used by CAT software, converts between the two, and tracks per-entry metadata (creation date, modification date, brief flag, comments) in sidecar files.

It is not a translation engine. It does not run live alongside steno input, and it does not replace Plover or on-keyboard translation firmware. Its purpose is curation: building, cleaning, and mining dictionaries.

Multiple dictionaries can be open at once, each in its own tab. Entries can be copied or moved between tabs, which is useful when extracting briefs from a reference dictionary into a personal one or splitting a single working dictionary into themed files.

# 2\. The Main Window

The window has five horizontal regions, top to bottom: the menu bar, the toolbar, the search panel, the dictionary tabs (each with its own filter panel and table), and the status bar.

## Menu bar

Standard menus: File, Edit, Tools, View, and Help. Every command has a keyboard shortcut where one is meaningful; see Section 11 for the full list. **Help → User Manual** opens this manual in your default web browser.

## Toolbar

Seven icon buttons are arranged across the toolbar. The five action buttons on the left replicate the most common commands. Two history buttons — ↺ Undo and ↻ Redo — sit on the right. Hover any button to see its full label and keyboard shortcut as a tooltip.

|     |     |     |
| --- | --- | --- |
| Icon | Action | Notes |
| ⊞   | Open Dictionary | Same as File → Open Dictionary. |
| +   | Add Entry | Opens the Add Entry dialog on the active tab. |
| ✎   | Edit Entry | Opens the Edit dialog for the selected row. |
| ⌕   | Find & Replace | Opens the Find & Replace dialog. |
| ★   | Toggle Bookmark | Bookmarks or un-bookmarks all selected rows. |
| ↺   | Undo | Undo the last change: an add, edit, delete, copy or move into the tab, Replace, or Replace All. Sits on the right side of the toolbar; disabled when there is nothing to undo. |
| ↻   | Redo | Replay the most recently undone operation. Disabled when there is nothing to redo. |

## Search panel

Two-axis search across steno and translation. Collapsible. Covered in detail in Section 6.

## Dictionary tabs

One tab per open dictionary. The tab title shows the dictionary name. A dot before the name (for example "● main") indicates unsaved changes; it disappears once the file is saved.

Each tab has its own filter panel just below the tab strip. Filters and search both apply only to the active tab.

## Tab context menu

Right-click a tab heading to access the most common per-dictionary operations without having to switch focus to the tab first:

|     |     |
| --- | --- |
| Command | What it does |
| Save | Save the dictionary. Greyed out when there are no unsaved changes. |
| Save As... | Save a copy to a new path, and continue editing under the new name. The original file is left untouched. Choosing a .json or .rtf name saves the copy in that format. |
| Open Containing Folder | Reveal the dictionary file in the system file browser. |
| Restore Backup... | Open the restore dialog for this dictionary (Section 12). |
| Close | Close this tab. Prompts about unsaved changes if any. |

The right-clicked tab is selected first, so subsequent operations always act on the tab you actually clicked rather than whichever happened to be active before.

## Status bar

Bottom of the window. Shows the active dictionary name, the total number of entries in that dictionary, and the count of dictionaries currently open.

# 3\. Working with Dictionaries

## Opening a dictionary

File → Open Dictionary, or Ctrl+O, or the ⊞ toolbar button. The file picker accepts JSON and RTF/CRE (.rtf) dictionaries. A JSON dictionary is a flat object mapping steno keys to translation strings — the same format Plover uses.

Example: {"KAT": "cat", "TKOG": "dog"}

Duplicate steno keys in the source file are preserved as separate entries rather than collapsed (a standard JSON parser would silently keep only the last value for a duplicate key). This matters because duplicates surface in the Conflicts filter, where they can be reviewed and resolved.

The file picker also accepts RTF/CRE dictionaries (.rtf), the interchange format exported by Eclipse, Case CATalyst, Digital CAT, Plover and other CAT software. See [RTF/CRE dictionaries](#rtfcre-dictionaries) in Section 12 for how their formatting is shown.

## Multiple dictionaries

Each opened dictionary becomes a new tab. There is no fixed limit on how many can be open at once. Tabs persist across sessions: whichever dictionaries are open when the application closes will reopen on the next launch.

## Saving

File → Save Dictionary, or Ctrl+S. The active tab's dictionary is written back to its original file. Before each save StenoLab writes a timestamped backup of the previous file contents to its backup folder, so a previous version can always be recovered; see Section 12 for details on backups and restoration.

Saving writes only the steno-to-translation mapping. Per-entry metadata (dates, brief flag, comments) lives in a separate file and is saved automatically whenever an entry is edited; see Section 12.

## Closing a dictionary

File → Close Dictionary closes the active tab. If the tab has unsaved changes (the dot indicator is showing), StenoLab asks whether to save them, discard them, or cancel and keep the tab open.

Closing the application — File → Exit, or the window close button — follows the same logic but considers all open tabs at once. If several have unsaved changes a single dialog lists them with checkboxes, defaulting to all ticked, so you can save the ones you want and discard the rest in one step. Tabs with no unsaved changes never appear in the dialog; their files are already in sync with disk.

Metadata edits (Brief flag, Comments, etc.) are saved together with the dictionary, so saving keeps both and discarding drops both. This keeps a dictionary and its metadata in step: renaming a steno and then discarding can't lose that entry's comments.

## The unsaved-changes indicator

When a tab has changes that have not yet been written to its dictionary file, a dot (●) appears before the tab name. It covers every change to the tab: entries added, edited, deleted, copied or moved in, Find & Replace, and the metadata that goes with them. Undoing back to the last saved state clears the dot again.

# 4\. The Dictionary Table

Each tab shows its dictionary as a table. The columns are:

|     |     |
| --- | --- |
| Column | Meaning |
| Steno | The stroke or stroke sequence. Multi-stroke entries use "/" as a separator (for example AL/PHOERPB). |
| Translation | The text the stroke produces. |
| S   | Stroke count: number of strokes in the entry. Useful for finding multi-stroke entries that could be briefed. |
| W   | Word count: number of whitespace-separated words in the translation. A long-translation entry combined with a short stroke is likely a brief. |
| B   | Brief flag: shows ✓ if the entry has been marked as a brief in its metadata. The flag is set in the Add/Edit dialog. |
| F   | Frequency score for the entry's translation, from an imported frequency list (Section 12). Optional — shown only when *Show frequency column* is ticked in the filter panel. |
| Added | Date the entry was first recorded by StenoLab (not necessarily the date the dictionary file was created). |
| Modified | Date the entry was last edited. |
| Comments | Free-text notes about the entry. Long comments are truncated in the table view; the full text is visible in the Edit dialog. |

## Sorting

Click any column header to sort by it. Clicking the same header again reverses the sort direction. The currently sorted column shows an arrow: ▲ for ascending, ▼ for descending.

Sorting is per-tab and is not persisted across sessions; each new launch starts sorted by Translation, ascending.

## Selection

Click a row to select it. Click-and-drag across rows (or Shift-click) selects a contiguous range. Right-click any row to open the context menu (covered in Section 5).

## Column widths

Drag the divider between two column headers to resize. New widths save automatically and apply to every dictionary tab on next launch.

## Row colours

The table uses subtle background tints to flag entry state at a glance:

*   Bookmarked entries are tinted green.
*   Conflicting entries (where two or more rows share the same steno) are tinted red.
*   An entry that is both bookmarked and in conflict is tinted amber.
*   During a Find & Replace search, matching rows are highlighted in yellow.

Tints adapt to dark and light mode automatically.

## Large dictionaries

The whole dictionary is shown at once. There is no row cap and no pagination: however many entries match the current search and filters — a handful or all 100,000+ — every one is listed in a single, continuously scrollable table.

This works because the table is *virtualised*: only the rows currently on screen are actually drawn, and more are rendered as you scroll. Opening a six-figure dictionary is near-instant and scrolling stays smooth, because the work never depends on the total number of rows.

In practice you'll still reach a specific entry fastest by typing into the search bar (Section 6) rather than scrolling — but nothing stops you from scrolling the full list when you want to. The entry-count chip in the filter panel header always shows the current match count (for example, "1,234 of 101,455").

# 5\. Adding, Editing, and Deleting Entries

## Adding

Edit → Add Entry, or Ctrl+N, or the + toolbar button. A modal dialog opens with empty Steno and Translation fields, an unchecked Brief checkbox, and an empty Comments box. Save commits the entry to the active tab; Cancel discards it. The Steno field is focused on open, so you can start typing immediately.

## Editing

Several routes open the Edit dialog for the selected row:

*   Double-click the row.
*   Press Enter or Ctrl+E with the row selected.
*   Edit → Edit Entry.
*   Right-click → Edit Entry.
*   The ✎ toolbar button.

The dialog is identical to Add Entry but pre-filled with the existing values. Saving writes the change to the active tab and stamps today's date into the entry's Modified field.

## Steno validation

When you click Save in the Add or Edit dialog, the Steno field is checked against a basic correctness rule: characters must come from the steno alphabet (S T K P W H R A O \* E U F R P B L G T S D Z, digits, and the modifier characters # and -), and within each stroke the keys must appear left-to-right in canonical order. Multi-stroke entries split on "/" and each stroke is checked individually.

The check only runs when the steno is new or has changed, so editing just the translation, brief flag or comments never triggers it. Digital CAT's style of writing a hyphen between the vowels (HAO-EUF) is accepted.

If validation fails, the Steno field gains a red border and a message below it explains the problem ("Invalid character 'x'", "Keys are out of order", and so on). The check only knows Plover's English layout, so it's a warning rather than a rule: press Save again with the same steno to keep it anyway. This is how you edit Palantype and other systems' dictionaries. The message clears as soon as you start editing the field again.

Validation runs only at Save time, not as you type. Briefs are entered key-by-key, and validating mid-stroke would flicker errors while you're still typing.

The Steno field auto-capitalises as you type. Steno is conventionally written in upper case, and forcing it removes the need to hold Shift or toggle Caps Lock for every entry.

## Deleting

Select one or more rows, then either press Delete, choose Edit → Delete Selected, or right-click → Delete. A confirmation prompt appears; for a single row it shows the steno key, for multiple rows it shows the count.

Deleted entries are removed from the in-memory dictionary immediately. Their metadata is discarded too, unless another row still uses the same steno. The dictionary file and its metadata on disk are unchanged until the next save.

## Cross-tab transfer

Right-click a selection to access "Copy to →" and "Move to →" submenus listing every other open tab. Copying preserves the entries on the source tab; moving deletes them from the source after copying. Metadata travels with the entries in both cases.

This is the main mechanism for mining other dictionaries: open the reference dictionary in one tab, your personal dictionary in another, select interesting entries in the reference, and copy them across.

## Brief flag

The Brief checkbox in the Add/Edit dialog is purely advisory — a hand-set marker indicating you consider this entry a brief rather than a phonetic outline. The flag drives the B column in the table and the "Is brief" filter (Section 7); nothing in the application infers it automatically from stroke length.

## Comments

The Comments field is a multi-line free-text box. Use it for whatever is useful: a memory hook for an awkward outline, the source dictionary an entry was extracted from, a note that an entry needs revisiting. The Has Comments filter (Section 7) lists every entry whose Comments field is non-empty, which is a quick way to find unfinished work.

# 6\. Searching

StenoLab searches along two independent axes — Steno and Text — that can be combined freely. This is the headline feature for dictionary mining: it lets you ask questions like "show me every entry whose steno ends in -FT and whose translation ends in 'st'", which a single-axis search cannot express.

## The search panel

Click the "▶ Search" header to expand the panel. The panel persists in whichever state — collapsed or expanded — it was last left in, across application restarts.

When expanded, the panel has three rows:

*   Text: a method dropdown, an entry field, and a "Match case" checkbox.
*   Steno: a method dropdown, an entry field, and a "Whole strokes only" checkbox.
*   Scope: a dropdown selector, plus a Clear button that empties both query fields.

The Text axis sits above Steno because most searches start by thinking of an English word and recalling the outline second.

## Methods

Each axis offers three methods that determine how the query string is matched:

|     |     |
| --- | --- |
| Method | Behaviour |
| Contains | Match if the query string appears anywhere in the field. |
| Begins With | Match if the field starts with the query string. |
| Ends With | Match if the field ends with the query string. |

Steno matching is case-insensitive, and the Steno query field auto-capitalises as you type so you don't have to hold Shift or toggle Caps Lock. Text matching is case-insensitive by default; tick "Match case" on the Text row to require an exact case match. Useful when auditing capitalisation in a proper-noun dictionary, or distinguishing entries like "US" (the country) from "us" (the pronoun).

## Combining the two axes

The two axes AND together. An entry is shown only if it matches the Steno axis (or the Steno query is empty) AND matches the Text axis (or the Text query is empty).

Empty axes impose no constraint. With both fields empty, the panel is effectively inactive.

Worked example: looking for short briefs ending in -st where the steno ends in -FT. Set Steno method to _Ends With_, Steno query to FT. Set Text method to _Ends With_, Text query to st. The result includes TEFT → "test" but excludes PR-FT → "proof".

## Whole strokes only

This checkbox changes the steno match algorithm. By default (unchecked), the steno value is treated as a single string and the chosen method matches against that string directly. With the checkbox ticked, the steno value is split into individual strokes on the "/" separator and the query is matched stroke-by-stroke.

Example: searching for steno ending in AL. Without whole-strokes mode, both TPORPL/AL and TPAL match (the latter because its single stroke ends in the substring "AL"). With whole-strokes mode on, only TPORPL/AL matches — its final stroke is exactly AL, whereas TPAL contains "AL" only as part of a larger stroke.

Whole-strokes mode applies to all three methods (Contains, Begins With, Ends With) and only affects the Steno axis. The Text axis is unaffected.

## Scope

The Scope dropdown determines which dictionaries are searched. "Current Dictionary" — the default — searches only the active tab. "All Dictionaries" searches every open tab simultaneously, with each tab's filter panel reflecting the matches found in that tab. This is useful when looking for an entry without remembering which dictionary it lives in, or when comparing how the same word is outlined across several reference dictionaries.

## Type-ahead filtering

StenoLab filters as you type, with no Search button to press. Each keystroke updates the visible rows immediately.

More unusually: keystrokes received while the application has focus but no input field is selected are routed automatically to the Text search field, expanding the search panel first if it is currently collapsed. So the workflow "open the program, type the word you're looking for, see results" works without any prior clicks. The character is treated as Begins-With text, the most common search reflex.

Type-ahead routing skips when an input field is already focused (so typing in the Find & Replace dialog or an Edit dialog works normally), when modifier keys are held (Ctrl, Alt), and on navigation keys (arrows, Page Up, Home), function keys (F1–F12), and editing keys (Backspace, Delete, Enter, Escape).

Steno-axis searches are not reachable through type-ahead. To search by stroke, click into the Steno field first; the program assumes that someone already thinking in steno will know to do this.

## The active-search hint

When the search panel is collapsed and a search is active, the panel header shows a brief summary of what is currently being filtered, for example:

▶ Search active: text: "the"

If the active search yields zero matches, the suffix "— no matches" is appended:

▶ Search active: steno: "FT", text: "xyz" — no matches

This indicator means a collapsed panel is never silently filtering — there is always a visible cue that some constraint is in force.

## Clearing the search

The Clear button on the bottom row of the search panel empties both query fields in one click, leaving the method dropdowns and Whole-strokes checkbox untouched.

# 7\. Filtering

The filter panel sits just below the tab strip on every dictionary tab. It is collapsed by default; click the "▶ Filters" header to expand it.

Filters are independent of search and AND together with the search axes. An entry is shown only if it matches both the search criteria and every active filter checkbox.

All filters are checkboxes. With none ticked, no filtering is applied and the full dictionary is shown (subject to any active search). Multiple filters combine with AND — for example, ticking both "Is brief" and "Has comments" shows only entries that are flagged as briefs and have non-empty comments.

## Entry-state filters

The first row of filters reflects metadata or per-entry state.

|     |     |
| --- | --- |
| Filter | Matches entries where... |
| Has comments | the Comments field contains any non-whitespace text. |
| Is brief | the Brief flag has been set in the Edit dialog. |
| Bookmarked | the entry is currently bookmarked in this session (see Section 9). |
| Conflicts | the steno key is shared with at least one other entry in the same dictionary. |

## Content-predicate filters

The second row of filters tests the content of the Translation field.

|     |     |
| --- | --- |
| Filter | Matches entries where the translation... |
| Capitalised | begins with an uppercase letter. Useful for auditing proper-noun dictionaries or checking that capitalisation is consistent. |
| Numbers (0–9) | contains at least one digit. Picks up things like "$1.50" and "23-skidoo". |
| Numbers (written) | contains a word that names a number — "one", "twenty", "thousand", and so on. Helpful for sanity-checking number spelling entries. |
| Punctuation | contains any non-alphanumeric punctuation character. Punctuation entries are a common source of small dictionary bugs that go unnoticed for a long time. |

## Frequency filters

A third row of filters uses the frequency score imported via **Tools → Import Frequency List** (Section 12). Entries that have never been matched to a frequency list have a score of 0.

|     |     |
| --- | --- |
| Filter | Matches entries where the translation... |
| Has frequency | has a non-zero frequency score. |
| Top N by frequency | is among the N highest-scoring entries in the dictionary. Type N in the adjacent box (default 500). Useful for concentrating on the most common words first — the ones where a good brief pays off most. |

The same row of the panel also carries two **view toggles** rather than filters — *Focus mode* and *Show frequency column* — both described in Section 10.

## What "conflict" means

"Conflict" here has a specific meaning: a steno key that appears more than once in the same dictionary. It does not flag entries whose translation is duplicated under different stenos, and it does not look across dictionaries.

Conflict detection runs automatically when a dictionary is opened, when entries are added, edited, or deleted, and after Replace All. Conflicting rows show the red row tint described in Section 4.

Within a Plover JSON file, duplicate keys are unusual — Plover itself deduplicates them on read, keeping the last value. StenoLab preserves the duplicates so they can be inspected and resolved. If a dictionary is opened and the Conflicts filter shows entries, those are silent collisions in the source file that Plover has been ignoring all along.

## Conflict warnings on edit

When adding or editing an entry creates a new conflict — that is, the steno key being saved now collides with an existing entry — a non-blocking warning banner appears at the bottom of the tab naming the conflicting steno, and the Conflicts filter is automatically turned on so the conflicting rows are immediately visible.

The banner is non-blocking on purpose. Bulk operations like copying many entries between dictionaries can legitimately create dozens of conflicts in a row, and a modal dialog per conflict would be intolerable. The auto-applied filter does the work of pointing you at the conflicts so you can resolve them when convenient. Click the × on the banner to dismiss it.

## Combining filters and search

Search and filters are independent and stack with AND. The visible rows are the intersection of: (a) entries matching the Steno query or no Steno constraint; (b) entries matching the Text query or no Text constraint; and (c) entries matching every ticked filter. The entry count in the filter panel header reflects the intersection.

# 8\. Find & Replace

Find & Replace is a separate dialog reached via Ctrl+F, Edit → Find & Replace, or the ⌕ toolbar button. It is non-modal — the main window stays usable behind it — and it always operates on the currently active tab, so switching tabs while the dialog is open naturally retargets the search.

Where the Search panel filters the visible rows down, Find & Replace navigates and modifies. The two are complementary: search narrows, Find & Replace acts.

## Dialog layout

*   Find: the text to search for.
*   Replace: the text to substitute in.
*   In: which field to search — Translation, Steno, or Both.
*   Match case: when ticked, capitalisation must match exactly.
*   Prev / Next: navigate between matches.
*   Replace: replace in the currently selected match, then advance.
*   Replace All: replace every match across the entire dictionary in one operation. A confirmation shows how many entries will change. Replace All is a single undoable change, so Ctrl+Z reverses all of it.
*   Close: dismiss the dialog and clear find highlighting.

## Highlighting

As the Find query is typed, all matching rows in the active tab are highlighted in yellow. The status line below the input fields shows the match count ("15 matches", or "No matches"), and once you navigate, it updates to position ("3 of 15 matches").

## Find vs. Replace All scope

There is one important asymmetry to be aware of:

*   Find — and the Prev / Next / Replace buttons — operates only on the currently visible (filtered) rows. If a search or filter is hiding rows in the tab, Find won't see them.
*   Replace All operates on every entry in the dictionary, regardless of search or filter state.

This is intentional: Find should match what’s on screen, and Replace All should be a sweeping operation that won’t leave instances behind in hidden rows. Be deliberate when using Replace All — it really does mean every entry. If the result isn't what you wanted, Ctrl+Z undoes the whole replacement in one step.

## Case sensitivity

Match case is off by default, so a search for "the" matches "The" and "THE". Tick the checkbox to require an exact case match. The match count updates immediately when the checkbox state changes.

## What gets stamped

Replace and Replace All stamp today's date into the Modified field of every entry they change. Adding metadata in this way ensures audit trails remain accurate even when changes come through Find & Replace rather than the Edit dialog.

## Renaming a steno key

When the In field is set to Steno or Both, Find & Replace can rewrite steno keys. This is more than a string change: bookmark state, metadata, and conflict membership are all migrated from the old key to the new key. The dictionary file is updated on the next save.

## Closing

Pressing Escape, clicking Close, or closing the dialog window clears the find highlighting from the table. The dialog otherwise stays open as long as you want, ready for the next find.

# 9\. Bookmarks

Bookmarks are visual flags that pin individual entries for attention during a working session. They have no effect on the dictionary file and do not influence search or sort order; they exist purely to make an entry easy to find again and easy to filter for.

## Toggling

Three routes toggle the bookmark state of the selected rows:

*   Edit → Toggle Bookmark, or Ctrl+B.
*   Right-click → Toggle Bookmark.
*   The ★ toolbar button.

All three operate on the current selection, and all three behave consistently: if every selected row is currently bookmarked, the action removes bookmarks from all of them; otherwise, every selected row gets bookmarked. This means selecting a mix of bookmarked and unbookmarked rows and triggering the action makes them uniformly bookmarked, which is usually what you want.

## Visual indicator

Bookmarked rows are tinted green in the dictionary table. The tint adapts to dark and light mode automatically.

An entry that is both bookmarked and in conflict (a duplicate steno key) is tinted amber, signalling that two states overlap.

## The Bookmarked filter

Tick the Bookmarked checkbox in the filter panel to show only bookmarked entries. This is the most common use of bookmarks: flag interesting rows while scrolling, then filter down to review them.

## Session-only

Bookmarks are not persisted between sessions. They are a working-memory aid, not a long-term tag. Closing the application or closing the dictionary tab clears them. For permanent tagging, use the Comments field on individual entries.

# 10\. View Options

## Dark and light mode

View → Dark Mode is a checkbox toggle. The application defaults to dark mode on first launch. The choice persists across sessions.

Dark mode also requests a dark title bar from Windows, which most modern Windows 10 and 11 installations honour automatically. On platforms where the title bar can't be themed (older Windows builds, some Linux window managers), the title bar will remain in the system default appearance even when dark mode is active inside the application.

Switching modes is instant — there is no need to restart. Open dialogs, including Find & Replace, repaint to match the new mode.

## Focus mode

The *Focus mode* checkbox in the filter panel switches the table to a stripped-down set of columns — Steno, Translation, and the Brief flag only (plus the F column if it is shown). It is meant for distraction-free daily editing, where the metadata columns (dates, comments, counts) are just noise. Focus mode is per-session and always starts off.

## Show frequency column

The *Show frequency column* checkbox adds the optional **F** column to the table (Section 4), showing each entry's imported frequency score. The choice is shared across all tabs and persists across sessions.

## Panel collapse states

Both the Search panel and each tab's Filter panel can be collapsed by clicking their header row.

*   The Search panel's collapse state is application-wide and persists across sessions.
*   The Filter panel's collapse state is per-tab and resets each time a tab is opened.

When a panel is collapsed but is currently filtering, its header shows a hint summarising what is active (see Section 6 for the Search panel; the Filter panel shows an entry count).

## Column widths

Column widths persist across sessions and are shared across all dictionary tabs. Adjust them on whichever tab is convenient; the new widths apply everywhere on the next launch.

## Open tabs

The set of open dictionary tabs is remembered between sessions. Whichever dictionaries are open when the application closes will reopen automatically on the next launch, in the same order, with the tab that was active last time re-selected. The *Show frequency column* choice is also remembered.

## What does not persist

These elements deliberately reset between sessions:

*   The current sort column and direction (always starts as Translation, ascending).
*   Filter checkbox states (always start unticked).
*   Focus mode (always starts off).
*   Search field contents (always start empty).
*   Bookmarks (see Section 9).

# 11\. Keyboard Shortcuts

All keyboard shortcuts available throughout the application:

|     |     |     |
| --- | --- | --- |
| Shortcut | Action | Where it works |
| Ctrl+O | Open Dictionary | Anywhere |
| Ctrl+S | Save active dictionary | Anywhere |
| Ctrl+N | Add Entry | Anywhere |
| Ctrl+E | Edit selected entry | Anywhere |
| Ctrl+B | Toggle bookmark on selection | Anywhere |
| Ctrl+F | Open Find & Replace | Anywhere |
| Delete | Delete selected entries | In the dictionary table |
| Enter | Edit selected entry | In the dictionary table |
| Double-click | Edit clicked entry | In the dictionary table |
| Right-click | Open context menu | In the dictionary table |
| Enter | Find Next | In the Find & Replace dialog |
| Shift+Enter | Find Previous | In the Find & Replace dialog |
| Escape | Close Find & Replace | In the Find & Replace dialog |
| Ctrl+Z | Undo | Anywhere |
| Ctrl+Y / Ctrl+Shift+Z | Redo | Anywhere |
| Any letter / digit | Begin Text search (type-ahead) | When no input field is focused |

# 12\. Files and Storage (Appendix)

StenoLab stores all of its data on the local machine. Nothing is uploaded or synchronised. Three categories of file are involved:

## Dictionary files

These are the JSON or RTF/CRE dictionary files you open with File → Open Dictionary. StenoLab does not move or copy them; it reads from and writes back to whatever path you opened, in the same format. A JSON dictionary is a flat object mapping steno keys to translation strings:

{  
"KAT": "cat",  
"TKOG": "dog",  
"TPHEUS/SOUR": "Missouri"  
}

This is the same format Plover uses, so dictionaries can be opened in either application. Files are written with UTF-8 encoding and two-space indentation.

Duplicate steno keys in the file are preserved on load (Section 7) and written back as separate entries on save, in both formats. Plover keeps only the last value for a duplicated key, so resolve conflicts if you want a predictable result in Plover.

## RTF/CRE dictionaries

Dictionaries with an .rtf extension are read and written in RTF/CRE format. So that they look and search the same as JSON dictionaries, CRE formatting is shown in Plover syntax and converted back when the file is saved:

| RTF/CRE | Shown as |
| --- | --- |
| \\cxds (delete space) | {^}, or a compact form such as {^ing} |
| \\cxfc / \\cxfl (force capital / lower case) | {-\|} / {>} |
| {\\cxp. } and other punctuation | {.} {,} {?} {!} {:} {;} |
| {\\cxfing a} (fingerspelling) | {&a} |
| \\par, \\tab | {^\\n^}, {^\\t^} |
| {\\\*\\cxplovermeta …}, {\\\*\\cxplovermacro …} | the Plover meta or =macro |

Anything else is preserved unchanged. Unrecognised formatting such as {\\i text} stays visible in the translation as raw RTF. Hidden per-entry data such as Digital CAT entry dates and comments is kept out of sight and written back on save. When you save over an existing .rtf, its header (CAT system name, stylesheet) is reused. Save As to a new .rtf writes a standard header. Equivalent Plover forms may be normalised: for example {^}ing is shown as {^ing}.

To convert a dictionary file without opening it, use Tools → Convert Dictionary → JSON to RTF... or RTF to JSON.... Choose the source file, then where to save the converted copy. The source is left untouched, its metadata (dates, brief flags, comments) is copied to the new file, and you are offered the chance to open the result. If the destination already exists it is backed up before being replaced. Save As can also convert an open dictionary: choose a .json name to save an RTF dictionary as Plover JSON, or the reverse.

## Metadata sidecar files

Per-entry metadata (creation date, modification date, brief flag, comments, frequency) is stored alongside the dictionary in a separate file. Sidecar files live in StenoLab's data folder — a **StenoLab Data** folder inside your Documents folder (OneDrive-synced if you use OneDrive) — not next to the dictionary, so the dictionary file itself contains only steno and translations.

Location:

Documents\\StenoLab Data\\metadata\\

Each metadata file is named after its dictionary. For example, a dictionary at C:\\dicts\\main.json has a metadata file at Documents\\StenoLab Data\\metadata\\main.json. The format is a JSON object keyed by steno:

{  
"KAT": {  
"date\_added": "2024-08-01",  
"modified": "2024-09-12",  
"brief": false,  
"comments": "extracted from Lapwing",  
"bookmarked": false,  
"frequency": 0  
}  
}

To keep the file small for large dictionaries, it is written without indentation, and fields that hold their default value (brief false, comments empty, bookmarked false, frequency 0) are left out. StenoLab reads a missing field as its default. The example above shows every field for clarity; on disk this entry is stored as `"KAT":{"date_added":"2024-08-01","modified":"2024-09-12","comments":"extracted from Lapwing"}`.

The frequency field holds a usage-frequency score for the entry's translation. It is populated by **Tools → Import Frequency List** and is read by the *Has frequency* and *Top N by frequency* filters (Section 7) and the optional **F** column (Section 4). A score of 0 means no frequency data has been matched to that entry. The bookmarked field is unused in practice (bookmarks are session-only, see Section 9) but the field is retained in the schema for future flexibility.

If a metadata file is missing or unreadable, StenoLab builds a fresh one in memory using today's date for both Added and Modified fields. There is no harm in deleting metadata files; it just means history information for that dictionary is lost.

## Backup files

StenoLab automatically backs up dictionaries so a previous version is always recoverable. Backups are stored as timestamped copies of the dictionary file together with its metadata sidecar. RTF dictionaries are backed up with an .rtf extension.

Location:

Documents\\StenoLab Data\\backups\\

Filenames combine the dictionary name and a millisecond-precision timestamp, for example:

main\_2026-04-30\_14-32-08-241.json  
main\_2026-04-30\_14-32-08-241.metadata.json

Backups are created at two specific moments:

*   When a dictionary is opened in a session, capturing the file as it stood at the start of the working session. This snapshot is taken once per dictionary per session — reopening the same file later in the same session does not produce another open-time backup.
*   Before every save, capturing the on-disk file as it was just before being overwritten. So even within a session you can roll back to the version immediately preceding any save.

Pruning runs after each backup and keeps, per dictionary, the three most recent open-time snapshots and the two most recent pre-save snapshots. The two kinds are pruned separately, so heavy saving never pushes out the open-time snapshots. Older backups are removed automatically. If you need to keep a particular backup beyond that limit, copy it out of the backup folder; StenoLab never touches files it doesn't recognise.

Backup creation runs silently in the background. The exception is a failure: if StenoLab cannot write a backup before saving (most commonly a full disk or permission problem), it warns you and asks whether to save anyway. Saving without a backup is allowed but deliberately makes you confirm, since the safety net would be absent for that save only.

## Restoring from a backup

Tools → Restore Backup opens a dialog listing every available backup for the active tab's dictionary, newest first. Each row shows when the backup was made, how many entries it contained, and whether a matching metadata sidecar was captured. Select one and click Restore Selected (or double-click) to replace the current file.

Restoration steps StenoLab performs in order:

*   Warns if the active tab has unsaved changes that would be lost.
*   Asks for confirmation, showing the timestamp of the chosen backup.
*   Backs up the current state immediately before replacing it. This is an important property: a restore is itself reversible by restoring the snapshot it took on the way in.
*   Replaces the dictionary file (and the metadata sidecar, if the backup includes one) with the chosen backup's contents.
*   Reloads the active tab from the restored file so the table reflects the new state immediately.

If the dictionary has no backups yet, the dialog opens but reports the empty state rather than disabling the menu item.

## Settings file

User preferences and session state live in a single JSON file:

Documents\\StenoLab Data\\settings.json

Keys currently stored:

|     |     |
| --- | --- |
| Key | Purpose |
| theme | "dark" or "light" — see Section 10. |
| search\_collapsed | Whether the Search panel was collapsed at the time of the last session change. |
| column\_widths | Map of column name to pixel width. Shared across all tabs. |
| open\_tabs | List of dictionary file paths that were open when the application last closed. Used to reopen them on next launch. |
| active\_tab | Path of the dictionary that was the active tab when the application last closed, so it is re-selected on next launch. |
| show\_freq\_column | Whether the optional **F** (frequency) column is shown. Shared across all tabs. |
| ignored\_frequency\_words | List of words to skip when reviewing missing frequency matches (see Tools below). |

## The Tools menu

The Tools menu groups the restore feature, the data-folder shortcuts, dictionary conversion, and the frequency tools:

|     |     |
| --- | --- |
| Command | What it does |
| Restore Backup... | Opens the restore dialog described above. If no dictionary tab is active, the command shows a brief message asking you to open one first. |
| Open Backup Folder | Opens the backup directory in the system file browser. Useful for inspecting backups manually, copying one out before it gets pruned, or clearing space. |
| Open Metadata Folder | Opens the metadata directory in the system file browser. Useful for inspecting a sidecar manually, removing the metadata for a dictionary you no longer use, or transferring metadata between machines. |
| Convert Dictionary → JSON to RTF... / RTF to JSON... | Converts a dictionary file on disk to the other format without opening it. Choose the source, then where to save the copy. The source is left untouched and its metadata is copied to the new file. See [RTF/CRE dictionaries](#rtfcre-dictionaries). |
| Import Frequency List... | Loads a word-frequency list (space/tab-delimited or CSV — rows of a word with a usage count) and writes a frequency score into the metadata of each entry whose translation is a single plain word that matches. This populates the **F** column and the *Has frequency* / *Top N by frequency* filters. |
| Review Missing Frequency Words... | Loads a frequency list and lists the most common words from it that have **no** entry in the active dictionary — a worklist of common words still worth an outline. Words you decide to skip are remembered via Manage Ignored Frequency Words. |
| Manage Ignored Frequency Words... | Edits the list of words excluded from the missing-frequency review. |

## Manual backups

The automatic backup system handles routine recovery, but for long-term archiving — disaster recovery, transferring to a new machine, or keeping snapshots beyond the rolling backup window — back up everything by copying:

*   Each dictionary file (wherever you keep them).
*   The Documents\\StenoLab Data folder in its entirety.

Restoring is the reverse: place the dictionary files where they were before, restore the StenoLab Data folder, and reopen the application. All metadata, settings, automatic backups, and previously open tabs will be present.

## Sharing dictionaries

To share a dictionary with another user, just send the dictionary file. Plover users can open either format; for CAT software such as Eclipse or Case CATalyst, send an RTF (use Tools → Convert Dictionary → JSON to RTF if needed). Metadata is local to your machine and won't travel with it; the recipient will see the entries with empty Added / Modified dates and an unset Brief flag, building up their own metadata as they use the dictionary.

If you want the metadata to come with the dictionary, send the matching file from Documents\\StenoLab Data\\metadata\\ as well, and the recipient can drop it into the same location on their machine.