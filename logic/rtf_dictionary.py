# logic/rtf_dictionary.py
"""
Read and write RTF/CRE steno dictionaries (the interchange format used by
Eclipse, Case CATalyst, Digital CAT, Plover, etc.).

Translations are converted to Plover syntax on load so RTF dictionaries
look and search the same as JSON ones, and converted back on save:

    \\cxds                  <->  {^}   (merged into {^ing}, {un^}, {^-^} when simple)
    \\cxfc / \\cxfl          <->  {-|} / {>}
    {\\cxp. }               <->  {.}   (likewise , ? ! : ;)
    {\\cxfing a}            <->  {&a}
    \\par / \\line           <->  {^\\n^}
    \\tab                   <->  {^\\t^}
    {\\*\\cxplovermeta X}    <->  {X}   (any other Plover meta)
    {\\*\\cxplovermacro X}   <->  =X
    \\uN, \\'hh              <->  the Unicode character

Anything else is kept verbatim so it survives a round trip:

  * unknown control words and formatting groups (e.g. \\s1, {\\i text})
    stay in the translation as raw RTF;
  * per-entry ignorable groups such as {\\*\\cxsvatdictentrydate ...} or
    {\\*\\cxcomment ...} are hidden from the translation and stored in the
    entry's "rtf_extra" field, then written back after the translation;
  * the file header (everything before the first entry) is reused on save.
"""
import re

DEFAULT_HEADER = (
    "{\\rtf1\\ansi{\\*\\cxrev100}\\cxdict{\\*\\cxsystem StenoLab}"
    "{\\stylesheet{\\s0 Normal;}}"
)

_PUNCTUATION = set(".,?!:;")
_CONTROL_RE = re.compile(r"\\([a-zA-Z]+)(-?\d+)? ?")
_SIMPLE_ATTACH_RE = re.compile(r"[^{}\\^\r\n\t]+")
# Printable ASCII except backslash and braces: needs no escaping or conversion.
_PLAIN_TEXT_RE = re.compile(r"[ -\[\]-z|~]*")
# Plover macros look like =undo or =retro_insert_space:args.
_MACRO_RE = re.compile(r"=[A-Za-z_][\w.]*(?::[^{}]*)?")


def is_rtf_path(path: str) -> bool:
    return bool(path) and path.lower().endswith(".rtf")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
