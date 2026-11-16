#!/usr/bin/env python3
"""Rebuild the Taiwan post-war architects map from the source maps.

Inputs  : sources/*.kml / *.kmz  (one file per Google My Maps map)
Rules   : scripts/config.json    (architect list + colours, aliases, merge pairs ...)
Template: scripts/template.html
Outputs : index.html, data/architects.json, data/buildings.json

Standard library only, so it runs on GitHub Actions without installing anything.
"""
import html, io, json, math, os, re, sys, zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {'k': 'http://www.opengis.net/kml/2.2'}
CFG = json.load(open(os.path.join(ROOT, 'scripts', 'config.json'), encoding='utf-8'))
ARCH = [a['name'] for a in CFG['architects']]
COLORS = [a['color'] for a in CFG['architects']]
ALIASES = CFG['aliases']
BASE = CFG['base_map']
FUYI_BOTH = set(CFG['fuyi_both'])

# Source files, in the order the original merge used.
SOURCES = [
    '基泰工程司 feat. 高而潘.kmz',
    '傅義的白冷外方大雞雞.kmz',
    '大高雄戲院地圖®.kmz',
    '蓮之呼吸★改.kmz',
    '蓬萊異聞錄.kml',      # downloaded live from Google My Maps by the workflow
]


def keys(a):
    return ALIASES.get(a, [a])


def read_kml(path):
    data = open(path, 'rb').read()
    if data[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = 'doc.kml' if 'doc.kml' in z.namelist() else [n for n in z.namelist() if n.endswith('.kml')][0]
            data = z.read(name)
    return ET.fromstring(data)


def load_points():
    pts = []
    for fn in SOURCES:
        path = os.path.join(ROOT, 'sources', fn)
        if not os.path.exists(path) and fn.endswith('.kml'):
            path = path[:-4] + '.kmz'
        r = read_kml(path)
        src = r.findtext('.//k:Document/k:name', namespaces=NS)
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
    s = re.sub(r'(?<!href=")(?<!">)(https?://[^\s<"]+)', r'<a href="\1">\1</a>', s)
    s = re.sub(r'(<br>\s*){3,}', '<br><br>', s)
    return s.strip()


def year(n):
    m = re.search(r'(18[5-9]\d|19\d\d|20[0-2]\d)', n)
    return int(m.group(1)) if m else None


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
    for p in pts:
        A = assign(p)
        if not A or p['i'] in used:
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
            if plain(q['desc']) and plain(q['desc']) not in plain(prim['desc']):
                extra.append(q['desc'])
        d = clean('<br><br>'.join(parts + extra))
        name = prim['name'].strip().replace('\n', ' ')
        alln = ' '.join([name] + [q['name'] for q in secs])
        t = (alln + ' ' + plain(html.unescape(re.sub('<[^>]+>', ' ', '<br>'.join([prim['desc']] + [q['desc'] for q in secs]))))).lower()
        B.append(dict(n=name, y=year(name), a=a, lat=round(lat, 6), lng=round(lng, 6), d=d, s=src, t=t))
    return {'arch': ARCH, 'b': B}


def write(D):
    data = json.dumps(D, ensure_ascii=False, separators=(',', ':'))
    data = data.replace('</', '<\\/').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    tpl = open(os.path.join(ROOT, 'scripts', 'template.html'), encoding='utf-8').read()
    out = tpl.replace('__DATA__', data).replace('__COLORS__', json.dumps(COLORS))
    open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(out)
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    arch = [{"id": i, "name": n, "color": COLORS[i], "count": sum(1 for b in D['b'] if i in b['a'])} for i, n in enumerate(ARCH)]
    bld = [{"id": i, "name": b['n'], "year": b['y'], "architects": b['a'], "lat": b['lat'], "lng": b['lng'],
            "description_html": b['d'], "sources": b['s']} for i, b in enumerate(D['b'])]
    json.dump(arch, open(os.path.join(ROOT, 'data', 'architects.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(bld, open(os.path.join(ROOT, 'data', 'buildings.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    D = build()
    # Safety net: a broken download should never wipe the site.
    prev = os.path.join(ROOT, 'data', 'buildings.json')
    if os.path.exists(prev):
        n_prev = len(json.load(open(prev, encoding='utf-8')))
        if len(D['b']) < n_prev * 0.8:
            sys.exit(f'Refusing to publish: {len(D["b"])} buildings vs {n_prev} before (source download looks broken).')
    write(D)
    print(f"{len(D['b'])} buildings, {len(ARCH)} architects")
