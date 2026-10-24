# logic/metadata_store.py
import os
import json
import hashlib
from datetime import date

from .file_io import atomic_write_text
from .storage_paths import (
    APP_ROOT,
    LEGACY_APP_ROOT,
    METADATA_ROOT,
    LEGACY_METADATA_ROOT,
)


def _ensure_dirs() -> None:
    """Create required directories on first use rather than at import time."""
    os.makedirs(METADATA_ROOT, exist_ok=True)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _metadata_file_for(dictionary_path: str) -> str:
    """Return the metadata JSON path for a given dictionary.

    Filename includes a stable hash of the absolute dictionary path to avoid
    collisions when different folders contain dictionaries with the same name.
    """
    base = os.path.basename(dictionary_path)
    name, _ = os.path.splitext(base)
    norm = os.path.normcase(os.path.abspath(dictionary_path))
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]
    return os.path.join(METADATA_ROOT, f"{name}__{digest}.json")


def _legacy_hashed_metadata_file_for(dictionary_path: str) -> str:
    """Return hashed metadata path from the old AppData location."""
    base = os.path.basename(dictionary_path)
    name, _ = os.path.splitext(base)
    norm = os.path.normcase(os.path.abspath(dictionary_path))
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]
    return os.path.join(LEGACY_METADATA_ROOT, f"{name}__{digest}.json")


def _legacy_metadata_file_for(dictionary_path: str) -> str:
    """Return pre-hash metadata path in the new data folder."""
    base = os.path.basename(dictionary_path)
    name, _ = os.path.splitext(base)
    return os.path.join(METADATA_ROOT, f"{name}.json")


def _legacy_appdata_metadata_file_for(dictionary_path: str) -> str:
    """Return pre-hash metadata path from the old AppData location."""
    base = os.path.basename(dictionary_path)
    name, _ = os.path.splitext(base)
    return os.path.join(LEGACY_METADATA_ROOT, f"{name}.json")


def _metadata_files_for_all_locations(dictionary_path: str) -> tuple[str, ...]:
    """Return new and legacy metadata candidates for this dictionary."""
    return (
        _metadata_file_for(dictionary_path),
        _legacy_metadata_file_for(dictionary_path),
        _legacy_hashed_metadata_file_for(dictionary_path),
        _legacy_appdata_metadata_file_for(dictionary_path),
    )


# ------------------------------------------------------------
# Loading
# ------------------------------------------------------------

def load_metadata(dictionary_path: str) -> dict:
    """
    Load metadata for a dictionary.
    Returns a dict mapping steno -> metadata dict.
    Returns {} if no metadata file exists yet.
    """
    candidates = _metadata_files_for_all_locations(dictionary_path)
    path = next((p for p in candidates if os.path.exists(p)), None)
    if path is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if path != candidates[0]:
        try:
            _ensure_dirs()
            atomic_write_text(candidates[0], json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            pass
    return data


# ------------------------------------------------------------
# Saving
# ------------------------------------------------------------

def save_metadata(dictionary_path: str, metadata_dict: dict) -> None:
    """Write all metadata for a dictionary to a single JSON file."""
    _ensure_dirs()
    path = _metadata_file_for(dictionary_path)
    atomic_write_text(path, json.dumps(metadata_dict, indent=2, ensure_ascii=False))


# ------------------------------------------------------------
# Ensuring metadata exists (in-memory only - caller saves if dirty)
# ------------------------------------------------------------

def default_metadata(date_added: str, modified: str) -> dict:
    """A fresh metadata record for one steno."""
    return {
        "date_added": date_added,
        "modified": modified,
        "brief": False,
        "comments": "",
        "bookmarked": False,
        "frequency": 0,
    }


def merge_metadata(existing: dict, *, modified: str,
                   brief: bool | None = None, comments: str | None = None) -> dict:
    """
    Metadata for a steno that an entry is joining when the steno already
    has metadata (another row shares it).  The existing record wins; the
    incoming brief flag and comments are added to it rather than replacing
    it, so nothing the other row relies on is lost.
    """
    merged = dict(existing)
    merged["modified"] = modified
    if brief:
        merged["brief"] = True
    if comments:
        current = merged.get("comments", "")
        if not current:
            merged["comments"] = comments
        elif comments not in current:
            merged["comments"] = f"{current}\n{comments}"
    return merged


def ensure_metadata(entries: list, existing_metadata: dict) -> dict:
    """
    Build in-memory metadata for all entries.
    Fills in defaults for any entry not already present.
    Does NOT write to disk - caller is responsible for saving when dirty.
    """
    metadata = dict(existing_metadata) if existing_metadata else {}
    today = str(date.today())

    for entry in entries:
        steno = entry["steno"]
        if steno not in metadata:
            metadata[steno] = default_metadata(
                entry.get("date_added", today), entry.get("modified", today)
            )

    return metadata