class _Reader:
    """Single-pass RTF tokenizer that turns entry bodies into Plover strings."""

    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    # -- low-level helpers -------------------------------------------------
    def _skip_group(self, start: int) -> int:
        """Return the index just past the group opening at `start`."""
        depth = 0
        i = start
        while i < self.n:
            c = self.s[i]
            if c == "\\":
                i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return self.n

    def _group_head(self, i: int):
        """For a group at i, return (is_ignorable, control_word) of its opening."""
        j = i + 1
        while j < self.n and self.s[j] in "\r\n":
            j += 1
        ignorable = self.s.startswith("\\*", j)
        if ignorable:
            j += 2
        while j < self.n and self.s[j] in " \r\n":
            j += 1
        m = _CONTROL_RE.match(self.s, j)
        return ignorable, (m.group(1) if m else None)

    def _plain_text(self, start: int, end: int) -> str:
        """Decode the text content of s[start:end], ignoring control words."""
        pieces, _ = self._parse_span(start, end, top_level=False)
        return "".join(p[1] if p[0] in ("text", "raw") else "" for p in pieces)

    # -- span parser -------------------------------------------------------
    def _parse_span(self, start: int, end: int, top_level: bool):
        """
        Parse s[start:end] into pieces: ("text", literal), ("meta", inner),
        ("raw", rtf_source).  Returns (pieces, extras) where extras are the
        verbatim sources of hidden ignorable groups.
        """
        pieces = []
        extras = []
        uc_skip = 1
        pending_skip = 0
        i = start
        s = self.s

        def add_text(t):
            nonlocal pending_skip
            if pending_skip:
                drop = min(pending_skip, len(t))
                t = t[drop:]
                pending_skip -= drop
            if t:
                pieces.append(("text", t))

        while i < end:
            c = s[i]
            if c in "\r\n":
                i += 1
                continue
            if c == "{":
                g_end = self._skip_group(i)
                if g_end > end:
                    # Unclosed group in a malformed entry: read its contents
                    # as if the brace were not there.
                    i += 1
                    continue
                ignorable, word = self._group_head(i)
                inner_start = s.index("\\*", i) + 2 if ignorable else i + 1
                inner_end = g_end - 1
                if word == "cxplovermeta":
                    body = _CONTROL_RE.match(s, s.index("\\cxplovermeta", i)).end()
                    pieces.append(("meta", _unescape_meta(s[body:inner_end])))
                elif word == "cxplovermacro":
                    body = _CONTROL_RE.match(s, s.index("\\cxplovermacro", i)).end()
                    pieces.append(("text", "=" + _unescape_meta(s[body:inner_end])))
                elif word == "cxp" and not ignorable:
                    body = _CONTROL_RE.match(s, s.index("\\cxp", i)).end()
                    punct = self._plain_text(body, inner_end).strip()
                    if punct in _PUNCTUATION:
                        pieces.append(("meta", punct))
                    else:
                        pieces.append(("raw", s[i:g_end]))
                elif word == "cxfing" and not ignorable:
                    body = _CONTROL_RE.match(s, s.index("\\cxfing", i)).end()
                    pieces.append(("meta", "&" + self._plain_text(body, inner_end)))
                elif ignorable:
                    extras.append(s[i:g_end])
                elif word is not None and word not in _KNOWN_WORDS:
                    # Formatting group like {\i text}: keep it whole.
                    pieces.append(("raw", s[i:g_end]))
                else:
                    sub, sub_extras = self._parse_span(inner_start, inner_end, False)
                    pieces.extend(sub)
                    extras.extend(sub_extras)
                i = g_end
                continue
            if c == "}":
                i += 1
                continue
            if c == "\\":
                nxt = s[i + 1] if i + 1 < end else ""
                if nxt in "\\{}":
                    add_text(nxt)
                    i += 2
                    continue
                if nxt == "'":
                    try:
                        ch = bytes([int(s[i + 2:i + 4], 16)]).decode("cp1252")
                    except (ValueError, UnicodeDecodeError):
                        ch = "?"
                    add_text(ch)
                    i += 4
                    continue
                if nxt == "~":
                    add_text("\u00a0")
                    i += 2
                    continue
                if nxt == "_":
                    add_text("\u2011")
                    i += 2
                    continue
                if nxt == "-":
                    i += 2  # optional hyphen: no visible text
                    continue
                m = _CONTROL_RE.match(s, i)
                if not m:
                    pieces.append(("raw", s[i:i + 2]))
                    i += 2
                    continue
                word, param = m.group(1), m.group(2)
                i = m.end()
                if word == "cxds":
                    pieces.append(("meta", "^"))
                elif word == "cxfc":
                    pieces.append(("meta", "-|"))
                elif word == "cxfl":
                    pieces.append(("meta", ">"))
                elif word in ("par", "line"):
                    pieces.append(("meta", "^\n^"))
                elif word == "tab":
                    pieces.append(("meta", "^\t^"))
                elif word == "uc" and param is not None:
                    uc_skip = int(param)
                elif word == "u" and param is not None:
                    code = int(param)
                    if code < 0:
                        code += 65536
                    pieces.append(("text", chr(code)))
                    pending_skip = uc_skip
                    # A fallback written as \'hh counts as one character.
                    while pending_skip and s.startswith("\\'", i):
                        i += 4
                        pending_skip -= 1
                else:
                    pieces.append(("raw", m.group(0)))
                continue
            # Plain text run
            j = i
            while j < end and s[j] not in "{}\\\r\n":
                j += 1
            add_text(s[i:j])
            i = j

        return _join_surrogates(pieces), extras

    # -- entries -----------------------------------------------------------
    def read(self):
        s = self.s
        first = s.find("{\\*\\cxs ")
        if not s.lstrip().startswith("{\\rtf"):
            raise ValueError("Not an RTF file")
        if first < 0:
            return s[:s.rfind("}")].rstrip("\r\n"), []
        header = s[:first].rstrip("\r\n")

        # Document end is the brace closing the outer {\rtf1 group.
        doc_end = s.rfind("}")
        if doc_end < first:
            doc_end = self.n

        # Every {\*\cxs ...} group starts an entry.  Locating them by marker
        # rather than by brace matching keeps one malformed entry (e.g. an
        # unbalanced brace) from swallowing the rest of the file.
        starts = []
        i = first
        while 0 <= i < doc_end:
            if i == 0 or s[i - 1] != "\\":
                starts.append(i)
            i = s.find("{\\*\\cxs ", i + 1)

        entries = []
        for idx, st in enumerate(starts):
            steno_end = s.find("}", st) + 1
            steno = s[st + len("{\\*\\cxs "):steno_end - 1].strip()
            body_end = starts[idx + 1] if idx + 1 < len(starts) else doc_end
            pieces, extras = self._parse_span(steno_end, body_end, top_level=True)
            entries.append((steno, _pieces_to_plover(pieces), "".join(extras)))
        return header, entries


