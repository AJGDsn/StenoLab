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
    if not isinstance(data, dict):
        return {}
    # save_metadata leaves default-valued fields out; put them back so every
    # record in memory has the full shape.
    data = {
        steno: {**_OMIT_WHEN_DEFAULT, **record} if isinstance(record, dict) else record
        for steno, record in data.items()
    }
    if path != candidates[0]:
        try:
            _ensure_dirs()
            atomic_write_text(candidates[0], json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            pass
    return data


# ------------------------------------------------------------
# Metadata delivered beside a dictionary
# ------------------------------------------------------------

# Tools that build dictionaries (e.g. the Steno Theory scripts) can deliver
# metadata in StenoLab's format as "<dictionary name>.stenolab-meta.json"
# next to the dictionary file.
SIDECAR_SUFFIX = ".stenolab-meta.json"


def sidecar_path_for(dictionary_path: str) -> str:
    return os.path.splitext(dictionary_path)[0] + SIDECAR_SUFFIX


# Marks a delivered comment that clashed with one edited in StenoLab; the
# user searches comments for it to resolve them.
DELIVERED_COMMENT_MARK = "[Delivered]"


def _delivered_file_for(dictionary_path: str) -> str:
    """StenoLab's copy of the delivery it last imported for a dictionary."""
    return os.path.splitext(_metadata_file_for(dictionary_path))[0] + ".delivered.json"


def _file_stamp(path: str) -> list:
    stat = os.stat(path)
    return [stat.st_size, stat.st_mtime_ns]


def _read_json_object(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_delivered(dictionary_path: str, stamp: list, delivered: dict) -> None:
    _ensure_dirs()
    atomic_write_text(
        _delivered_file_for(dictionary_path),
        json.dumps({"stamp": stamp, "entries": delivered},
                   ensure_ascii=False, separators=(",", ":")),
    )


def _merge_field(field: str, base, delivered, current):
    """
    Three-way merge of one field: base is the previous delivery's value,
    current is StenoLab's.  Returns the merged value and whether the two
    sides clashed.
    """
    default = _OMIT_WHEN_DEFAULT.get(field, "")
    if field in ("date_added", "modified") and not delivered:
        return current, False          # blank dates never wipe stored ones
    if delivered == base or delivered == current:
        return current, False          # the delivery didn't change it
    if current == base or current in (None, default):
        return delivered, False        # the user didn't change it
    if field == "comments":
        if delivered and delivered not in current:
            return f"{current}\n{DELIVERED_COMMENT_MARK} {delivered}", True
        return current, False
    return current, True               # other fields: the user's value stays


def import_sidecar_metadata(dictionary_path: str) -> int | None:
    """
    Merge a delivered metadata file into StenoLab's own store.

    StenoLab keeps a copy of each delivery it imports.  When a different
    delivery turns up, only the fields that changed since that copy are
    applied, so comments and flags edited in StenoLab survive a rebuild.
    Where both sides changed a comment, the delivered text is added after
    the user's, marked with DELIVERED_COMMENT_MARK, and the entry is
    bookmarked.  Blank delivered dates never wipe stored ones.

    Returns None when nothing was imported, otherwise the number of
    comments that clashed.
    """
    sidecar = sidecar_path_for(dictionary_path)
    if not os.path.isfile(sidecar):
        return None
    stamp = _file_stamp(sidecar)
    previous = _read_json_object(_delivered_file_for(dictionary_path))
    if previous is not None and previous.get("stamp") == stamp:
        return None
    delivered = _read_json_object(sidecar)
    if delivered is None:
        return None

    stored = _metadata_file_for(dictionary_path)
    if previous is None and os.path.exists(stored) and os.path.getmtime(stored) >= os.path.getmtime(sidecar):
        # Imported before StenoLab kept a copy of deliveries: this one is
        # already in the store, so it becomes the base for the next merge.
        _write_delivered(dictionary_path, stamp, delivered)
        return None

    base_entries = (previous or {}).get("entries")
    base_entries = base_entries if isinstance(base_entries, dict) else {}
    merged = load_metadata(dictionary_path)
    clashes = 0
    for steno, record in delivered.items():
        if not isinstance(record, dict):
            continue
        if not isinstance(merged.get(steno), dict):
            merged[steno] = {field: value for field, value in record.items()
                             if value or field not in ("date_added", "modified")}
            continue
        base = base_entries.get(steno)
        base = base if isinstance(base, dict) else {}
        current = dict(merged[steno])
        comment_clash = False
        for field, value in record.items():
            value, clashed = _merge_field(field, base.get(field), value, current.get(field))
            comment_clash |= clashed and field == "comments"
            if value is not None:
                current[field] = value
        if comment_clash:
            current["bookmarked"] = True   # so the Bookmarked filter finds them
            clashes += 1
        merged[steno] = current
    save_metadata(dictionary_path, merged)
    _write_delivered(dictionary_path, stamp, delivered)
    return clashes


# ------------------------------------------------------------
# Saving
# ------------------------------------------------------------

# Fields whose default value is left out of the file.  Every reader uses
# .get(field, default), so a missing field reads back as its default.
_OMIT_WHEN_DEFAULT = {"brief": False, "comments": "", "bookmarked": False, "frequency": 0}
_KEEP = object()   # sentinel: never equal to a value, so the field is kept


def save_metadata(dictionary_path: str, metadata_dict: dict) -> None:
    """
    Write all metadata for a dictionary to a single JSON file.

    The file is compact (no indentation) and leaves out default-valued
    fields: for a 370k-entry dictionary that is about a quarter of the
    indented size, and json.dumps without indent uses the fast C encoder.
    """
    _ensure_dirs()
    path = _metadata_file_for(dictionary_path)
    compact = {
        steno: {
            field: value for field, value in record.items()
            if _OMIT_WHEN_DEFAULT.get(field, _KEEP) != value
        }
        for steno, record in metadata_dict.items()
    }
    atomic_write_text(path, json.dumps(compact, ensure_ascii=False, separators=(",", ":")))


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
