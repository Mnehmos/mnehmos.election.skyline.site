# 2026 Midterms in 3D — county results by population density

**▶ Live site: https://mnehmos.github.io/mnehmos.election.skyline.site/**

An interactive 3D map of unofficial 2026 midterm results: every covered county is extruded by population density
(or votes cast) and colored by the winner's margin in the Senate or Governor race.

| | |
|---|---|
| Live site | https://mnehmos.github.io/mnehmos.election.skyline.site/ |
| Merged results (JSON) | https://mnehmos.github.io/mnehmos.election.skyline.site/data/results.json |
| County shapes + data (JSON) | https://mnehmos.github.io/mnehmos.election.skyline.site/data/geo.json |
| Source | https://github.com/Mnehmos/mnehmos.election.skyline.site |

### Run locally
Open `index.html` in a browser (needs an internet connection: three.js and the Inter font load from CDNs).
Everything else, including all county shapes and results, is inside that one file.

### Deployment
Every push to `main` deploys `index.html` and `data/` to GitHub Pages via `.github/workflows/pages.yml`
(Settings → Pages → Source must be set to **GitHub Actions**). You can also run the workflow by hand from the Actions tab.

## What it shows
- **Height:** people per square mile (2024 Census estimate ÷ land area), or total votes cast. Linear, square-root or log scale.
- **Color:** the county winner's margin between the race's top two candidates statewide (blue D, red R, gold independent), saturating at 40 points.
- **Race:** U.S. Senate, Governor, or "Senate, else Governor".
- **Zoom → state:** singles the state out, rescales heights to it, and the *Explode counties* slider pulls its counties apart.
- **Photo mode** (button or `P`, `Esc` to exit): hides the controls and shows a caption with the race, statewide result, encoding and source.

## Data (unofficial, not certified)
Results are unofficial Nov 3, 2026 returns from each state's own election office, as of Nov 4–12, 2026.
Priority per state and race:
1. election.jamiecahn.com public API (open-source official-feed collector: github.com/jcahnProgramming/election-map)
2. pushbuild/us-2026-election-results snapshot of Nov 6 (CC0)
3. Collected directly: Montana Senate (electionresults.mt.gov), Hawaii governor (county summary PDFs, elections.hawaii.gov),
   Rhode Island towns summed to counties.

The full per-race source list is in the page under "Data & caveats" and in `data/results.json` (`races`).

Not covered (no county-level results reachable on Nov 12): NY, IL, WI, KY, TN, MS, OK, ME, NH, NV (sites block automated
access), MA and KS (not posted yet), WY (Google Drive only), MI and NJ (county clerks only), AK (reports by House district).

Population: Census Vintage 2024 county estimates (CT's old counties use 2020 estimates). Land area: 2024 Census Gazetteer.
Shapes: US Census boundaries via us-atlas `counties-10m.json`, Albers USA projection.

Small Virginia independent cities and Kalawao County, HI are merged into their surrounding county (the shapes either omit
them or they collapse to zero area at this scale); their votes and population are kept.

## Files
- `index.html` — the finished site.
- `data/results.json` — merged county results: `counties[fips].sen|gov = [top candidate A, B, others]`, plus `races` metadata (names, parties, statewide totals, source, timestamp).
- `data/geo.json` — projected county shapes joined with population, area and results (what's embedded in the page).
- `build/` — the pipeline:
  - `collect.py` merges the result sources into `results.json`
  - `join.py` adds Census population and land area
  - `project.mjs` projects/simplifies shapes, folds tiny cities, removes specks and self-crossings → `geo.json`
  - `template.html` is the page; the build replaces `__GEO__` with `geo.json`
  - `audit.mjs` checks every shape for slivers, self-crossings and bad triangulation

### Rebuild
```
cd build && npm install
python3 collect.py <api_json_dir> <pushbuild_data_dir> <mt_senate.json> <2024_Gaz_cousubs_national.txt> <2024_Gaz_counties_national.txt> results.json
python3 join.py - <census_dir> joined.json        # census_dir: co-est2024-alldata.csv, co-est2020-alldata.csv, 2024 + 2020 county Gazetteers
node project.mjs counties-10m.json joined.json geo.json
python3 -c "t=open('template.html').read(); g=open('geo.json').read().replace('</','<\\/'); open('../index.html','w').write(t.replace('__GEO__',g))"
node audit.mjs template.html
```
The raw inputs aren't bundled; their URLs are in the source list above and in the scripts.
