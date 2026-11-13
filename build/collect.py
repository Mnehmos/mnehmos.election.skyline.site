"""Merge 2026 county results from every source into results.json.

Priority per (state, race): election-map API (newest official feeds) > pushbuild snapshot > hand-collected
official files (MT ResultsAjax, HI county PDFs, RI towns rolled up to counties).
Usage: python3 -I collect.py <api_dir> <pushbuild_data_dir> <mt_json> <cousub_gazetteer> <county_gazetteer> <out>
"""
import csv, glob, json, os, re, sys, collections

api_dir, pb_dir, mt_path, cousub_path, cty_path, out = sys.argv[1:7]
RACE = {'senate': 'sen', 'governor': 'gov'}

# county name index for pushbuild rows
def norm(n):
    n = n.lower().replace('&', 'and')
    n = re.sub(r'\bsaint\b|\bste?\.', lambda m: 'ste' if m.group(0).startswith('ste') else 'st', n)
    n = re.sub(r"[.'’\-]", '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    n = re.sub(r' (county|parish|borough|census area|city and borough|municipality)$', '', n)
    return n.replace(' ', '')

idx = collections.defaultdict(dict)
for r in csv.DictReader(open(cty_path), delimiter='\t'):
    r = {k.strip(): v.strip() for k, v in r.items()}
    idx[r['USPS']][norm(r['NAME'])] = r['GEOID']

# results[(st, race)] = {'src':..., 'asof':..., 'counties': {fips: {name: (party, votes)}}}
results = {}

def put(st, race, src, asof, counties):
    if counties and (st, race) not in results:
        results[(st, race)] = {'src': src, 'asof': asof, 'counties': counties}

def P(p):
    p = (p or '').upper().strip()
    if p.startswith('REP') or p in ('R', 'GOP'): return 'R'
    if p.startswith('DEM') or p in ('D', 'DFL') or p.startswith('DFL'): return 'D'
    return 'I'

# ---- 1. election-map API (official feeds, fetched today) ----
for f in sorted(glob.glob(os.path.join(api_dir, '*.json'))):
    st, race = os.path.basename(f)[:-5].split('-')
    d = json.load(open(f))
    if d.get('countyData') != 'available':
        continue
    sw = d['statewide']
    cs = {}
    for c in d['counties']:
        cs[c['fips']] = {x['name']: (P(x['party']), int(x['votes'] or 0)) for x in c['candidates']}
    put(st, RACE[race], f"{sw.get('sourceName') or sw.get('source')} via election.jamiecahn.com ({d['official']['office']})",
        (sw.get('fetchedAt') or '')[:16].replace('T', ' ') + ' UTC', cs)

# ---- 2. pushbuild snapshot (Nov 6) ----
SEN = re.compile(r'(\bu\.?\s*s\.?|united states|\bus)\s+senat|senator in congress', re.I)
GOV = re.compile(r'^(ks )?governor\b', re.I)
for path in sorted(glob.glob(os.path.join(pb_dir, '*.csv'))):
    st = os.path.basename(path)[:2].upper()
    if st in ('AK', 'CT', 'KS'):  # AK: districts, CT: towns (API has counties), KS: 2-county feed with inconsistent labels
        continue
    by = collections.defaultdict(lambda: collections.defaultdict(dict))
    asof, src = '', ''
    for r in csv.DictReader(open(path, encoding='utf-8')):
        if r['level'] != 'county':
            continue
        c = r['contest']; cl = c.lower()
        if 'state senat' in cl or 'wayne state' in cl or 'lieutenant governor' == cl.strip():
            continue
        race = 'sen' if SEN.search(c) else ('gov' if GOV.search(c) else None)
        if not race:
            continue
        name = r['county']
        if st == 'RI':
            fips = ('RI-TOWN', name)
        else:
            fips = idx[st].get(norm(name))
            if not fips:
                continue
        try: v = int(float(r['votes'] or 0))
        except ValueError: continue
        cand = r['candidate']
        prev = by[race][fips].get(cand, (P(r['party']), 0))
        by[race][fips][cand] = (prev[0], prev[1] + v)
        asof, src = r['fetchedAt'][:16].replace('T', ' ') + ' UTC', r['source']
    if st == 'RI':
        continue  # handled below
    for race, cs in by.items():
        put(st, race, f'{src} via pushbuild/us-2026-election-results', asof, dict(cs))

# ---- 3a. Rhode Island: towns -> counties via Census county subdivisions ----
town2fips = {}
for r in csv.DictReader(open(cousub_path), delimiter='\t'):
    r = {k.strip(): v.strip() for k, v in r.items()}
    if r['USPS'] == 'RI':
        town2fips[re.sub(r' (town|city)$', '', r['NAME']).lower()] = r['GEOID'][:5]
for race in ('sen', 'gov'):
    agg = collections.defaultdict(dict); asof = ''
    for r in csv.DictReader(open(os.path.join(pb_dir, 'ri.csv'), encoding='utf-8')):
        if r['level'] != 'county': continue
        c = r['contest']
        if (race == 'sen' and not SEN.search(c)) or (race == 'gov' and c.strip() != 'Governor'): continue
        f = town2fips.get(r['county'].lower())
        if not f: continue  # 'Federal' ballots have no town
        p, v = agg[f].get(r['candidate'], (P(r['party']), 0))
        agg[f][r['candidate']] = (p, v + int(float(r['votes'] or 0)))
        asof = r['fetchedAt'][:16].replace('T', ' ') + ' UTC'
    put('RI', race, 'Rhode Island Secretary of State (39 towns summed to counties) via pushbuild', asof, dict(agg))

# ---- 3b. Montana Senate (ResultsAjax GetMapData, esersws.mt.gov) ----
mt = json.load(open(mt_path))['d']
cs = collections.defaultdict(dict)
for x in mt:
    f = idx['MT'].get(norm(x['CountyName'].title()))
    if f: cs[f][x['calcCandidate'].title()] = (P(x['PartyCode']), int(x['calcCandidateVotes']))
put('MT', 'sen', 'Montana Secretary of State (electionresults.mt.gov)', '2026-11-12 22:33 UTC', dict(cs))

# ---- 3c. Hawaii governor (county summary PDFs, elections.hawaii.gov) ----
HI = {'15003': (179619, 69999), '15001': (45934, 15779), '15007': (17754, 6198), '15009': (36138, 13282)}
put('HI', 'gov', 'Hawaii Office of Elections county summary reports', '2026-11-12 22:33 UTC',
    {f: {'Josh Green': ('D', d), 'Gary Cordery': ('R', r)} for f, (d, r) in HI.items()})

# ---- normalise to two sides per state race ----
def clean(n):
    n = re.sub(r'\(.*?\)', '', n)
    n = re.sub(r'"[^"]*"', '', n).replace('"', '')
    n = re.split(r' / | and | And | AND |/', n)[0]
    if ',' in n and n.count(',') == 1 and n.split(',')[1].strip():
        last, first = n.split(','); n = first.strip() + ' ' + last.strip()
    n = re.sub(r'\s+', ' ', n).strip()
    return ' '.join(w.title() if w.isupper() and len(w) > 2 else w for w in n.split())

outc = collections.defaultdict(dict); meta = {}
for (st, race), rec in sorted(results.items()):
    tot = collections.Counter(); party = {}
    for cs in rec['counties'].values():
        for name, (p, v) in cs.items():
            if re.search(r'write|blank|over|under', name, re.I): continue
            tot[name] += v; party[name] = p
    rank = [n for n, _ in tot.most_common()]
    a, b = rank[0], rank[1]
    meta[f'{st}-{race}'] = {'src': rec['src'], 'asof': rec['asof'], 'A': clean(a), 'Ap': party[a], 'B': clean(b), 'Bp': party[b],
                            'Av': tot[a], 'Bv': tot[b], 'T': sum(tot.values())}
    for f, cs in rec['counties'].items():
        T = sum(v for n, (p, v) in cs.items() if not re.search(r'write|blank|over|under', n, re.I))
        A = cs.get(a, ('', 0))[1]; B = cs.get(b, ('', 0))[1]
        outc[f][race] = [A, B, T - A - B]
json.dump({'counties': outc, 'races': meta}, open(out, 'w'), separators=(',', ':'))
for k, m in meta.items():
    print(k.ljust(7), f"{m['A']} ({m['Ap']}) {m['Av']:,} vs {m['B']} ({m['Bp']}) {m['Bv']:,}", '|', m['asof'], '|', m['src'][:60])
print('counties with any result:', len(outc))