_KNOWN_WORDS = {"cxds", "cxfc", "cxfl", "par", "line", "tab", "u", "uc"}


def _join_surrogates(pieces):
    """Merge text pieces so \\u surrogate pairs become single characters."""
    out = []
    for p in pieces:
        if p[0] == "text" and out and out[-1][0] == "text":
            out[-1] = ("text", out[-1][1] + p[1])
        else:
            out.append(p)
    fixed = []
    for kind, val in out:
        if kind == "text":
            val = val.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
        fixed.append((kind, val))
    return fixed


def _escape_plover_text(t: str) -> str:
    return t.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _unescape_meta(raw: str) -> str:
    return raw.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")


def _pieces_to_plover(pieces) -> str:
    # Trim insignificant whitespace (e.g. Eclipse's "{\*\cxs X} word").
    if pieces and pieces[0][0] == "text":
        pieces[0] = ("text", pieces[0][1].lstrip(" "))
    if pieces and pieces[-1][0] == "text":
        pieces[-1] = ("text", pieces[-1][1].rstrip(" "))
    pieces = [p for p in pieces if p[1] != "" or p[0] == "meta"]

    # Collapse simple attach patterns into Plover's compact forms.
    kinds = [(k, v) for k, v in pieces]
    if len(kinds) in (2, 3):
        texts = [v for k, v in kinds if k == "text"]
        if len(texts) == 1 and _SIMPLE_ATTACH_RE.fullmatch(texts[0]):
            t = _escape_plover_text(texts[0])
            pattern = tuple(v if k == "meta" else "T" for k, v in kinds)
            compact = {
                ("^", "T"): "{^%s}",
                ("T", "^"): "{%s^}",
                ("^", "T", "^"): "{^%s^}",
            }.get(pattern)
            if compact:
                return compact % t

    out = []
    for kind, val in pieces:
        if kind == "text":
            out.append(_escape_plover_text(val))
        elif kind == "meta":
            out.append("{" + val + "}")
        else:
            out.append(val)
    return "".join(out)


def read_rtf_dictionary(text: str):
    """
    Parse RTF/CRE text.

    Returns (header, [(steno, plover_translation, rtf_extra), ...]).
    Duplicate steno strokes are preserved as separate entries.
    """
    return _Reader(text).read()


