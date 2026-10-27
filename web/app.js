// web/app.js
// StenoLab Viewer: a read-only dictionary viewer for the iPad.
//
// Dictionaries are opened from the Files app (so OneDrive and Dropbox work),
// read entirely on the device, and kept in IndexedDB for next time.  Each
// dictionary is held as compact rows: [steno, translation, comment?].
(function () {
  "use strict";

  const ROW_HEIGHT = 52;            // keep in step with --row in style.css
  const COMPARE = "compare";        // id of the Compare tab
  const MAX_COMPARE_HITS = 20;
  const $ = (id) => document.getElementById(id);

  const state = {
    dicts: [],                      // see makeDict()
    active: null,                   // a dictionary id, COMPARE, or null
    sort: { col: 1, dir: "asc" },   // col 0 = steno, 1 = translation
    visible: [],                    // row indices of the active dictionary, in display order
  };

  // ---------------------------------------------------------------------
  // Reading files
  // ---------------------------------------------------------------------

  // A flat JSON object of steno -> translation, keeping duplicate keys
  // (JSON.parse would keep only the last), as StenoLab does.
  function parseFlatJson(text) {
    let i = 0;
    const n = text.length;
    const ws = () => { while (i < n && " \t\r\n﻿".includes(text[i])) i++; };
    const fail = (what) => { throw new Error(`Not a JSON dictionary (${what} at character ${i})`); };
    const str = () => {
      if (text[i] !== '"') fail("expected a string");
      const start = i++;
      while (i < n && text[i] !== '"') i += text[i] === "\\" ? 2 : 1;
      i++;
      return JSON.parse(text.slice(start, i));
    };
    const rows = [];
    ws();
    if (text[i++] !== "{") fail("expected {");
    ws();
    if (text[i] === "}") return rows;
    for (;;) {
      ws();
      const key = str();
      ws();
      if (text[i++] !== ":") fail("expected :");
      ws();
      let value;
      if (text.startsWith("null", i)) { value = null; i += 4; } else value = str();
      rows.push([key, value]);
      ws();
      const c = text[i++];
      if (c === "}") return rows;
      if (c !== ",") fail("expected , or }");
    }
  }

  async function readDictionaryFile(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    const head = new TextDecoder("latin1").decode(bytes.subarray(0, 64)).trimStart();
    if (/\.rtf$/i.test(file.name) || head.startsWith("{\\rtf")) {
      const rows = StenoRTF.readRtfDictionary(StenoRTF.decodeRtfBytes(bytes));
      return makeDict({ name: baseName(file.name), source: file.name, kind: "RTF", rows });
    }
    const text = new TextDecoder("utf-8").decode(bytes);
    let review = null;
    try {
      const parsed = JSON.parse(text);
      if (parsed && parsed.format === "stenolab-review") review = parsed;
    } catch (e) { /* not plain JSON either way; parseFlatJson reports it */ }
    if (review) {
      return makeDict({
        name: review.name || baseName(file.name), source: file.name, kind: "Review",
        description: review.description, exported: review.exported, rows: review.entries,
      });
    }
    return makeDict({ name: baseName(file.name), source: file.name, kind: "JSON", rows: parseFlatJson(text) });
  }

  function baseName(fileName) {
    return fileName.replace(/\.(json|rtf)$/i, "");
  }

  function makeDict(d) {
    return {
      id: d.id || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name: d.name, source: d.source, kind: d.kind,
      description: d.description || "", exported: d.exported || "",
      rows: d.rows,
      added: d.added || new Date().toISOString(),
      cache: {},                    // derived arrays; never stored
    };
  }

  // Lowered, trimmed text of one column for every row (built once).
  function columnText(dict, col) {
    const key = `text${col}`;
    if (!dict.cache[key]) {
      dict.cache[key] = dict.rows.map((r) => (r[col] == null ? "" : String(r[col])).trim().toLowerCase());
    }
    return dict.cache[key];
  }

  // Row indices in the current sort order (built once per sort).
  function sortedIndices(dict) {
    const { col, dir } = state.sort;
    const asc = `order${col}`;
    if (!dict.cache[asc]) {
      const text = columnText(dict, col);
      const order = dict.rows.map((_, i) => i);
      order.sort((a, b) => (text[a] < text[b] ? -1 : text[a] > text[b] ? 1 : a - b));
      dict.cache[asc] = order;
    }
    if (dir === "asc") return dict.cache[asc];
    const desc = `${asc}desc`;
    if (!dict.cache[desc]) dict.cache[desc] = dict.cache[asc].slice().reverse();
    return dict.cache[desc];
  }

  // ---------------------------------------------------------------------
  // Storage (IndexedDB), so dictionaries are still here next time
  // ---------------------------------------------------------------------
  let dbPromise = null;
  function db() {
    if (!dbPromise) {
      dbPromise = new Promise((resolve, reject) => {
        const req = indexedDB.open("stenolab-viewer", 1);
        req.onupgradeneeded = () => req.result.createObjectStore("dicts", { keyPath: "id" });
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
    }
    return dbPromise;
  }

  async function storeDict(dict) {
    const { cache, ...stored } = dict;
    const tx = (await db()).transaction("dicts", "readwrite");
    tx.objectStore("dicts").put(stored);
    return new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error); });
  }

  async function deleteDict(id) {
    const tx = (await db()).transaction("dicts", "readwrite");
    tx.objectStore("dicts").delete(id);
    return new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error); });
  }

  async function loadStoredDicts() {
    try {
      const store = (await db()).transaction("dicts").objectStore("dicts");
      const all = await new Promise((res, rej) => {
        const req = store.getAll();
        req.onsuccess = () => res(req.result);
        req.onerror = () => rej(req.error);
      });
      return all.sort((a, b) => a.added.localeCompare(b.added)).map(makeDict);
    } catch (e) {
      console.warn("Stored dictionaries unavailable", e);
      return [];
    }
  }

  // Small per-viewer conveniences (last tab, searches); losing them is harmless.
  const prefs = {
    get(key, fallback) {
      try { const v = localStorage.getItem(`stenolab.${key}`); return v === null ? fallback : JSON.parse(v); }
      catch (e) { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem(`stenolab.${key}`, JSON.stringify(value)); } catch (e) { /* ignore */ }
    },
  };

  // ---------------------------------------------------------------------
  // Tabs
  // ---------------------------------------------------------------------
  function renderTabs() {
    const tabs = $("tabs");
    tabs.textContent = "";
    for (const d of state.dicts) tabs.append(tabButton(d.id, d.name));
    if (state.dicts.length) tabs.append(tabButton(COMPARE, "Compare", "compare"));
  }

  function tabButton(id, label, cls) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", String(id === state.active));
    if (cls) b.className = cls;
    b.addEventListener("click", () => activate(id));
    return b;
  }

  function activeDict() {
    return state.dicts.find((d) => d.id === state.active) || null;
  }

  function activate(id) {
    if (!state.dicts.length) id = null;
    else if (id !== COMPARE && !state.dicts.some((d) => d.id === id)) id = state.dicts[0].id;
    state.active = id;
    prefs.set("active", id);
    renderTabs();
    $("empty-view").hidden = id !== null;
    $("compare-view").hidden = id !== COMPARE;
    $("dict-view").hidden = id === null || id === COMPARE;
    if (id === COMPARE) renderCompare();
    else if (id) { refreshList(true); renderInfo(); }
  }

  // ---------------------------------------------------------------------
  // Dictionary view: search, sort, virtual list
  // ---------------------------------------------------------------------
  const MATCHERS = {
    "Begins With": (hay, q) => hay.startsWith(q),
    "Contains": (hay, q) => hay.includes(q),
    "Ends With": (hay, q) => hay.endsWith(q),
  };

  function refreshList(resetScroll) {
    const dict = activeDict();
    if (!dict) return;
    const textQ = $("text-q").value.trim().toLowerCase();
    const stenoQ = $("steno-q").value.trim().toLowerCase();
    const textMatch = MATCHERS[$("text-method").value];
    const stenoMatch = MATCHERS[$("steno-method").value];
    const order = sortedIndices(dict);
    let visible = order;
    if (textQ || stenoQ) {
      const english = columnText(dict, 1);
      const steno = columnText(dict, 0);
      visible = order.filter((i) => (!textQ || textMatch(english[i], textQ))
                                   && (!stenoQ || stenoMatch(steno[i], stenoQ)));
    }
    state.visible = visible;
    const total = dict.rows.length;
    $("count").textContent = visible.length === total
      ? `${total.toLocaleString()} entries`
      : `${visible.length.toLocaleString()} of ${total.toLocaleString()}`;
    for (const head of document.querySelectorAll(".list-head .col")) {
      if (Number(head.dataset.sort) === state.sort.col) head.dataset.dir = state.sort.dir;
      else delete head.dataset.dir;
    }
    $("list-inner").style.height = `${visible.length * ROW_HEIGHT}px`;
    if (resetScroll) $("list").scrollTop = 0;
    pool.forEach((el) => { el.dataset.row = ""; });
    renderRows();
  }

  // Only the rows in view (plus a margin) exist as elements, recycled on scroll.
  const pool = [];
  function renderRows() {
    const dict = activeDict();
    const list = $("list");
    if (!dict) return;
    const first = Math.max(0, Math.floor(list.scrollTop / ROW_HEIGHT) - 10);
    const count = Math.ceil(list.clientHeight / ROW_HEIGHT) + 20;
    const last = Math.min(state.visible.length, first + count);
    while (pool.length < count) {
      const el = document.createElement("div");
      el.className = "row";
      el.innerHTML = '<span class="steno"></span><span class="english"></span><span class="comment"></span>';
      // Row elements are reused across tabs, so look the row up on tap.
      el.addEventListener("click", () => openDetail(Number(el.dataset.index)));
      $("list-inner").append(el);
      pool.push(el);
    }
    pool.forEach((el, k) => {
      const pos = first + k;
      if (pos >= last) { el.hidden = true; return; }
      el.hidden = false;
      if (el.dataset.row === String(pos)) return;
      const index = state.visible[pos];
      const [steno, english, comment] = dict.rows[index];
      el.dataset.row = String(pos);
      el.dataset.index = String(index);
      el.style.top = `${pos * ROW_HEIGHT}px`;
      el.children[0].textContent = steno;
      el.children[1].textContent = english == null ? "" : english;
      el.children[2].textContent = comment || "";
      el.children[2].hidden = !comment;
    });
  }

  function renderInfo() {
    const dict = activeDict();
    const info = $("dict-info");
    info.textContent = "";
    if (!dict) return;
    const parts = [dict.source];
    if (dict.kind === "Review") {
      parts.push(dict.description ? `Review: ${dict.description}` : "Review");
      if (dict.exported) parts.push(`exported ${dict.exported.replace("T", " ")}`);
    }
    const span = document.createElement("span");
    span.textContent = parts.join(" · ");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove from iPad";
    remove.addEventListener("click", () => confirmRemove(dict));
    info.append(span, remove);
  }

  function openDetail(index) {
    const dict = activeDict();
    if (!dict || Number.isNaN(index)) return;
    const [steno, english, comment] = dict.rows[index];
    $("detail-steno").textContent = steno;
    $("detail-english").textContent = english == null ? "(none)" : english;
    $("detail-comment").textContent = comment || "";
    $("detail-comment").hidden = $("detail-comment-label").hidden = !comment;
    $("detail-compare").onclick = () => {
      $("detail").close();
      $("compare-field").value = "1";
      $("compare-q").value = english == null ? steno : english;
      if (english == null) $("compare-field").value = "0";
      prefs.set("compare", { q: $("compare-q").value, field: $("compare-field").value });
      activate(COMPARE);
    };
    $("detail").showModal();
  }

  function confirmRemove(dict) {
    $("remove-text").textContent =
      `Remove ${dict.name} from this iPad? The file in Files is not affected; you can open it again any time.`;
    const dialog = $("remove-confirm");
    // Escape closes without setting returnValue, so clear the last answer
    // first: otherwise a previous "remove" would count as this one's.
    dialog.returnValue = "";
    dialog.onclose = async () => {
      if (dialog.returnValue !== "remove") return;
      await deleteDict(dict.id);
      state.dicts = state.dicts.filter((d) => d.id !== dict.id);
      activate(state.dicts[0] ? state.dicts[0].id : null);
    };
    dialog.showModal();
  }

  // ---------------------------------------------------------------------
  // Compare view: one word across every dictionary
  // ---------------------------------------------------------------------
  function renderCompare() {
    const out = $("compare-results");
    out.textContent = "";
    const q = $("compare-q").value.trim().toLowerCase();
    if (!q) {
      const p = document.createElement("p");
      p.className = "none";
      p.textContent = "Type a word (or choose Steno and type an outline) to see how each dictionary writes it.";
      out.append(p);
      return;
    }
    const col = Number($("compare-field").value);
    for (const dict of state.dicts) {
      const text = columnText(dict, col);
      let hits = [];
      for (let i = 0; i < text.length; i++) if (text[i] === q) hits.push(i);
      let note = "";
      if (!hits.length) {
        for (let i = 0; i < text.length; i++) if (text[i].startsWith(q)) hits.push(i);
        if (hits.length) note = "No exact match; entries beginning with it:";
      }
      const group = document.createElement("section");
      group.className = "compare-group";
      const h = document.createElement("h3");
      h.textContent = dict.name;
      group.append(h);
      if (note) {
        const n = document.createElement("div");
        n.className = "note";
        n.textContent = note;
        group.append(n);
      }
      if (!hits.length) {
        const none = document.createElement("div");
        none.className = "none";
        none.textContent = "No match";
        group.append(none);
      }
      const order = columnText(dict, col === 1 ? 0 : 1);
      hits.sort((a, b) => (text[a] < text[b] ? -1 : text[a] > text[b] ? 1
                           : order[a] < order[b] ? -1 : order[a] > order[b] ? 1 : a - b));
      for (const i of hits.slice(0, MAX_COMPARE_HITS)) {
        const [steno, english, comment] = dict.rows[i];
        const hit = document.createElement("div");
        hit.className = "hit";
        hit.innerHTML = '<span class="steno"></span><span></span>';
        hit.children[0].textContent = steno;
        hit.children[1].textContent = english == null ? "" : english;
        if (comment) {
          const c = document.createElement("span");
          c.className = "comment";
          c.textContent = comment;
          hit.append(c);
        }
        group.append(hit);
      }
      if (hits.length > MAX_COMPARE_HITS) {
        const more = document.createElement("div");
        more.className = "note";
        more.textContent = `and ${(hits.length - MAX_COMPARE_HITS).toLocaleString()} more`;
        group.append(more);
      }
      out.append(group);
    }
  }

  // ---------------------------------------------------------------------
  // Opening files
  // ---------------------------------------------------------------------
  async function openFiles(files) {
    const failures = [];
    let lastId = null;
    for (const file of files) {
      try {
        const dict = await readDictionaryFile(file);
        // Re-opening a file usually means an updated copy, so it replaces
        // the stored one of the same name.  The Files picker gives no
        // folder, so a different file that shares the name is told apart
        // only by asking.
        const existing = state.dicts.find((d) => d.source === dict.source);
        if (existing && !confirm(
          `${dict.source} is already on this iPad.\n\nOK replaces it with this file. ` +
          "Cancel keeps both.")) {
          dict.name = uniqueName(dict.name);
          state.dicts.push(dict);
        } else if (existing) {
          dict.id = existing.id;
          dict.added = existing.added;
          state.dicts = state.dicts.map((d) => (d.id === existing.id ? dict : d));
        } else {
          state.dicts.push(dict);
        }
        await storeDict(dict);
        lastId = dict.id;
      } catch (e) {
        failures.push(`${file.name}: ${e.message}`);
      }
    }
    if (lastId) activate(lastId);
    if (failures.length) alert(`Could not open:\n\n${failures.join("\n")}`);
  }

  function uniqueName(name) {
    const taken = new Set(state.dicts.map((d) => d.name));
    let n = 2;
    while (taken.has(`${name} (${n})`)) n++;
    return `${name} (${n})`;
  }

  // ---------------------------------------------------------------------
  // Wiring
  // ---------------------------------------------------------------------
  function debounce(fn, ms) {
    let t = 0;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  function init() {
    $("open-btn").addEventListener("click", () => $("file-input").click());
    $("file-input").addEventListener("change", (e) => {
      const files = [...e.target.files];
      e.target.value = "";
      if (files.length) openFiles(files);
    });

    const searchChanged = debounce(() => {
      prefs.set("search", { text: $("text-q").value, steno: $("steno-q").value,
                            textMethod: $("text-method").value, stenoMethod: $("steno-method").value });
      refreshList(true);
    }, 120);
    for (const id of ["text-q", "steno-q"]) $(id).addEventListener("input", searchChanged);
    for (const id of ["text-method", "steno-method"]) $(id).addEventListener("change", searchChanged);

    for (const head of document.querySelectorAll(".list-head .col")) {
      head.addEventListener("click", () => {
        const col = Number(head.dataset.sort);
        state.sort = { col, dir: state.sort.col === col && state.sort.dir === "asc" ? "desc" : "asc" };
        prefs.set("sort", state.sort);
        refreshList(true);
      });
    }

    $("list").addEventListener("scroll", () => requestAnimationFrame(renderRows), { passive: true });
    window.addEventListener("resize", debounce(renderRows, 100));

    const compareChanged = debounce(() => {
      prefs.set("compare", { q: $("compare-q").value, field: $("compare-field").value });
      renderCompare();
    }, 150);
    $("compare-q").addEventListener("input", compareChanged);
    $("compare-field").addEventListener("change", compareChanged);
    const savedCompare = prefs.get("compare", {});
    $("compare-q").value = savedCompare.q || "";
    if (savedCompare.field) $("compare-field").value = savedCompare.field;

    const saved = prefs.get("search", {});
    $("text-q").value = saved.text || "";
    $("steno-q").value = saved.steno || "";
    if (saved.textMethod) $("text-method").value = saved.textMethod;
    if (saved.stenoMethod) $("steno-method").value = saved.stenoMethod;
    state.sort = prefs.get("sort", state.sort);

    // Ask the browser to keep stored dictionaries rather than clear them
    // to free space (granted automatically for Home Screen apps).
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
    if ("serviceWorker" in navigator && location.protocol !== "file:") {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }

    loadStoredDicts().then((dicts) => {
      state.dicts = dicts;
      activate(prefs.get("active", dicts[0] ? dicts[0].id : null));
    });
  }

  // Exposed for tests run under Node.
  if (typeof module !== "undefined" && module.exports) module.exports = { parseFlatJson };
  else init();
})();
