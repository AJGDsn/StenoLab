# logic/settings_store.py
import copy
import json
import os

from .file_io import atomic_write_text
from .storage_paths import SETTINGS_PATH, LEGACY_SETTINGS_PATH

# The app is the only writer of its settings file, so the last settings read
# or written are kept in memory instead of re-reading the file on every
# access.  Keyed by path so a changed SETTINGS_PATH (tests) starts afresh.
_cache = {"path": None, "settings": None}


def _ensure_settings_folder():
    folder = os.path.dirname(SETTINGS_PATH)
    os.makedirs(folder, exist_ok=True)

def _read_settings_file(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _remember(settings: dict) -> None:
    _cache["path"] = SETTINGS_PATH
    _cache["settings"] = copy.deepcopy(settings)

def load_settings():
    """Return a copy of the settings; callers may change it and save it."""
    if _cache["path"] == SETTINGS_PATH and _cache["settings"] is not None:
        return copy.deepcopy(_cache["settings"])
    _ensure_settings_folder()
    if os.path.exists(SETTINGS_PATH):
        settings = _read_settings_file(SETTINGS_PATH)
    elif os.path.exists(LEGACY_SETTINGS_PATH):
        settings = _read_settings_file(LEGACY_SETTINGS_PATH)
        if settings:
            save_settings(settings)
    else:
        settings = {}
    _remember(settings)
    return copy.deepcopy(settings)

def save_settings(settings: dict):
    _ensure_settings_folder()
    try:
        atomic_write_text(SETTINGS_PATH, json.dumps(settings, indent=2))
        _remember(settings)
    except Exception as e:
        print(f"[StenoEditor] Failed to save settings to {SETTINGS_PATH}: {e}")