def decode_rtf_bytes(raw: bytes) -> str:
    """RTF is 7-bit ASCII in principle; tolerate stray cp1252 / UTF-8 bytes."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def _escape_rtf_text(t: str) -> str:
    out = []
    for ch in t:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == "{":
            out.append("\\{")
        elif ch == "}":
            out.append("\\}")
        elif ch == "\n":
            out.append("\\par ")
        elif ch == "\t":
            out.append("\\tab ")
        elif ch == "\u00a0":
            out.append("\\~")
        elif ch == "\u2011":
            out.append("\\_")
        elif o < 128:
            out.append(ch)
        else:
            for unit in _utf16_units(ch):
                signed = unit - 65536 if unit > 32767 else unit
                out.append(f"\\u{signed}?")
    return "".join(out)


def _utf16_units(ch: str):
    data = ch.encode("utf-16-le")
    return [int.from_bytes(data[k:k + 2], "little") for k in range(0, len(data), 2)]


def _meta_to_rtf(meta: str) -> str:
    if meta == "^":
        return "\\cxds "
    if meta == "-|":
        return "\\cxfc "
    if meta == ">":
        return "\\cxfl "
    if meta in _PUNCTUATION:
        return "{\\cxp%s }" % meta
    if meta in ("^\n^", "^\\n^"):
        return "\\par "
    if meta in ("^\t^", "^\\t^"):
        return "\\tab "
    if meta.startswith("&") and len(meta) > 1:
        return "{\\cxfing %s}" % _escape_rtf_text(meta[1:])
    # Attach forms {^text}, {text^}, {^text^}
    if len(meta) > 1 and (meta[0] == "^" or meta[-1] == "^"):
        core = meta[1 if meta[0] == "^" else 0:len(meta) - (1 if meta[-1] == "^" else 0)]
        if core and "^" not in core and _SIMPLE_ATTACH_RE.fullmatch(core):
            return (
                ("\\cxds " if meta[0] == "^" else "")
                + _escape_rtf_text(core)
                + ("\\cxds " if meta[-1] == "^" else "")
            )
    escaped = meta.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return "{\\*\\cxplovermeta %s}" % escaped


def _find_close(t: str, start: int) -> int:
    """Index of the brace closing the one at `start`, honoring escapes."""
    depth = 0
    i = start
    while i < len(t):
        c = t[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def plover_to_rtf(translation: str) -> str:
    """Convert a Plover-syntax translation into an RTF/CRE entry body."""
    # Most translations are plain words: printable ASCII with nothing RTF
    # or Plover treats specially.  Those are written unchanged, which keeps
    # saving a large dictionary fast.
    if _PLAIN_TEXT_RE.fullmatch(translation) and not translation.startswith("="):
        return translation
    if _MACRO_RE.fullmatch(translation):
        return "{\\*\\cxplovermacro %s}" % _escape_rtf_text(translation[1:])

    out = []
    text = []
    i = 0
    t = translation

    def flush():
        if text:
            out.append(_escape_rtf_text("".join(text)))
            text.clear()

    while i < len(t):
        c = t[i]
        if c == "\\" and i + 1 < len(t):
            nxt = t[i + 1]
            if nxt in "\\{}":
                text.append(nxt)
                i += 2
                continue
            m = _CONTROL_RE.match(t, i)
            if m:
                # Raw RTF control word kept from the original file.
                flush()
                out.append(m.group(0))
                i = m.end()
                continue
            if not nxt.isspace():
                # Raw RTF control symbol such as \" or \|.
                flush()
                out.append(t[i:i + 2])
                i += 2
                continue
            text.append(c)
            i += 1
            continue
        if c == "{":
            close = _find_close(t, i)
            if close < 0:
                text.append(c)
                i += 1
                continue
            flush()
            inner = t[i + 1:close]
            if inner.startswith("\\") and not inner.startswith(("\\{", "\\}", "\\\\")):
                out.append(t[i:close + 1])  # raw RTF group, e.g. {\i text}
            else:
                out.append(_meta_to_rtf(inner))
            i = close + 1
            continue
        text.append(c)
        i += 1
    flush()
    return "".join(out)


def write_rtf_dictionary(entries, header: str | None = None) -> str:
    """
    Serialize entries ({"steno", "english", optional "rtf_extra"}) to RTF/CRE.
    Order and duplicate steno keys are preserved.
    """
    lines = [(header or DEFAULT_HEADER).rstrip("\r\n")]
    for entry in entries:
        body = plover_to_rtf(entry["english"])
        extra = entry.get("rtf_extra", "")
        lines.append("{\\*\\cxs %s}%s%s" % (entry["steno"], body, extra))
    return "\r\n".join(lines) + "\r\n}\r\n"
