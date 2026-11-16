# 台灣戰後建築師地圖 · Taiwan Post-war Architects Map

A searchable map of 1,647 post-war buildings in Taiwan, grouped into 80 architect layers.
Part of **atelier WooO database** (https://project-7twdd.vercel.app/).

- Live (standalone): https://atelier-wooo-map.vercel.app
- Contact: atelierwooop@gmail.com · Instagram [@atelier_woo0](https://www.instagram.com/atelier_woo0/)

---

## Repository layout

```
index.html              ← GENERATED: the whole app in ONE file (HTML + CSS + JS + embedded data). Deployable as-is.
scripts/build_site.py   ← rebuilds index.html + data/ from sources/ (stdlib Python, no deps)
scripts/config.json     ← architects (order + colour), aliases, duplicate-merge pairs
scripts/template.html   ← page template (edit layout/style here)
sources/                ← source maps (蓬萊異聞錄 is refreshed from Google My Maps every hour)
.github/workflows/      ← hourly sync job
data/architects.json    ← 80 architect layers: { id, name, color, count }  (ordered by surname stroke count)
data/buildings.json     ← 1,647 buildings: { id, name, year, architects[], lat, lng, description_html, sources[] }
.vercelignore           ← keeps raw KMZ sources / helper scripts out of the deployment
```

`index.html` is self-contained on purpose: no build step, no bundler. The JSON files in `data/` hold
exactly the same data, split out so it can be imported into the main site.

## Features

- **Keyword search** (single input). Space-separated keywords are AND-matched against building name,
  architect names, year and description text. Example: `陳仁和 住宅`.
  A new search always covers all architects; ticking layers afterwards narrows the result.
- **Architect layers** (80, multi-select). Shown as `王大閎（96）`; the number is the count of mapped buildings.
  Selecting layers filters the map to those architects only. Each layer expands to its works,
  sorted by completion year (works without a year go last).
- **Info card** per point: year, name, all architects (click to add that layer), full original text,
  sources, coordinates, and an **"在 Google Maps 開啟 ↗"** link
  (`https://www.google.com/maps/search/?api=1&query=lat,lng`).
- Buildings designed by several architects appear in each of their layers; the marker takes the colour of
  the first selected architect.

## Tech

| Part | Choice |
|---|---|
| Map library | Leaflet 1.9.4 from cdnjs (`https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js`). Leaflet's core CSS is inlined. |
| Basemap | 內政部國土測繪中心 臺灣通用電子地圖（灰階） WMTS, no API key: `https://wmts.nlsc.gov.tw/wmts/EMAP01/default/GoogleMapsCompatible/{z}/{y}/{x}` — darkened with CSS `filter: grayscale(1) invert(1) brightness(.78) contrast(.95)` (class `.base-tiles`). Attribution required. |
| Fallback | If tiles cannot load (e.g. sandboxed previews), a simplified county outline is drawn instead. |
| Markers | `L.circleMarker` on a canvas renderer (1,600+ points stay fast). |
| Fonts | `"Source Code Pro", "Microsoft JhengHei", "Noto Sans TC", Arial, monospace` (Google Fonts: Source Code Pro 400/700, Noto Sans TC as CJK fallback for non-Windows). |

## Design tokens (already matched to project-7twdd)

The CSS uses the same variables as the main site's `:root`, so it should drop in without restyling:

```css
--silver:#b4bebe; --silver-light:#d0d8d8; --silver-dark:#737c7c; --black:#000; --white:#fff;
--silver-text:#b4bebe; --silver-title:#d0d8d8; --silver-muted:#7f8888; --rule:rgba(180,190,190,.5);
html { font-size:10pt; }   /* body 10pt, captions 10–12px, footer 10px */
```

Also copied from the main site: header grid (58px silver logo + two-line brand, lowercase nav, 1px rule),
`a:hover` underline, and the 2px crosshair cursor (`.index-cursor-x / -y`, `--cursor-x / --cursor-y`).

## Merging into the main site (notes for Codex)

Suggested route: a new page at **`/map`** in the Astro site, linked from the nav (`index · axis · archive · map · about`).

1. Create `src/pages/map.astro` using the site's existing layout/header (drop this file's own `<header>` and
   crosshair cursor — the site already has both).
2. Move the `<style>` block into the page (or a scoped stylesheet). Variables already match `:root`; remove the
   duplicated `:root`, `html`, `body`, `a` and cursor rules. Keep the Leaflet core CSS.
3. Load Leaflet (`<script src=…leaflet.min.js is:inline>`) and move the main `<script>` in as a client script.
   Replace the inline `const DATA = {...}` with an import of `data/architects.json` + `data/buildings.json`
   (copy them to `src/data/` or `public/data/`). Field mapping used by the script:
   `arch[i] = architects[i].name`, `COLORS[i] = architects[i].color`,
   building `{n:name, y:year, a:architects, lat, lng, d:description_html, s:sources, t:lowercase search text}`.
   `t` = name + plain-text description + architect names + year, all lower-case.
4. The map container needs a fixed height: currently `main` is `position:absolute; top:var(--head); bottom:0`.
   Inside the site layout use e.g. `height: calc(100svh - <header height>)`.
5. Mobile (< 760px): the sidebar becomes an off-canvas panel toggled by the `list` button (`body.side-open`).

## Data sources

Merged and de-duplicated from five Google My Maps KMZ files by the author:
〈蓬萊異聞錄〉（only the 戰後建築／宗教建築／戲院 layers）、〈基泰工程司 feat. 高而潘〉、〈傅義的白冷外方〉、〈大高雄戲院地圖®〉、〈蓮之呼吸★改〉.

- Points were assigned to an architect when the architect's name (or an alias / known typo) appears in the
  point's text; files dedicated to one architect (基泰／高而潘, 傅義／費宥諒, 王秀蓮) were assigned by file.
- Aliases merged: 林建業 → 基泰工程司; 登琨艷、漢寅德 → 漢寶德; 王文芳 → 王水河; 顧授書、彭蔭宣 → 中國興業; 吳文熹 → 陳鍊鋒.
- 75 cross-file duplicates were merged, keeping the richer record and appending the other's text.
- Year = first 4-digit year in the point name.

## Updating

**Data — automatic.** `.github/workflows/sync-mymaps.yml` runs every hour (and on demand from the Actions tab →
"Sync from Google My Maps" → Run workflow). It downloads the live 蓬萊異聞錄 My Map
(`mid=1YdXsuuZrWFRGo5Qb1JtVM8GOE7hDbYOg`) as KML, runs `scripts/build_site.py`, and commits `index.html` + `data/`
if anything changed; Vercel then redeploys. The other four sources are static files in `sources/`.

**Rules** (architect list/colours/order, aliases, duplicate pairs) live in `scripts/config.json`.
**Layout / style** lives in `scripts/template.html` — edit that, not `index.html`, which is generated.
The build refuses to publish if the building count drops by more than 20 % (protects against a broken download).
