#!/usr/bin/env python3
"""Rebuild the Taiwan post-war architects map from the source maps.

Inputs  : sources/*.kml / *.kmz  (one file per Google My Maps map)
Rules   : scripts/config.json    (architect list + colours, aliases, merge pairs ...)
Template: scripts/template.html
Outputs : index.html, data/architects.json, data/buildings.json

Standard library only, so it runs on GitHub Actions without installing anything.
"""
import hashlib, html, io, json, math, os, re, sys, zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {'k': 'http://www.opengis.net/kml/2.2'}
CFG = json.load(open(os.path.join(ROOT, 'scripts', 'config.json'), encoding='utf-8'))
ARCH = [a['name'] for a in CFG['architects']]


def _oklch_hex(L, C, h):
    """OKLCH → sRGB hex; chroma is reduced until the colour fits the sRGB gamut."""
    for _ in range(40):
        a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
        l_, m_, s_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        rgb = [4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
               -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
               -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_]
        if all(-1e-4 <= v <= 1.0001 for v in rgb):
            break
        C *= 0.94
    enc = lambda v: 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return '#' + ''.join(f'{round(min(1, max(0, enc(min(1, max(0, v))))) * 255):02x}' for v in rgb)


def stroke_gradient(n):
    """Morandi palette following the layer order (surname stroke count).
    Hue walks once round the wheel; lightness repeats a fixed 5-step ramp,
    light → dark, so the rhythm is regular and neighbours stay distinguishable.
    Chroma stays low (dusty, greyed), slightly higher on the darker steps so
    they do not turn muddy on the black map."""
    ramp = [(0.86, 0.045), (0.79, 0.052), (0.72, 0.060), (0.65, 0.066), (0.58, 0.072)]
    out = []
    for i in range(n):
        L, C = ramp[i % len(ramp)]
        out.append(_oklch_hex(L, C, 20 + 320 * i / max(1, n - 1)))
    return out


COLORS = stroke_gradient(len(ARCH))
ALIASES = CFG['aliases']
BASE = CFG['base_map']
FUYI_BOTH = set(CFG['fuyi_both'])

# Source maps, by My Maps title, in the order the original merge used.
SOURCES = [
    '基泰工程司 feat. 高而潘',
    '傅義的白冷外方大雞雞',
    '大高雄戲院地圖®',
    '蓮之呼吸★改',
    '蓬萊異聞錄',
    '台博GIS',
]

# Maps whose folders are named after one architect and whose points update
# that architect's existing points (name + location win, all text is kept).
UPDATE_MAPS = {'台博GIS'}


def keys(a):
    return ALIASES.get(a, [a])


