"""web/rtf.js must read RTF exactly as logic/rtf_dictionary.py does."""
import json
import os
import shutil
import subprocess

import pytest

from logic.rtf_dictionary import read_rtf_dictionary

HERE = os.path.dirname(os.path.abspath(__file__))

BODIES = [
    r"hello world", r"\cxds ing", r"un\cxds ", r"\cxds -\cxds ", r"{\cxds  ,564}",
    r"{\cxds 15 \cxds}", r"{\cxp. }", r"{\cxp, }", r"\cxfc ", r"{\cxfing a}", r"\par ",
    r"caf\u233?", r"caf\'e9", r"\{brace\}", r"{\*\cxplovermeta #Return}",
    r"{\*\cxplovermacro undo}", r" 'em", r"{\i italic}", r"x\'81y", r"\"{^}{-|}",
    r"{\cxconf [{\cxc\cxds", r"cat{\*\cxsvatdictentrydate\yr2006\mo5\da15}",
    r"\u-10179?\u-8704?",
]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_js_reader_matches_python(tmp_path):
    body = "\r\n".join(f"{{\\*\\cxs S{i}}}{b}" for i, b in enumerate(BODIES))
    text = "{\\rtf1\\ansi\\cxdict{\\*\\cxsystem Test}\r\n" + body + "\r\n}"
    path = tmp_path / "sample.rtf"
    path.write_bytes(text.encode("cp1252"))

    _, triples = read_rtf_dictionary(text)
    python = [[steno, english] for steno, english, _extra in triples]
    js = json.loads(subprocess.run(
        ["node", os.path.join(HERE, "rtf_dump.js"), str(path)],
        capture_output=True, check=True, encoding="utf-8").stdout)
    assert len(python) == len(BODIES)
    assert js == python
