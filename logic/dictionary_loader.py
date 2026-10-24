# logic/dictionary_loader.py
import json
from .metadata_store import SIDECAR_SUFFIX, import_sidecar_metadata, load_metadata
from .rtf_dictionary import decode_rtf_bytes, is_rtf_path, read_rtf_dictionary


def load_dictionary_with_metadata(dict_path: str):
    """
    Load a dictionary (JSON, or RTF/CRE by .rtf extension) and its metadata
    (if present).  RTF translations are converted to Plover syntax.

    Duplicate steno keys are preserved as separate entries so they surface
    as conflicts in the UI.  Standard json.load() silently keeps only the
    last value for duplicate keys; object_pairs_hook bypasses that.

    Returns:
        entries: list of {
            "steno": str,
            "english": str,
            "modified": str,
            "date_added": str
        }
        metadata: dict keyed by steno
        has_metadata: bool
    """
    if is_rtf_path(dict_path):
        triples = _read_rtf_triples(dict_path)
    else:
        triples = [(steno, english, None) for steno, english in _read_json_pairs(dict_path)]

    import_sidecar_metadata(dict_path)
    metadata = load_metadata(dict_path)
    has_metadata = len(metadata) > 0

    entries = []
    for steno, english, rtf_extra in triples:
        meta = metadata.get(steno, {})
        entry = {
            "steno": steno,
            "english": english,
            "modified": meta.get("modified", ""),
            "date_added": meta.get("date_added", ""),
        }
        if rtf_extra:
            entry["rtf_extra"] = rtf_extra
        entries.append(entry)

    return entries, metadata, has_metadata


def _read_json_pairs(dict_path: str):
    with open(dict_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # object_pairs_hook returns the raw [(steno, english), ...] list,
    # preserving any duplicate keys rather than collapsing to a dict.
    pairs = json.loads(raw_text, object_pairs_hook=lambda p: p)

    if not isinstance(pairs, list) or any(
        not isinstance(pair, tuple) or len(pair) != 2
        for pair in pairs
    ):
        raise ValueError(f"Dictionary file must be a JSON object: {dict_path}")
    # A dictionary maps steno to translation text; a metadata file maps it
    # to records, and is easy to pick by mistake from the Open dialog.
    if any(not isinstance(english, (str, type(None))) for _steno, english in pairs):
        if dict_path.lower().endswith(SIDECAR_SUFFIX):
            raise ValueError(
                "This is a StenoLab metadata file, not a dictionary. Open the "
                "dictionary beside it instead; its metadata is read automatically."
            )
        raise ValueError(f"Dictionary translations must be text: {dict_path}")
    return pairs


def _read_rtf_triples(dict_path: str):
    with open(dict_path, "rb") as f:
        raw_text = decode_rtf_bytes(f.read())
    try:
        _, triples = read_rtf_dictionary(raw_text)
    except ValueError:
        raise ValueError(f"Dictionary file must be an RTF/CRE dictionary: {dict_path}")
    return triples


def read_rtf_header(dict_path: str) -> str | None:
    """Header of an existing RTF dictionary, reused when saving over it."""
    try:
        with open(dict_path, "rb") as f:
            header, _ = read_rtf_dictionary(decode_rtf_bytes(f.read()))
        return header
    except (OSError, ValueError):
        return None
