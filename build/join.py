"""Join 2026 county results (pushbuild CSVs) with Census population + land area.
Usage: python3 -I join.py <results_data_dir> <census_dir> <out.json>
"""
import csv, glob, json, os, re, sys, collections

res_dir, census_dir, out = sys.argv[1:4]

# ---------- Census ----------
pop = {}
names = {}  # fips -> (state_abbr, name)
for r in csv.DictReader(open(os.path.join(census_dir, 'co-est2024-alldata.csv'), encoding='latin-1')):
    if r['SUMLEV'] != '050':
        continue
    f = r['STATE'] + r['COUNTY']
    pop[f] = int(r['POPESTIMATE2024'])
area = {}
for r in csv.DictReader(open(os.path.join(census_dir, '2024_Gaz_counties_national.txt')), delimiter='\t'):
    r = {k.strip(): v.strip() for k, v in r.items()}
    area[r['GEOID']] = float(r['ALAND_SQMI'])
    names[r['GEOID']] = (r['USPS'], r['NAME'])


# Legacy geometry in us-atlas: Connecticut's 8 old counties (replaced by planning regions in
# Census 2022+) and Alaska's Valdez-Cordova (split in 2019 into 02063 + 02066).
for r in csv.DictReader(open(os.path.join(census_dir, 'co-est2020-alldata.csv'), encoding='latin-1')):
    if r['SUMLEV'] == '050' and r['STATE'] == '09':
        pop[r['STATE'] + r['COUNTY']] = int(r['POPESTIMATE2020'])
for r in csv.DictReader(open(os.path.join(census_dir, '2020_Gaz_counties_national.txt')), delimiter='\t'):
    r = {k.strip(): v.strip() for k, v in r.items()}
    if r['USPS'] == 'CT':
        area[r['GEOID']] = float(r['ALAND_SQMI'])
        names[r['GEOID']] = ('CT', r['NAME'])
pop['02261'] = pop.get('02063', 0) + pop.get('02066', 0)
area['02261'] = area.get('02063', 0) + area.get('02066', 0)
names['02261'] = ('AK', 'Valdez-Cordova Census Area (pre-2019)')
LEGACY_POP_NOTE = 'CT uses 2020 estimates for its pre-2022 counties'


def norm(n):
    n = n.lower().replace('&', 'and')
    n = re.sub(r'\bsaint\b|\bste?\.', lambda m: 'ste' if m.group(0).startswith('ste') else 'st', n)
    n = re.sub(r"[.'’\-]", '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    n = re.sub(r' (county|parish|borough|census area|city and borough|municipality)$', '', n)
    return n.replace(' ', '')


index = collections.defaultdict(dict)
for f, (st, nm) in names.items():
    index[st][norm(nm)] = f

# ---------- Results (merged by collect.py) ----------
R = json.load(open(os.path.join(os.path.dirname(os.path.abspath(out)), 'results.json')))
outd = {}
for f, (st, nm) in names.items():
    rec = {'n': nm, 's': st, 'p': pop.get(f), 'a': area.get(f)}
    rec.update(R['counties'].get(f, {}))
    outd[f] = rec
missing = set(R['counties']) - set(outd)
print('result fips without census record:', sorted(missing), file=sys.stderr)
json.dump({'counties': outd, 'races': R['races']}, open(out, 'w'), separators=(',', ':'))
