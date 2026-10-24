"""The viewer's JSON reader (web/app.js parseFlatJson) keeps duplicate keys,
like logic/dictionary_loader.py, so conflicts show on the iPad too."""
import json
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "..", "web", "app.js").replace("\\", "/")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_duplicates_nulls_and_escapes_survive():
    text = '{"KAT": "cat", "KAT": "kat", "TPHUL": null, "SKWR": "say \\"hi\\" \\u00e9", "-G": "{^ing}"}'
    script = (f"const {{ parseFlatJson }} = require({json.dumps(APP)});"
              f"process.stdout.write(JSON.stringify(parseFlatJson({json.dumps(text)})));")
    out = subprocess.run(["node", "-e", script], capture_output=True, check=True,
                         encoding="utf-8").stdout
    assert json.loads(out) == [
        ["KAT", "cat"], ["KAT", "kat"], ["TPHUL", None],
        ["SKWR", 'say "hi" é'], ["-G", "{^ing}"],
    ]
