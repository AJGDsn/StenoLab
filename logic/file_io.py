# logic/file_io.py
import os
import tempfile
import time


def atomic_write_text(path: str, text: str, *, newline: str | None = None) -> None:
    """
    Replace the file at path with text, so it is never left half-written.

    The text goes to a temporary file in the same folder, which is flushed
    to disk and then swapped in with os.replace.  If anything fails, the
    original file is untouched and the temporary file is removed.
    """
    _atomic_write(path, "w", text, encoding="utf-8", newline=newline)


def atomic_write_bytes(path: str, data: bytes) -> None:
    """Byte-for-byte variant of atomic_write_text (used when restoring backups)."""
    _atomic_write(path, "wb", data)


def _atomic_write(path, mode, data, **open_kwargs):
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=folder
    )
    try:
        with os.fdopen(fd, mode, **open_kwargs) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _replace_with_retry(src: str, dst: str, attempts: int = 5) -> None:
    # On Windows, os.replace fails with PermissionError while another process
    # (OneDrive, Dropbox, antivirus) briefly holds the target open.
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.1 * (attempt + 1))
