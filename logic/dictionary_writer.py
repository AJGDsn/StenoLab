# logic/dictionary_writer.py
import json

from .dictionary_loader import load_dictionary_with_metadata, read_rtf_header
from .file_io import atomic_write_text
from .metadata_store import save_metadata
from .rtf_dictionary import is_rtf_path, write_rtf_dictionary


def serialize_dictionary(entries, dict_path: str) -> str:
    """
    Serialize entries in the format implied by dict_path's extension.

    Duplicate steno keys are preserved in both formats.  For RTF, the
    header of an existing file at dict_path (CAT system, stylesheet) is
    reused; a new file gets a standard header.
    """
    if is_rtf_path(dict_path):
        return write_rtf_dictionary(entries, read_rtf_header(dict_path))

    # Preserve duplicate steno keys by writing object members manually
    # rather than collapsing into a Python dict.
    pieces = []
    for entry in entries:
        k = json.dumps(entry["steno"], ensure_ascii=False)
        v = json.dumps(entry["english"], ensure_ascii=False)
        pieces.append(f"  {k}: {v}")
    return "{\n" + ",\n".join(pieces) + "\n}" if pieces else "{}"


def write_dictionary(entries, dict_path: str) -> None:
    serialized = serialize_dictionary(entries, dict_path)
    # newline="" keeps the RTF writer's CRLFs as written.
    newline = "" if is_rtf_path(dict_path) else None
    atomic_write_text(dict_path, serialized, newline=newline)


def convert_dictionary(src_path: str, dst_path: str) -> int:
    """
    Convert the dictionary at src_path to the format of dst_path's extension.

    The source's metadata sidecar is copied to the destination so dates,
    brief flags and comments carry over.  Returns the number of entries.
    """
    entries, metadata, has_metadata = load_dictionary_with_metadata(src_path)
    write_dictionary(entries, dst_path)
    if has_metadata:
        save_metadata(dst_path, metadata)
    return len(entries)
