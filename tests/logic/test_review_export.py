import json

from logic.review_export import REVIEW_FORMAT, build_review, write_review


def test_review_carries_steno_translation_and_only_non_empty_comments(tmp_path):
    entries = [{"steno": "KAT", "english": "cat"}, {"steno": "TKOG", "english": "dog"},
               {"steno": "KAT", "english": "kat"}, {"steno": "TPHUL", "english": None}]
    metadata = {"KAT": {"comments": "shared note", "brief": True}, "TKOG": {"comments": ""}}

    review = build_review(entries, metadata, name="Ian", source=r"C:\dicts\Ian.rtf",
                          description="Conflicts")
    path = tmp_path / "Ian - review.json"
    write_review(str(path), review)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded["format"] == REVIEW_FORMAT and loaded["version"] == 1
    assert loaded["name"] == "Ian" and loaded["source"] == "Ian.rtf"
    assert loaded["description"] == "Conflicts"
    assert loaded["entries"] == [
        ["KAT", "cat", "shared note"], ["TKOG", "dog"],
        ["KAT", "kat", "shared note"], ["TPHUL", None],
    ]
