// web/rtf.js
// RTF/CRE dictionary reader for the iPad viewer: a line-for-line port of the
// reading half of logic/rtf_dictionary.py, so both apps show a translation
// identically.  tests/web/check_rtf_parity.py compares the two on real files.
// Works in the browser (window.StenoRTF) and in Node (module.exports).
(function (root) {
  "use strict";

  const CONTROL_RE = /\\([a-zA-Z]+)(-?\d+)? ?/y;
  const SIMPLE_ATTACH_RE = /^[^{}\\^\r\n\t]+$/;
  const PUNCTUATION = new Set([".", ",", "?", "!", ":", ";"]);
  const KNOWN_WORDS = new Set(["cxds", "cxfc", "cxfl", "par", "line", "tab", "u", "uc"]);
  // cp1252 bytes 0x80-0x9F; every other byte is the same as Latin-1.
  const CP1252 = {
    0x80: "€", 0x82: "‚", 0x83: "ƒ", 0x84: "„", 0x85: "…",
    0x86: "†", 0x87: "‡", 0x88: "ˆ", 0x89: "‰", 0x8a: "Š",
    0x8b: "‹", 0x8c: "Œ", 0x8e: "Ž", 0x91: "‘", 0x92: "’",
    0x93: "“", 0x94: "”", 0x95: "•", 0x96: "–", 0x97: "—",
    0x98: "˜", 0x99: "™", 0x9a: "š", 0x9b: "›", 0x9c: "œ",
    0x9e: "ž", 0x9f: "Ÿ",
  };
  const UNDEFINED_CP1252 = new Set([0x81, 0x8d, 0x8f, 0x90, 0x9d]);

  function matchControl(s, i) {
    CONTROL_RE.lastIndex = i;
    return CONTROL_RE.exec(s);
  }

  function cp1252Char(byte) {
    if (UNDEFINED_CP1252.has(byte)) return null;
    return CP1252[byte] || String.fromCharCode(byte);
  }

  function escapePloverText(t) {
    return t.replace(/\\/g, "\\\\").replace(/\{/g, "\\{").replace(/\}/g, "\\}");
  }

  function unescapeMeta(raw) {
    return raw.replace(/\\\{/g, "{").replace(/\\\}/g, "}").replace(/\\\\/g, "\\");
  }

  // Merge adjacent text pieces so \u surrogate pairs become one character;
  // lone surrogates become U+FFFD, as Python's "replace" decoding does.
  function joinSurrogates(pieces) {
    const out = [];
    for (const p of pieces) {
      const last = out[out.length - 1];
      if (p[0] === "text" && last && last[0] === "text") out[out.length - 1] = ["text", last[1] + p[1]];
      else out.push(p);
    }
    return out.map(([kind, val]) => kind === "text"
      ? [kind, val.replace(/[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/g, "�")]
      : [kind, val]);
  }

  class Reader {
    constructor(text) {
      this.s = text;
      this.n = text.length;
    }

    skipGroup(start) {
      let depth = 0;
      let i = start;
      const s = this.s;
      while (i < this.n) {
        const c = s[i];
        if (c === "\\") { i += 2; continue; }
        if (c === "{") depth += 1;
        else if (c === "}") {
          depth -= 1;
          if (depth === 0) return i + 1;
        }
        i += 1;
      }
      return this.n;
    }

    groupHead(i) {
      const s = this.s;
      let j = i + 1;
      while (j < this.n && (s[j] === "\r" || s[j] === "\n")) j += 1;
      const ignorable = s.startsWith("\\*", j);
      if (ignorable) j += 2;
      while (j < this.n && (s[j] === " " || s[j] === "\r" || s[j] === "\n")) j += 1;
      const m = matchControl(s, j);
      return [ignorable, m ? m[1] : null];
    }

    plainText(start, end) {
      const [pieces] = this.parseSpan(start, end);
      return pieces.map((p) => (p[0] === "text" || p[0] === "raw" ? p[1] : "")).join("");
    }

    parseSpan(start, end) {
      const s = this.s;
      const pieces = [];
      const extras = [];
      let ucSkip = 1;
      let pendingSkip = 0;
      let i = start;

      const addText = (t) => {
        if (pendingSkip) {
          const drop = Math.min(pendingSkip, t.length);
          t = t.slice(drop);
          pendingSkip -= drop;
        }
        if (t) pieces.push(["text", t]);
      };
      // Index just past a group's opening control word (and its space).
      const bodyAfter = (word, from) => {
        const m = matchControl(s, s.indexOf("\\" + word, from));
        return m.index + m[0].length;
      };

      while (i < end) {
        const c = s[i];
        if (c === "\r" || c === "\n") { i += 1; continue; }
        if (c === "{") {
          const gEnd = this.skipGroup(i);
          if (gEnd > end) { i += 1; continue; }  // unclosed group: ignore the brace
          const [ignorable, word] = this.groupHead(i);
          const innerStart = ignorable ? s.indexOf("\\*", i) + 2 : i + 1;
          const innerEnd = gEnd - 1;
          if (word === "cxplovermeta") {
            pieces.push(["meta", unescapeMeta(s.slice(bodyAfter(word, i), innerEnd))]);
          } else if (word === "cxplovermacro") {
            pieces.push(["text", "=" + unescapeMeta(s.slice(bodyAfter(word, i), innerEnd))]);
          } else if (word === "cxp" && !ignorable) {
            const punct = this.plainText(bodyAfter(word, i), innerEnd).trim();
            if (PUNCTUATION.has(punct)) pieces.push(["meta", punct]);
            else pieces.push(["raw", s.slice(i, gEnd)]);
          } else if (word === "cxfing" && !ignorable) {
            pieces.push(["meta", "&" + this.plainText(bodyAfter(word, i), innerEnd)]);
          } else if (ignorable) {
            extras.push(s.slice(i, gEnd));
          } else if (word !== null && !KNOWN_WORDS.has(word)) {
            pieces.push(["raw", s.slice(i, gEnd)]);  // formatting group like {\i text}
          } else {
            const [sub, subExtras] = this.parseSpan(innerStart, innerEnd);
            pieces.push(...sub);
            extras.push(...subExtras);
          }
          i = gEnd;
          continue;
        }
        if (c === "}") { i += 1; continue; }
        if (c === "\\") {
          const nxt = i + 1 < end ? s[i + 1] : "";
          if (nxt === "\\" || nxt === "{" || nxt === "}") { addText(nxt); i += 2; continue; }
          if (nxt === "'") {
            const hex = s.slice(i + 2, i + 4);
            const byte = /^[0-9a-fA-F]{1,2}$/.test(hex) ? parseInt(hex, 16) : NaN;
            const ch = Number.isNaN(byte) ? null : cp1252Char(byte);
            addText(ch === null ? "?" : ch);
            i += 4;
            continue;
          }
          if (nxt === "~") { addText(" "); i += 2; continue; }
          if (nxt === "_") { addText("‑"); i += 2; continue; }
          if (nxt === "-") { i += 2; continue; }  // optional hyphen
          const m = matchControl(s, i);
          if (!m) { pieces.push(["raw", s.slice(i, i + 2)]); i += 2; continue; }
          const word = m[1];
          const param = m[2];
          i = m.index + m[0].length;
          if (word === "cxds") pieces.push(["meta", "^"]);
          else if (word === "cxfc") pieces.push(["meta", "-|"]);
          else if (word === "cxfl") pieces.push(["meta", ">"]);
          else if (word === "par" || word === "line") pieces.push(["meta", "^\n^"]);
          else if (word === "tab") pieces.push(["meta", "^\t^"]);
          else if (word === "uc" && param !== undefined) ucSkip = parseInt(param, 10);
          else if (word === "u" && param !== undefined) {
            let code = parseInt(param, 10);
            if (code < 0) code += 65536;
            pieces.push(["text", String.fromCharCode(code)]);
            pendingSkip = ucSkip;
            while (pendingSkip && s.startsWith("\\'", i)) { i += 4; pendingSkip -= 1; }
          } else pieces.push(["raw", m[0]]);
          continue;
        }
        let j = i;
        while (j < end && !"{}\\\r\n".includes(s[j])) j += 1;
        addText(s.slice(i, j));
        i = j;
      }
      return [joinSurrogates(pieces), extras];
    }

    read() {
      const s = this.s;
      if (!s.trimStart().startsWith("{\\rtf")) throw new Error("Not an RTF file");
      const first = s.indexOf("{\\*\\cxs ");
      if (first < 0) return [];
      let docEnd = s.lastIndexOf("}");
      if (docEnd < first) docEnd = this.n;

      // Every {\*\cxs ...} group starts an entry; locating them by marker
      // keeps one malformed entry from swallowing the rest of the file.
      const starts = [];
      let i = first;
      while (i >= 0 && i < docEnd) {
        if (i === 0 || s[i - 1] !== "\\") starts.push(i);
        i = s.indexOf("{\\*\\cxs ", i + 1);
      }

      const entries = [];
      for (let k = 0; k < starts.length; k++) {
        const st = starts[k];
        const stenoEnd = s.indexOf("}", st) + 1;
        const steno = s.slice(st + "{\\*\\cxs ".length, stenoEnd - 1).trim();
        const bodyEnd = k + 1 < starts.length ? starts[k + 1] : docEnd;
        const [pieces] = this.parseSpan(stenoEnd, bodyEnd);
        entries.push([steno, piecesToPlover(pieces)]);
      }
      return entries;
    }
  }

  function piecesToPlover(pieces) {
    if (pieces.length && pieces[0][0] === "text") pieces[0] = ["text", pieces[0][1].replace(/^ +/, "")];
    const last = pieces.length - 1;
    if (pieces.length && pieces[last][0] === "text") pieces[last] = ["text", pieces[last][1].replace(/ +$/, "")];
    pieces = pieces.filter((p) => p[1] !== "" || p[0] === "meta");

    if (pieces.length === 2 || pieces.length === 3) {
      const texts = pieces.filter((p) => p[0] === "text").map((p) => p[1]);
      if (texts.length === 1 && SIMPLE_ATTACH_RE.test(texts[0])) {
        const t = escapePloverText(texts[0]);
        const pattern = pieces.map((p) => (p[0] === "meta" ? p[1] : "T")).join("|");
        const compact = { "^|T": `{^${t}}`, "T|^": `{${t}^}`, "^|T|^": `{^${t}^}` }[pattern];
        if (compact) return compact;
      }
    }
    return pieces.map(([kind, val]) => (kind === "text" ? escapePloverText(val)
      : kind === "meta" ? "{" + val + "}" : val)).join("");
  }

  // Bytes to text: UTF-8 when valid, otherwise cp1252.  The browser's
  // windows-1252 decoder turns cp1252's five undefined bytes into control
  // characters; Python reads them as U+FFFD, so do the same.
  function decodeRtfBytes(bytes) {
    try {
      return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch (e) {
      return new TextDecoder("windows-1252").decode(bytes)
        .replace(/[\u0081\u008d\u008f\u0090\u009d]/g, "�");
    }
  }

  // [[steno, translation], ...] in file order, duplicates kept.
  function readRtfDictionary(text) {
    return new Reader(text).read();
  }

  const api = { readRtfDictionary, decodeRtfBytes };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.StenoRTF = api;
})(typeof window !== "undefined" ? window : globalThis);
