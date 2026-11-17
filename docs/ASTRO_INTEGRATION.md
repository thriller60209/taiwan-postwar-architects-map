# Mounting the map in the atelier WooO Astro site (`/archive/map`)

Decided delivery: **copy** the module into the official repo, and serve the data from the
official site's own **server endpoint** behind the existing password session. No iframe,
no cross-origin requests from the browser, no CORS headers needed.

```txt
Google My Maps
  → this repo, hourly GitHub Action → data/architects.json, data/buildings.json
  → official site server endpoint (checks the map session cookie, fetches + caches the JSON)
  → /archive/map page → mountWoooMap(container, { architectsUrl, buildingsUrl })
```

My Maps edits still reach `/archive/map` automatically (≈1 hour + endpoint cache). Only the
module files are copied; they change when the map's behaviour or look changes, not when data does.

## 1. Files to copy (when `dist/wooo-map/manifest.json` → `version` changes)

From this repo:

```txt
dist/wooo-map/wooo-map.js    → src/vendor/wooo-map/wooo-map.js
dist/wooo-map/wooo-map.css   → src/vendor/wooo-map/wooo-map.css
dist/wooo-map/manifest.json  → src/vendor/wooo-map/manifest.json   (for reference)
```

Do not edit the copies; change `src/wooo-map/` in the map repo instead.

Leaflet: `npm i leaflet@1.9.4` in the official repo and pass it as `L` (otherwise the module
loads Leaflet 1.9.4 from cdnjs). The module's CSS already contains the scoped Leaflet core
rules, so do **not** import `leaflet/dist/leaflet.css`.

## 2. Data endpoint (server-side, protected)

`src/pages/archive/map/data/[file].ts` — sketch; reuse the site's existing session check
(the one `/archive/map` already uses) in place of `isMapSessionValid`.

```ts
import type { APIRoute } from "astro";
import { isMapSessionValid } from "../../../../lib/map-auth"; // existing helper

export const prerender = false;

const ALLOWED = new Set(["architects.json", "buildings.json"]);
const BASE = import.meta.env.MAP_DATA_BASE_URL
  ?? "https://raw.githubusercontent.com/thriller60209/taiwan-postwar-architects-map/main/data/";

export const GET: APIRoute = async ({ params, cookies }) => {
  if (!(await isMapSessionValid(cookies))) return new Response("unauthorized", { status: 401 });
  const file = params.file ?? "";
  if (!ALLOWED.has(file)) return new Response("not found", { status: 404 });

  const headers: Record<string, string> = {};
  // Later, if the map repo becomes private: a fine-grained read-only token in Vercel env.
  if (import.meta.env.MAP_DATA_TOKEN) headers.Authorization = `Bearer ${import.meta.env.MAP_DATA_TOKEN}`;

  const r = await fetch(BASE + file, { headers });
  if (!r.ok) return new Response("upstream error", { status: 502 });
  return new Response(await r.text(), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "private, max-age=300",   // per-user cache only; never public
      "X-Robots-Tag": "noindex"
    }
  });
};
```

Test: request `/archive/map/data/buildings.json` **without** the cookie → must be `401`.

## 3. The page

`src/pages/archive/map/index.astro` — inside the existing BaseLayout (which already draws the
header, footer, logo and crosshair). Replace the current "source module pending" block:

```astro
---
import BaseLayout from "../../../layouts/BaseLayout.astro";
import ArchiveViewSwitch from "../../../components/ArchiveViewSwitch.astro"; // the existing list / map switch
// existing auth redirect stays as it is
---
<BaseLayout title="post-war architects map / atelier WooO database">
  <!-- keep the robots noindex the page already sets (BaseLayout prop / head slot, whichever exists) -->
  <h1>archive</h1>
  <ArchiveViewSwitch />
  <div id="wooo-map-host" class="wooo-map-host"></div>
</BaseLayout>

<style>
  /* the host decides the size; the component fills it */
  .wooo-map-host { height: calc(100dvh - 220px); min-height: 420px; border-top: 1px solid var(--rule); }
  @media (max-width: 760px) { .wooo-map-host { height: calc(100dvh - 190px); margin: 0 -12px; } }
</style>

<script>
  import "../../../vendor/wooo-map/wooo-map.css";
  import L from "leaflet";
  import { mountWoooMap } from "../../../vendor/wooo-map/wooo-map.js";

  let map: { destroy(): void } | null = null;
  async function mount() {
    const host = document.getElementById("wooo-map-host");
    if (!host || map) return;
    map = await mountWoooMap(host, {
      L,
      architectsUrl: "/archive/map/data/architects.json",
      buildingsUrl: "/archive/map/data/buildings.json",
      initialView: "taiwan",
      mobileBreakpoint: 760
    });
  }
  mount();
  // If the site uses Astro view transitions:
  document.addEventListener("astro:page-load", mount);
  document.addEventListener("astro:before-swap", () => { map?.destroy(); map = null; });
</script>
```

Adjust the heights so the map fits under the official header/title/switch without page scroll;
the 220/190px values match `dist/demo.html`.

## 4. What the component does and does not do

- Renders only inside the container: search, layer list, map, building card, attribution.
- Adds **no** header, footer, logo, about/contact, fonts or cursor; sets no `html`/`body` styles or classes.
- All CSS is under `.wooo-map`. On fine pointers it sets `cursor: none` inside the map so the
  BaseLayout crosshair is the only cursor. Touch devices keep normal behaviour.
- Mobile layout switches on the **container** width (`mobileBreakpoint`, default 760):
  bottom sheet for search/layers, bottom card for details, 44px touch targets, no horizontal scroll.
- `description_html` is sanitized in the browser (text, `<br>`, `<a href="http(s)://…">` only).
- `prefers-reduced-motion: reduce` → no fly animations, no transitions.
- `destroy()` removes the Leaflet map, every listener, observers and timers, and its DOM.

## 5. Checklist on the official side

- [ ] `/archive/map/data/*.json` without cookie → 401
- [ ] `/archive/map` uses BaseLayout once (one header, footer, logo, crosshair)
- [ ] `noindex, nofollow` on `/archive/map`; route excluded from the sitemap
- [ ] 1280px / 1440px desktop, 320 / 375 / 390 / 430px mobile: no horizontal overflow
- [ ] NLSC attribution visible bottom-right
- [ ] `astro build` succeeds

Reference shell for all of the above: `dist/demo.html` (and `dist/widths.html` for phone widths)
in this repo, served at `https://atelier-wooo-map.vercel.app/dist/demo.html`.

## Data privacy note

While this repo, `atelier-wooo-map.vercel.app` and the My Maps stay public, the password
protects the official entrance, not the data itself. To make the data private later: make this
repo private, set `MAP_DATA_TOKEN` (read-only) in the official site's Vercel env, and stop
serving `data/` from the public map deployment. The sync workflow keeps working unchanged.
