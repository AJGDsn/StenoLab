import pytest

from logic.dictionary_loader import load_dictionary_with_metadata
from logic.rtf_dictionary import (
    plover_to_rtf,
    read_rtf_dictionary,
    write_rtf_dictionary,
)

HEADER = "{\\rtf1\\ansi{\\*\\cxrev100}\\cxdict{\\*\\cxsystem Test}{\\stylesheet{\\s0 Normal;}}"


def _translations(body):
    _, entries = read_rtf_dictionary(HEADER + "\r\n" + body + "\r\n}")
    return [(steno, english) for steno, english, _ in entries]


@pytest.mark.parametrize(
    "rtf, plover",
    [
        ("hello world", "hello world"),
        ("\\cxds ing", "{^ing}"),
        ("un\\cxds ", "{un^}"),
        ("\\cxds -\\cxds ", "{^-^}"),
        ("{\\cxds  ,564}", "{^ ,564}"),
        ("{\\cxds 15 \\cxds}", "{^15 ^}"),
        ("{\\cxp. }", "{.}"),
        ("{\\cxp, }", "{,}"),
        ("\\cxfc ", "{-|}"),
        ("{\\cxfing a}", "{&a}"),
        ("\\par ", "{^\n^}"),
        ("caf\\u233?", "café"),
        ("caf\\'e9", "café"),
        ("\\{brace\\}", "\\{brace\\}"),
        ("{\\*\\cxplovermeta #Return}", "{#Return}"),
        ("{\\*\\cxplovermacro undo}", "=undo"),
        (" 'em", "'em"),
        ("{\\i italic}", "{\\i italic}"),
    ],
)
def test_rtf_translation_converts_to_plover(rtf, plover):
    assert _translations("{\\*\\cxs TEFT}" + rtf) == [("TEFT", plover)]


@pytest.mark.parametrize(
    "plover",
    ["hello", "{^ing}", "{un^}", "{^-^}", "{.}", "{-|}", "{&a}", "{^\n^}",
     "café \U0001F600", "\\{x\\}", "{#Return}", "=undo", "{\\i italic}",
     "a{^}b", "{>}word"],
)
def test_plover_round_trips_through_rtf(plover):
    assert _translations("{\\*\\cxs TEFT}" + plover_to_rtf(plover)) == [("TEFT", plover)]


def test_entry_extras_are_hidden_and_preserved():
    body = "{\\*\\cxs KAT}cat{\\*\\cxsvatdictentrydate\\yr2006\\mo5\\da15}"
    header, entries = read_rtf_dictionary(HEADER + "\r\n" + body + "\r\n}")
    assert entries == [("KAT", "cat", "{\\*\\cxsvatdictentrydate\\yr2006\\mo5\\da15}")]

    out = write_rtf_dictionary(
        [{"steno": "KAT", "english": "cat", "rtf_extra": entries[0][2]}], header
    )
    assert body in out
    assert out.startswith(HEADER)


def test_load_rtf_dictionary_preserves_duplicates_and_extras(tmp_path):
    dictionary = tmp_path / "dict.rtf"
    dictionary.write_text(
        HEADER + "\r\n{\\*\\cxs ST}first\r\n{\\*\\cxs ST}second{\\*\\cxcomment note}\r\n}",
        encoding="ascii",
    )

    entries, metadata, has_metadata = load_dictionary_with_metadata(str(dictionary))

    assert [(e["steno"], e["english"]) for e in entries] == [("ST", "first"), ("ST", "second")]
    assert entries[1]["rtf_extra"] == "{\\*\\cxcomment note}"
    assert "rtf_extra" not in entries[0]
    assert metadata == {}
    assert not has_metadata


def test_load_rejects_non_rtf_file_with_rtf_extension(tmp_path):
    dictionary = tmp_path / "dict.rtf"
    dictionary.write_text('{"ST": "first"}', encoding="utf-8")

    with pytest.raises(ValueError, match="RTF/CRE"):
        load_dictionary_with_metadata(str(dictionary))
