/* wooo-map 07c2a89396 — generated from src/wooo-map by scripts/build_site.py; do not edit */
/* atelier WooO — Taiwan post-war architects map, mountable component.
 *
 *   import { mountWoooMap } from "./wooo-map.js";
 *   const map = await mountWoooMap(container, {
 *     architectsUrl, buildingsUrl,     // or: data: { architects, buildings }
 *     initialView: "taiwan",
 *     mobileBreakpoint: 760,           // container width, px
 *     L                                // optional Leaflet; loaded from CDN if absent
 *   });
 *   map.destroy();
 *
 * The component renders only inside `container`. It adds no header, footer,
 * logo, contact block, fonts or cursor, and it never touches document-level
 * classes or styles. Styles live in wooo-map.css, scoped to .wooo-map.
 */

const LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js";
const TILE_URL = "https://wmts.nlsc.gov.tw/wmts/EMAP01/default/GoogleMapsCompatible/{z}/{y}/{x}";
const TILE_ATTR = '底圖：<a href="https://maps.nlsc.gov.tw/" target="_blank" rel="noopener">內政部國土測繪中心 臺灣通用電子地圖（灰階）</a>';
const VIEWS = { taiwan: { center: [23.75, 120.95], zoom: 8 } };
const DIVE_ZOOM = 17;

let leafletLoading = null;
function loadLeaflet(url) {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletLoading) {
    leafletLoading = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = url; s.async = true;
      s.onload = () => (window.L ? resolve(window.L) : reject(new Error("Leaflet did not load")));
      s.onerror = () => { leafletLoading = null; reject(new Error("Leaflet did not load")); };
      document.head.appendChild(s);
    });
  }
  return leafletLoading;
}

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => n.toLocaleString("en-US");

