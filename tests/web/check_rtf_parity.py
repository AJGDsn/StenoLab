"""
Check that the iPad viewer's RTF reader (web/rtf.js) reads RTF dictionaries
exactly as StenoLab does (logic/rtf_dictionary.py).

    py tests/web/check_rtf_parity.py <folder or .rtf file> ...

Needs Node.js.  Prints one line per file and exits non-zero on any
difference.  The pytest suite runs the same comparison on small samples
(test_rtf_parity.py); this script is for checking real dictionaries.
"""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from logic.rtf_dictionary import decode_rtf_bytes, read_rtf_dictionary  # noqa: E402


def compare(path):
    with open(path, "rb") as f:
        _, triples = read_rtf_dictionary(decode_rtf_bytes(f.read()))
    python = [[steno, english] for steno, english, _extra in triples]
    out = subprocess.run(["node", os.path.join(HERE, "rtf_dump.js"), path],
                         capture_output=True, check=True, encoding="utf-8").stdout
    js = json.loads(out)
    diffs = [(i, p, j) for i, (p, j) in enumerate(zip(python, js)) if p != j]
    return len(python), len(js), diffs


def main(args):
    paths = []
    for arg in args:
        paths += sorted(glob.glob(os.path.join(arg, "**", "*.[rR][tT][fF]"), recursive=True)) \
            if os.path.isdir(arg) else [arg]
    failed = 0
    for path in paths:
        try:
            n_py, n_js, diffs = compare(path)
        except subprocess.CalledProcessError as e:
            print(f"ERROR {path}: {e.stderr.strip()[:200]}")
            failed += 1
            continue
        ok = n_py == n_js and not diffs
        failed += not ok
        print(f"{'ok  ' if ok else 'DIFF'} {n_py:>7} entries  {os.path.basename(path)}")
        for i, p, j in diffs[:3]:
            print(f"       #{i}: python {ascii(p)}\n           js     {ascii(j)}")
    print(f"{len(paths) - failed} of {len(paths)} files identical")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