def read_kml(path):
    data = open(path, 'rb').read()
    if data[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = 'doc.kml' if 'doc.kml' in z.namelist() else [n for n in z.namelist() if n.endswith('.kml')][0]
            data = z.read(name)
    return ET.fromstring(data)


def doc_title(r):
    return (r.findtext('.//k:Document/k:name', namespaces=NS) or '').strip()


def count_pm(r):
    return len(r.findall('.//k:Placemark', NS))


def load_sources():
    """Static snapshots in sources/*.kmz, overridden by live downloads in sources/live/*.kml."""
    roots, manifest = {}, []
    sdir = os.path.join(ROOT, 'sources')
    for fn in sorted(os.listdir(sdir)):
        if fn.endswith(('.kmz', '.kml')):
            r = read_kml(os.path.join(sdir, fn))
            roots[doc_title(r)] = r
    ldir = os.path.join(sdir, 'live')
    if os.path.isdir(ldir):
        for fn in sorted(os.listdir(ldir)):
            if not fn.endswith('.kml'):
                continue
            try:
                r = read_kml(os.path.join(ldir, fn))
            except ET.ParseError:
                manifest.append({'file': fn, 'status': 'unreadable'}); continue
            title, n = doc_title(r), count_pm(r)
            if title not in SOURCES:
                manifest.append({'file': fn, 'title': title, 'placemarks': n, 'status': 'ignored: unknown map title'}); continue
            old = count_pm(roots[title]) if title in roots else 0
            if n < old * 0.8:
                manifest.append({'file': fn, 'title': title, 'placemarks': n, 'status': f'ignored: only {n} vs {old} points'}); continue
            roots[title] = r
            manifest.append({'file': fn, 'title': title, 'placemarks': n, 'status': 'live'})
    return roots, manifest


def load_points():
    roots, manifest = load_sources()
    pts = []
    for title in SOURCES:
        if title not in roots:
            continue
        r = roots[title]
        src = doc_title(r)
        for f in r.iterfind('.//k:Folder', NS):
            fname = f.findtext('k:name', namespaces=NS)
            for p in f.findall('k:Placemark', NS):
                ed = [(x.get('name'), (x.findtext('k:value', namespaces=NS) or '')) for x in p.iterfind('.//k:Data', NS)]
                coords = (p.findtext('.//k:coordinates', namespaces=NS) or '').strip()
                if not coords:
                    continue
                pts.append(dict(src=src, folder=fname, name=p.findtext('k:name', namespaces=NS) or '',
                                desc=p.findtext('k:description', namespaces=NS) or '', ed=ed, coords=coords))
    for i, p in enumerate(pts):
        p['i'] = i
    load_points.manifest = manifest
    return pts


def text(p):
    return p['name'] + '\n' + re.sub('<[^>]+>', '\n', p['desc']) + '\n' + '\n'.join(b for a, b in p['ed'] if a != 'gx_media_links')


def assign(p):
    s = p['src']
    A = set()
    if s == BASE['title'] and p['folder'] not in BASE['folders']:
        return A
    t = text(p)
    for a in ARCH:
        if any(k in t for k in keys(a)):
            A.add(a)
    if s.startswith('基泰'):
        if p['folder'] == '純基泰':
            A.add('基泰工程司')
        elif p['folder'].startswith('高而潘基泰'):
            A |= {'基泰工程司', '高而潘'}
        else:
            A.add('高而潘')
        if '並非高而潘' in t:
            A.discard('高而潘')
    elif s.startswith('傅義'):
        if '費宥諒' in t or '費有諒' in t:
            A.add('費宥諒')
            if p['name'] in FUYI_BOTH:
                A.add('傅義')
        else:
            A.add('傅義')
    elif s in UPDATE_MAPS:
        if p['folder'].strip() in ARCH:
            A.add(p['folder'].strip())
    elif s.startswith('蓮之'):
        A.add('王秀蓮')
        if '王水河FU' in t:
            A.discard('王水河')
    return A


def lonlat(p):
    return [float(x) for x in p['coords'].split(',')[:2]]


def dist(p, q):
    a, b = lonlat(p), lonlat(q)
    dx = (a[0] - b[0]) * math.cos(math.radians(a[1])) * 111320
    dy = (a[1] - b[1]) * 110540
    return math.hypot(dx, dy)


def plain(s):
    return re.sub(r'\s+', '', html.unescape(re.sub('<[^>]+>', '', s)))


def richness(p):
    return len(plain(p['desc'])) + len(p['name']) * 0.1


def clean(s):
    s = re.sub(r'<img[^>]*src="([^"]+)"[^>]*/?>', lambda m: f'<a href="{m.group(1)}">［原始圖片］</a>', s)
    s = re.sub(r'<(?!/?(br|a)\b)[^>]+>', '', s)
    # keep only safe http(s) hrefs on links, drop every other attribute
    def _a(m):
        h = re.search(r'href\s*=\s*"([^"]*)"', m.group(0))
        h = html.unescape(h.group(1)).strip() if h else ''
        return f'<a href="{html.escape(h, quote=True)}">' if re.match(r'https?://', h, re.I) else '<a>'
    s = re.sub(r'<a\b[^>]*>', _a, s)
    s = re.sub(r'<br\b[^>]*>', '<br>', s)
    s = re.sub(r'(?<!href=")(?<!">)(https?://[^\s<"]+)', r'<a href="\1">\1</a>', s)
    s = re.sub(r'(<br>\s*){3,}', '<br><br>', s)
    return s.strip()


def year(n):
    m = re.search(r'(18[5-9]\d|19\d\d|20[0-2]\d)', n)
    return int(m.group(1)) if m else None


STRIP = re.compile(r'(18[5-9]\d|19\d\d|20[0-2]\d)|\(.*?\)|（.*?）|新建工程|工程|設計圖|國立|台灣|臺灣|[\s　,，、()（）]')


def norm(n):
    return STRIP.sub('', n.replace('臺', '台'))


def same_place(u, item_pts):
    """Score how well update point u matches an existing item; None = no match."""
    nu, yu = norm(u['name']), year(u['name'])
    best = None
    for q in item_pts:
        d = dist(u, q)
        if [u['name'], q['name']] in CFG.get('update_pairs', []) and d < 800:
            return -1
        nq, yq = norm(q['name']), year(q['name'])
        named = len(nu) >= 2 and len(nq) >= 2 and (nu in nq or nq in nu)
        if named and d < 800:
            sc = d
        elif d < 150 and yu and yu == yq:
            sc = d + 200
        elif d < 25:
            sc = d + 400
        else:
            continue
        if best is None or sc < best:
            best = sc
    return best


def resolve_merges(pts):
    by = {}
    for p in pts:
        by.setdefault((p['src'], p['name']), []).append(p)
    pairs = []
    for sa, na, sb, nb in CFG['merge_pairs']:
        best = None
        for a in by.get((sa, na), []):
            for b in by.get((sb, nb), []):
                dd = dist(a, b)
                if dd < 500 and (best is None or dd < best[0]):
                    best = (dd, a['i'], b['i'])
        if best:
            pairs.append(best[1:])
    return pairs


def build():
    pts = load_points()
    group = {}
    for a, b in resolve_merges(pts):
        if a in group or b in group:
            continue
        group[a] = group[b] = (a, b)
    used, items = set(), []
    updates = []
    drop = {n.strip() for n in CFG.get('exclude', [])}
    for p in pts:
        A = assign(p)
        if p['name'].strip() in drop:
            continue
        if not A or p['i'] in used:
            continue
        if p['src'] in UPDATE_MAPS:
            updates.append((p, A))
            continue
        if p['i'] in group:
            a, b = group[p['i']]
            P, Q = pts[a], pts[b]
            prim, sec = (P, Q) if richness(P) >= richness(Q) else (Q, P)
            used |= {a, b}
            items.append((prim, [sec], assign(P) | assign(Q)))
        else:
            used.add(p['i'])
            items.append((p, [], A))

    # Update maps: match each point to an existing work of the same architect;
    # the update point becomes the primary (its name and location), old text is kept.
    taken, stats = set(), {}
    for u, A in updates:
        best = None
        for k, (prim, secs, IA) in enumerate(items):
            if k in taken or not (A & IA):
                continue
            sc = same_place(u, [prim] + secs)
            if sc is not None and (best is None or sc < best[0]):
                best = (sc, k)
        st = stats.setdefault(next(iter(A)), [0, 0])
        if best:
            k = best[1]
            prim, secs, IA = items[k]
            items[k] = (u, [prim] + secs, IA | A)
            taken.add(k)
            st[0] += 1
        else:
            items.append((u, [], A))
            taken.add(len(items) - 1)
            st[1] += 1
    build.stats = stats

    aidx = {a: i for i, a in enumerate(ARCH)}
    B = []
    for prim, secs, A in items:
        a = sorted(aidx[x] for x in A if x in aidx)
        if not a:
            continue
        lng, lat = lonlat(prim)
        parts = [prim['desc']] if prim['desc'].strip() else []
        src = [f"《{prim['src']}》／{prim['folder']}"]
        extra = []
        for q in secs:
            src.append(f"《{q['src']}》／{q['folder']}")
            pq = plain(q['desc'])
            if not pq or any(pq in plain(x) for x in parts + extra):
                continue
            # drop earlier text that this one already contains
            parts = [x for x in parts if plain(x) not in pq]
            extra = [x for x in extra if plain(x) not in pq]
            extra.append(q['desc'])
        d = clean('<br><br>'.join(parts + extra))
        # 王秀蓮's My Map sorts her works into building types (one folder each): show it first
        types = []
        for q in [prim] + secs:
            if q['src'].startswith('蓮之') and q['folder'].strip() and q['folder'].strip() not in types:
                types.append(q['folder'].strip())
        if types:
            d = '類型：' + '、'.join(types) + ('<br><br>' + d if d else '')
        name = prim['name'].strip().replace('\n', ' ')
        if year(name) is None:   # same place: keep the name that carries a year
            for q in secs:
                if year(q['name']) is not None:
                    name = q['name'].strip().replace('\n', ' ')
                    break
        alln = ' '.join([name] + [q['name'] for q in secs])
        t = (alln + ' ' + plain(html.unescape(re.sub('<[^>]+>', ' ', '<br>'.join([prim['desc']] + [q['desc'] for q in secs]))))).lower()
        B.append(dict(n=name, y=year(name), a=a, lat=round(lat, 6), lng=round(lng, 6), d=d, s=src, t=t))
    return {'arch': ARCH, 'b': B}


def _hash(*parts):
    h = hashlib.sha256()
    for b in parts:
        h.update(b)
    return h.hexdigest()[:10]


def write(D):
    """data/*.json (the data contract), dist/wooo-map/ (the mountable module) and the standalone index.html."""
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    arch = [{"id": i, "name": n, "color": COLORS[i], "count": sum(1 for b in D['b'] if i in b['a'])} for i, n in enumerate(ARCH)]
    bld = [{"id": i, "name": b['n'], "year": b['y'], "architects": b['a'], "lat": b['lat'], "lng": b['lng'],
            "description_html": b['d'], "sources": b['s']} for i, b in enumerate(D['b'])]
    arch_txt = json.dumps(arch, ensure_ascii=False, indent=1)
    bld_txt = json.dumps(bld, ensure_ascii=False, indent=1)
    open(os.path.join(ROOT, 'data', 'architects.json'), 'w', encoding='utf-8').write(arch_txt)
    open(os.path.join(ROOT, 'data', 'buildings.json'), 'w', encoding='utf-8').write(bld_txt)
    data_version = _hash(arch_txt.encode(), bld_txt.encode())

    # dist/wooo-map: the module + scoped CSS, copied verbatim from src/wooo-map
    src = os.path.join(ROOT, 'src', 'wooo-map')
    js = open(os.path.join(src, 'core.js'), 'rb').read()
    css = open(os.path.join(src, 'wooo-map.css'), 'rb').read()
    version = _hash(js, css)
    dist = os.path.join(ROOT, 'dist', 'wooo-map')
    os.makedirs(dist, exist_ok=True)
    banner = f"/* wooo-map {version} — generated from src/wooo-map by scripts/build_site.py; do not edit */\n".encode()
    open(os.path.join(dist, 'wooo-map.js'), 'wb').write(banner + js)
    open(os.path.join(dist, 'wooo-map.css'), 'wb').write(banner + css)
    manifest = {
        "name": "wooo-map",
        "version": version,
        "dataVersion": data_version,
        "entry": "wooo-map.js",
        "style": "wooo-map.css",
        "export": "mountWoooMap(container, { architectsUrl, buildingsUrl, data, initialView, mobileBreakpoint, L, leafletUrl }) -> { destroy(), map, element }",
        "leaflet": "1.9.4 (pass as option L, or it is loaded from cdnjs)",
        "data": {"architects": "data/architects.json", "buildings": "data/buildings.json",
                 "architectsCount": len(arch), "buildingsCount": len(bld)},
    }
    open(os.path.join(dist, 'manifest.json'), 'w', encoding='utf-8').write(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n')

    tpl = open(os.path.join(ROOT, 'scripts', 'template.html'), encoding='utf-8').read()
    out = tpl.replace('__VERSION__', version).replace('__DATAVERSION__', data_version)
    open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(out)
    sw = ''.join(f'<li><i style="background:{c}"></i>{html.escape(n)}<small>{c}</small></li>' for n, c in zip(ARCH, COLORS))
    open(os.path.join(ROOT, 'dist', 'palette.html'), 'w', encoding='utf-8').write(
        '<!DOCTYPE html><meta charset="utf-8"><meta name="robots" content="noindex"><title>architect palette</title>'
        '<style>body{margin:0;padding:24px;background:#000;color:#b4bebe;font:10pt "Source Code Pro","Microsoft JhengHei",monospace}'
        'ol{columns:5 170px;column-gap:24px;margin:0;padding:0;list-style:none}li{display:flex;align-items:center;gap:10px;height:28px;break-inside:avoid}'
        'i{width:18px;height:18px;flex:none}small{margin-left:auto;color:#7f8888;font-size:8pt}</style>'
        f'<ol>{sw}</ol>')
    for page in ('demo.html', 'widths.html'):
        sp = os.path.join(ROOT, 'scripts', page)
        if os.path.exists(sp):
            t = open(sp, encoding='utf-8').read().replace('__VERSION__', version).replace('__DATAVERSION__', data_version)
            open(os.path.join(ROOT, 'dist', page), 'w', encoding='utf-8').write(t)


if __name__ == '__main__':
    D = build()
    # Safety net: a broken download should never wipe the site.
    prev = os.path.join(ROOT, 'data', 'buildings.json')
    if os.path.exists(prev):
        n_prev = len(json.load(open(prev, encoding='utf-8')))
        if len(D['b']) < n_prev * 0.8:
            sys.exit(f'Refusing to publish: {len(D["b"])} buildings vs {n_prev} before (source download looks broken).')
    write(D)
    os.makedirs(os.path.join(ROOT, 'sources', 'live'), exist_ok=True)
    json.dump(getattr(load_points, 'manifest', []), open(os.path.join(ROOT, 'sources', 'live', 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"{len(D['b'])} buildings, {len(ARCH)} architects")
    for a, (m, n) in getattr(build, 'stats', {}).items():
        print(f"  update map / {a}: {m} matched existing, {n} new")