/* description_html is untrusted: keep text, <br> and <a href="http(s)://…"> only. */
function sanitize(html) {
  const tpl = document.createElement("template");
  tpl.innerHTML = String(html || "");
  const out = document.createDocumentFragment();
  const walk = (node, parent) => {
    node.childNodes.forEach((n) => {
      if (n.nodeType === 3) { parent.appendChild(document.createTextNode(n.nodeValue)); return; }
      if (n.nodeType !== 1) return;
      const tag = n.tagName.toLowerCase();
      if (tag === "br") { parent.appendChild(document.createElement("br")); return; }
      if (tag === "script" || tag === "style" || tag === "iframe" || tag === "object") return;
      if (tag === "a") {
        const href = (n.getAttribute("href") || "").trim();
        const a = document.createElement("a");
        if (/^https?:\/\//i.test(href)) { a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; }
        walk(n, a); parent.appendChild(a); return;
      }
      walk(n, parent);
    });
  };
  walk(tpl.content, out);
  return out;
}
const plainText = (html) => { const t = document.createElement("template"); t.innerHTML = String(html || ""); return t.content.textContent || ""; };

async function getJSON(url, signal) {
  const r = await fetch(url, { credentials: "same-origin", signal });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

export async function mountWoooMap(container, opts = {}) {
  if (!container || !(container instanceof Element)) throw new Error("mountWoooMap: container element required");
  const o = Object.assign({ initialView: "taiwan", mobileBreakpoint: 760, leafletUrl: LEAFLET_JS }, opts);
  const view = typeof o.initialView === "object" ? o.initialView : (VIEWS[o.initialView] || VIEWS.taiwan);
  const ac = new AbortController();
  const on = (t, ev, fn, opt) => t.addEventListener(ev, fn, Object.assign({ signal: ac.signal }, opt || {}));
  const timers = new Set();
  const later = (fn, ms) => { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; };
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canHover = window.matchMedia && window.matchMedia("(hover: hover)").matches;

  /* ---------- skeleton ---------- */
  const uid = "wooo-map-" + Math.random().toString(36).slice(2, 8);
  const root = document.createElement("div");
  root.className = "wooo-map";
  root.innerHTML = `
    <div class="wooo-map__rail" data-part="rail">
      <button type="button" class="wooo-map__grab" data-part="grab" aria-label="展開或收合清單"><span></span></button>
      <div class="wooo-map__search">
        <label class="wooo-map__label" for="${uid}-q">search</label>
          <div class="wooo-map__sbox">
            <input class="wooo-map__input" id="${uid}-q" data-part="q" type="search" placeholder="ex: 王秀蓮 or 陳仁和 住宅" autocomplete="off" spellcheck="false">
            <button type="button" class="wooo-map__qx" data-part="qx" aria-label="清除搜尋" hidden>×</button>
          </div>
        <div class="wooo-map__stat"><div class="wooo-map__count" data-part="num" aria-live="polite">0</div><button type="button" class="wooo-map__clear" data-part="clr" hidden>清除篩選</button></div>
      </div>
      <div class="wooo-map__scroll" data-part="scroll">
        <section class="wooo-map__results" data-part="results" hidden>
          <div class="wooo-map__sec"><span>results / 搜尋結果</span><span data-part="resCnt"></span></div>
          <ul class="wooo-map__list" data-part="resList"></ul>
        </section>
        <section>
          <div class="wooo-map__sec"><span>architects / 建築師圖層</span><span data-part="layCnt"></span></div>
          <div data-part="archList"></div>
        </section>
      </div>
    </div>
    <div class="wooo-map__canvas" data-part="canvas"></div>
    <div class="wooo-map__loading" data-part="loading" aria-live="polite">loading map…</div>
    <div class="wooo-map__detail" data-part="detail" role="dialog" aria-label="建物資訊">
      <button type="button" class="wooo-map__close" data-part="close" aria-label="關閉">×</button>
      <div class="wooo-map__body" data-part="body"></div>
    </div>`;
  const $ = (p) => root.querySelector(`[data-part="${p}"]`);
  container.appendChild(root);

  /* ---------- layout: from container width ---------- */
  const isMobile = () => root.dataset.layout === "mobile";
  let lmap = null;
  const applyLayout = () => {
    const mobile = root.clientWidth > 0 && root.clientWidth <= o.mobileBreakpoint;
    const next = mobile ? "mobile" : "desktop";
    if (root.dataset.layout !== next) {
      root.dataset.layout = next;
      if (!mobile) setSheet("peek");
    }
    if (lmap) lmap.invalidateSize();
  };
  const ro = new ResizeObserver(applyLayout);
  ro.observe(root);
  on(window, "orientationchange", () => later(() => lmap && lmap.invalidateSize(), 300));

  let sheet = "peek";
  function setSheet(st) {
    sheet = st;
    if (st === "peek") delete root.dataset.sheet; else root.dataset.sheet = st;
  }
  root.dataset.layout = "desktop";
  applyLayout();

  const fail = (msg) => {
    const e = document.createElement("div");
    e.className = "wooo-map__error"; e.textContent = msg;
    root.appendChild(e);
  };

  /* ---------- data + Leaflet ---------- */
  let L, arch, bld;
  try {
    const dataP = o.data ? Promise.resolve([o.data.architects, o.data.buildings])
      : Promise.all([getJSON(o.architectsUrl, ac.signal), getJSON(o.buildingsUrl, ac.signal)]);
    [L, [arch, bld]] = await Promise.all([o.L ? Promise.resolve(o.L) : loadLeaflet(o.leafletUrl), dataP]);
  } catch (err) {
    if (ac.signal.aborted) return { destroy() {} };
    fail("map data could not be loaded");
    console.error("[wooo-map]", err);
    return { destroy() { ac.abort(); ro.disconnect(); root.remove(); } };
  }
  if (ac.signal.aborted) return { destroy() {} };

  arch = arch.slice().sort((a, b) => a.id - b.id);
  const ARCH = arch.map((a) => a.name);
  const COLORS = arch.map((a) => a.color);
  const B = bld.map((b, i) => ({
    i, n: b.name, y: b.year, a: b.architects, lat: b.lat, lng: b.lng, d: b.description_html || "", s: b.sources || [],
    t: [b.name, plainText(b.description_html).replace(/\s+/g, ""), b.architects.map((k) => ARCH[k]).join(" "), b.year || ""].join(" ").toLowerCase()
  }));
  const sortWorks = (x, y) => (x.y ?? 9999) - (y.y ?? 9999) || x.n.localeCompare(y.n, "zh-Hant");
  const byArch = ARCH.map((_, k) => B.filter((b) => b.a.includes(k)).sort(sortWorks));

  /* ---------- state ---------- */
  const selected = [];
  let tokens = [];
  const isSel = (k) => selected.includes(k);
  const matches = (b) => tokens.every((t) => b.t.includes(t));
  const inLayers = (b) => selected.length === 0 || b.a.some(isSel);
  const colorIdx = (b) => {
    if (selected.length) for (const k of selected) if (b.a.includes(k)) return k;
    for (const t of tokens) { const k = ARCH.indexOf(t); if (k >= 0 && b.a.includes(k)) return k; }
    return b.a[0];
  };

  /* ---------- map ---------- */
  lmap = L.map($("canvas"), { zoomControl: false, preferCanvas: true, minZoom: 6, maxZoom: 19, attributionControl: true })
    .setView(view.center, view.zoom);
  lmap.attributionControl.setPrefix(false);
  const Zoom = L.Control.extend({ options: { position: "topright" }, onAdd() {
    const d = L.DomUtil.create("div", "wooo-map__zoom");
    d.innerHTML = '<button type="button" aria-label="放大">+</button><button type="button" aria-label="縮小">−</button><button type="button" aria-label="全台灣">TW</button>';
    const [a, b, c] = d.querySelectorAll("button");
    a.onclick = () => lmap.zoomIn(); b.onclick = () => lmap.zoomOut();
    c.onclick = () => lmap.flyTo(view.center, view.zoom, { duration: reduceMotion ? 0 : 0.8 });
    L.DomEvent.disableClickPropagation(d); return d;
  } });
  new Zoom().addTo(lmap);
  const tiles = L.tileLayer(TILE_URL, { maxZoom: 19, className: "wooo-map__tiles", attribution: TILE_ATTR }).addTo(lmap);

  const renderer = L.canvas({ padding: 0.4 });
  const layer = L.layerGroup().addTo(lmap);
  const markers = B.map((b) => {
    const m = L.circleMarker([b.lat, b.lng], { renderer, radius: canHover ? 5.5 : 7, weight: 1.2, color: "#000", fillOpacity: 0.95, fillColor: "#888", bubblingMouseEvents: false });
    if (canHover) m.bindTooltip(esc(b.n), { direction: "top", offset: [0, -6], className: "wooo-map__tip", opacity: 1 });
    m.on("click", () => openCard(b));
    return m;
  });

  /* ---------- dive-in zoom (1 s) ---------- */
  let diveToken = 0;
  function dive(latlng, offsetY) {
    const token = ++diveToken;
    const target = Math.max(DIVE_ZOOM, lmap.getZoom());
    if (offsetY) latlng = lmap.unproject(lmap.project(latlng, target).add([0, offsetY]), target);
    if (target - lmap.getZoom() < 0.5 && lmap.distance(lmap.getCenter(), latlng) < 30) return;
    if (reduceMotion) { lmap.setView(latlng, target, { animate: false }); return; }
    if (token === diveToken) lmap.flyTo(latlng, target, { duration: 1, easeLinearity: 0.12 });
  }

  /* ---------- detail card ---------- */
  const body = $("body");
  function openCard(b) {
    body.textContent = "";
    const top = document.createElement("div"); top.className = "wooo-map__pp-top";
    top.innerHTML = `<div class="wooo-map__pp-yr">${b.y ? b.y : "年代未詳"}</div><h3 class="wooo-map__pp-title">${esc(b.n)}</h3><div class="wooo-map__chips"></div>`;
    const chips = top.querySelector(".wooo-map__chips");
    b.a.forEach((k) => {
      const c = document.createElement("button"); c.type = "button"; c.className = "wooo-map__chip";
      c.style.setProperty("--c", COLORS[k]); c.textContent = ARCH[k];
      c.addEventListener("click", () => { closeCard(); if (isMobile()) setSheet("half"); toggle(k, true); });
      chips.appendChild(c);
    });
    body.appendChild(top);
    if (b.d) { const d = document.createElement("div"); d.className = "wooo-map__pp-body"; d.appendChild(sanitize(b.d)); body.appendChild(d); }
    const src = document.createElement("div"); src.className = "wooo-map__pp-src";
    src.innerHTML = `來源：${b.s.map(esc).join("；")}<br><span>${b.lat.toFixed(5)}, ${b.lng.toFixed(5)}</span>`;
    body.appendChild(src);
    const g = document.createElement("a"); g.className = "wooo-map__gmap"; g.target = "_blank"; g.rel = "noopener noreferrer";
    g.href = `https://www.google.com/maps/search/?api=1&query=${b.lat},${b.lng}`; g.textContent = "在 Google Maps 開啟 ↗";
    body.appendChild(g);
    body.scrollTop = 0;
    root.dataset.card = "";
    requestAnimationFrame(() => {
      if (ac.signal.aborted) return;
      const h = Math.min($("detail").offsetHeight, root.clientHeight * 0.46);
      dive([b.lat, b.lng], isMobile() ? h / 2 : 0);
    });
  }
  function closeCard() { delete root.dataset.card; }
  on($("close"), "click", closeCard);
  on(root, "keydown", (e) => { if (e.key === "Escape" && "card" in root.dataset) { closeCard(); } });

  /* ---------- layer list ---------- */
  const archList = $("archList");
  const rows = ARCH.map((name, k) => {
    const el = document.createElement("div"); el.className = "wooo-map__arch"; el.style.setProperty("--c", COLORS[k]);
    el.innerHTML = `<div class="wooo-map__row" role="button" tabindex="0" aria-pressed="false"><span class="wooo-map__chk"></span><span class="wooo-map__name">${esc(name)}<small>（${byArch[k].length}）</small></span><span class="wooo-map__badge" hidden></span><button type="button" class="wooo-map__tog" aria-expanded="false" aria-label="展開 ${esc(name)} 作品列表"></button></div><ul class="wooo-map__list wooo-map__works"></ul>`;
    const row = el.firstChild, tog = el.querySelector(".wooo-map__tog");
    row.addEventListener("click", (e) => { if (e.target.closest(".wooo-map__tog")) return; toggle(k); });
    row.addEventListener("keydown", (e) => { if (e.target === row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggle(k); } });
    tog.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !("open" in el.dataset);
      if (open) { el.dataset.open = ""; renderWorks(k); } else delete el.dataset.open;
      tog.setAttribute("aria-expanded", open);
    });
    archList.appendChild(el); return el;
  });
  $("layCnt").textContent = ARCH.length + " 位";

  function workLI(b, k, withDot) {
    const li = document.createElement("li"); li.className = "wooo-map__work"; li.tabIndex = 0;
    li.innerHTML = (withDot ? `<span class="wooo-map__dot" style="--c:${COLORS[k]}"></span>` : "") + `<span class="wooo-map__yr">${b.y || "—"}</span><span>${esc(b.n)}</span>`;
    li.addEventListener("click", () => openCard(b));
    li.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); openCard(b); } });
    return li;
  }
  function renderWorks(k) {
    const ul = rows[k].querySelector(".wooo-map__works"); ul.textContent = "";
    const list = tokens.length ? byArch[k].filter(matches) : byArch[k];
    if (!list.length) { ul.innerHTML = '<li class="wooo-map__more">沒有符合搜尋的作品</li>'; return; }
    const frag = document.createDocumentFragment(); list.forEach((b) => frag.appendChild(workLI(b, k, false))); ul.appendChild(frag);
  }
  function toggle(k, scrollTo) {
    const i = selected.indexOf(k);
    if (i >= 0) selected.splice(i, 1); else selected.push(k);
    update(true);
    if (scrollTo && i < 0) rows[k].scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
  }

  /* ---------- update ---------- */
  let fitTimer = null;
  function update(fit) {
    const vis = [];
    B.forEach((b, i) => {
      const show = inLayers(b) && matches(b), m = markers[i];
      if (show) { m.setStyle({ fillColor: COLORS[colorIdx(b)] }); if (!layer.hasLayer(m)) layer.addLayer(m); vis.push(b); }
      else if (layer.hasLayer(m)) layer.removeLayer(m);
    });
    $("num").innerHTML = fmt(vis.length) + "<small>處建物" + (vis.length !== B.length ? " / 共 " + fmt(B.length) : "") + "</small>";
    $("clr").hidden = !(selected.length || tokens.length);
    if (selected.length) root.dataset.hasSel = ""; else delete root.dataset.hasSel;

    rows.forEach((el, k) => {
      const onK = isSel(k);
      if (onK) el.dataset.on = ""; else delete el.dataset.on;
      el.firstChild.setAttribute("aria-pressed", onK);
      const badge = el.querySelector(".wooo-map__badge");
      if (tokens.length) { const c = byArch[k].filter(matches).length; badge.hidden = !c; badge.textContent = "符合 " + c; if (c) delete el.dataset.dim; else el.dataset.dim = ""; }
      else { badge.hidden = true; delete el.dataset.dim; }
      if ("open" in el.dataset) renderWorks(k);
    });

    const res = $("results");
    if (tokens.length) {
      res.hidden = false;
      const list = vis.slice().sort(sortWorks);
      $("resCnt").textContent = fmt(list.length) + " 筆";
      const ul = $("resList"); ul.textContent = "";
      const frag = document.createDocumentFragment();
      if (selected.length) {
        const li = document.createElement("li"); li.className = "wooo-map__more";
        li.innerHTML = `僅顯示已勾選的 ${selected.length} 位建築師中符合者。<button type="button">改為搜尋全部</button>`;
        li.querySelector("button").addEventListener("click", () => { selected.length = 0; update(true); });
        frag.appendChild(li);
      }
      list.slice(0, 400).forEach((b) => frag.appendChild(workLI(b, colorIdx(b), true)));
      if (list.length > 400) { const li = document.createElement("li"); li.className = "wooo-map__more"; li.textContent = "僅列出前 400 筆，請加入更多關鍵字縮小範圍。"; frag.appendChild(li); }
      if (!list.length) { const li = document.createElement("li"); li.className = "wooo-map__more"; li.textContent = "沒有符合的點位。"; frag.appendChild(li); }
      ul.appendChild(frag);
    } else res.hidden = true;

    if (fit) {
      clearTimeout(fitTimer);
      fitTimer = later(() => {
        if (!vis.length) return;
        const dur = reduceMotion ? 0 : 0.8;
        if (!selected.length && !tokens.length) { lmap.flyTo(view.center, view.zoom, { duration: dur }); return; }
        const bb = L.latLngBounds(vis.map((b) => [b.lat, b.lng]));
        const pad = isMobile() ? { paddingTopLeft: [30, 30], paddingBottomRight: [30, $("rail").offsetHeight + 30] } : { padding: [60, 60] };
        lmap.flyToBounds(bb, Object.assign({ maxZoom: 16, duration: dur }, pad));
      }, 120);
    }
  }

  /* ---------- search ---------- */
  const q = $("q"), qx = $("qx");
  let qTimer = null, composing = false;
  function runSearch() {
    clearTimeout(qTimer);
    qTimer = later(() => {
      const nt = q.value.trim().toLowerCase().split(/[\s　,，、]+/).filter(Boolean);
      if (nt.join(" ") === tokens.join(" ")) return;
      if (nt.length) selected.length = 0;
      tokens = nt; update(true);
    }, 200);
  }
  const clearQuery = () => { q.value = ""; qx.hidden = true; runSearch(); };
  on(q, "focus", () => { if (isMobile()) { closeCard(); setSheet("full"); } });
  on(q, "compositionstart", () => { composing = true; });
  on(q, "compositionend", () => { composing = false; runSearch(); });
  on(q, "input", (e) => { qx.hidden = !q.value; if (composing || e.isComposing) return; runSearch(); });
  on(q, "keydown", (e) => { if (e.key === "Escape") clearQuery(); });
  on(qx, "click", () => { clearQuery(); q.focus(); });
  on($("clr"), "click", () => { selected.length = 0; q.value = ""; qx.hidden = true; tokens = []; update(true); });

  /* ---------- mobile sheet ---------- */
  const grab = $("grab"), rail = $("rail");
  let drag = null;
  on(grab, "pointerdown", (e) => { drag = { y: e.clientY, h: rail.offsetHeight, moved: false }; rail.dataset.dragging = ""; grab.setPointerCapture(e.pointerId); });
  on(grab, "pointermove", (e) => {
    if (!drag) return;
    const dy = drag.y - e.clientY; if (Math.abs(dy) > 4) drag.moved = true;
    rail.style.height = Math.max(90, Math.min(root.clientHeight, drag.h + dy)) + "px";
  });
  const endDrag = () => {
    if (!drag) return;
    delete rail.dataset.dragging;
    const r = rail.offsetHeight / root.clientHeight, moved = drag.moved; drag = null; rail.style.height = "";
    if (!moved) { setSheet(sheet === "peek" ? "half" : "peek"); return; }
    setSheet(r < 0.3 ? "peek" : r < 0.75 ? "half" : "full");
  };
  on(grab, "pointerup", endDrag); on(grab, "pointercancel", endDrag);
  on(grab, "click", (e) => { if (e.detail === 0) setSheet(sheet === "peek" ? "half" : "peek"); }); // keyboard
  lmap.on("click", () => { closeCard(); if (isMobile()) { q.blur(); setSheet("peek"); } });
  lmap.on("dragstart", () => { if (isMobile() && sheet !== "peek" && !("card" in root.dataset)) { q.blur(); setSheet("peek"); } });

  update(false);
  const ready = () => { if (!ac.signal.aborted) root.dataset.ready = ""; };
  tiles.once("load", ready); later(ready, 1500);

  return {
    element: root,
    map: lmap,
    destroy() {
      ac.abort();
      timers.forEach(clearTimeout); timers.clear();
      ro.disconnect();
      lmap.off(); lmap.remove();
      root.remove();
    }
  };
}

if (typeof window !== "undefined") window.mountWoooMap = window.mountWoooMap || mountWoooMap;
