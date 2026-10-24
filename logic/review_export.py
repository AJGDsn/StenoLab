# logic/review_export.py
"""
Review files: dictionaries exported for the read-only iPad viewer (web/).

A review file is JSON:

    {
      "format": "stenolab-review",
      "version": 1,
      "name": "Ian",                      dictionary name, for display
      "source": "Ian.rtf",                file it was exported from
      "description": "Conflicts",         which search / filters were applied
      "exported": "2026-10-24T15:04",
      "entries": [
        ["KAT", "cat", "a comment"],      steno, translation, comment
        ["TKOG", "dog"]                   (comment left off when empty)
      ]
    }

Entries are compact arrays so a large dictionary stays small; the only
metadata carried is each steno's comment.
"""
import json
import os
from datetime import datetime

from .file_io import atomic_write_text

REVIEW_FORMAT = "stenolab-review"
REVIEW_VERSION = 1


def build_review(entries, metadata, *, name, source, description) -> dict:
    metadata = metadata or {}
    rows = []
    for entry in entries:
        steno = entry["steno"]
        english = entry.get("english")
        comment = (metadata.get(steno) or {}).get("comments", "")
        rows.append([steno, english, comment] if comment else [steno, english])
    return {
        "format": REVIEW_FORMAT,
        "version": REVIEW_VERSION,
        "name": name,
        "source": os.path.basename(source) if source else "",
        "description": description,
        "exported": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "entries": rows,
    }


def write_review(path: str, review: dict) -> None:
    atomic_write_text(path, json.dumps(review, ensure_ascii=False, separators=(",", ":")))
