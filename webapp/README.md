# Bike Compare prototype

A first working version of the Bike Compare site: paste a second-hand bike ad and get a
check report on age, specs, size and value, matched against the road and gravel catalogue
that bikescaper collected from the brands' own sites: Trek and Canyon in July and August 2025,
Specialized, Giant, Cannondale, Cube, Factor, Scott and Orbea in October 2026.

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r webapp/requirements.txt
python -m webapp.seed                 # loads data/<Brand>/ into instance/bikecompare.sqlite3
flask --app webapp.app run --debug    # http://127.0.0.1:5000
python -m pytest tests                # tests
```

Set `BIKECOMPARE_DB` to use a different database file.

## Run it in Docker (e.g. on a UGREEN NAS)

```bash
docker compose up -d --build          # http://<host>:8280
```

**On a UGREEN NAS (UGOS Pro), easiest:** open the Docker app, go to Project > Create, paste the
contents of `nas/docker-compose.yml` and deploy. That file needs nothing next to it: on every
start the container downloads the latest `main` from GitHub, and while it runs it checks every 10
minutes for a new commit and switches to it without stopping the site (`nas/autoupdate.py`; set
`UPDATE_MINUTES` to change how often, `"0"` turns it off). A commit that fails to start is skipped.

The root `docker-compose.yml` instead builds from a full copy of this repo, so the whole repo
folder has to be on the NAS (Project > Create pointed at that folder, or
`docker compose up -d --build` over SSH).

The catalogue is loaded on first start; later starts only re-pick the model photos. Saved checks live in the `bikecompare-data` volume, so
they survive restarts and rebuilds. To reload the catalogue after new scrapes:
`docker compose exec bikecompare python -m webapp.seed`. To change the port, edit `8280` in
`docker-compose.yml`. The image is about 500 MB because it includes the bike photos.

## What's in it

| Page | Path | Notes |
|---|---|---|
| Home / check a listing | `/` | Paste the ad's title and text, asking price, place and your height. The ad itself is never fetched. |
| Check report | `/check/<id>` | Model match (with "change match"), age, spec comparison, size fit, value estimate, questions for the seller. |
| Selling | `/sell` | For sellers: paste a draft ad (or its link), answer what's missing, and get a new title, description and asking price, plus the verdicts a buyer's check will show. Drafts are never saved. |
| Photo review (not built) | `/sell/photo-review/interest` | The Selling page offers a paid photo review (€5 for 10 photos) that doesn't exist yet, to measure interest. Clicks and emails go in `photo_review_interest`; this unlinked page shows the counts. |
| Listings | `/listings` | Every saved check, filterable by result. |
| Models | `/models`, `/models/<slug>` | The seeded catalogue with spec sheets. |
| Size finder | `/size` | Height to frame size per model line (builds sharing a frame are grouped), from `webapp/size_charts.json`; brand chart when a model has none. |
| Value estimator | `/value` | Fair price from new price, model year and condition. |
| How it works | `/how-it-works` | Method, data sources and limits. |

The site is in Dutch and English. It follows the browser's language (Dutch when unsure), and the
NL/EN switch in the header changes it and remembers the choice in a cookie. Texts live in
`webapp/i18n.py`: English is the key, with the Dutch translation next to it.

Code: `webapp/checks.py` reads the seller's claims and runs the checks, `webapp/reference.py` holds
hand-entered reference data (brands, Trek generation years, generic size charts, groupsets),
`webapp/seed.py` loads the scraped JSON.

## Brands

Trek and Canyon come from their own scrapers (`trek_bikes_scraper.py`, `canyon_bikes_scraper.py`).
Specialized, Giant, Cannondale, Cube, Factor, Scott and Orbea come from `brand_scrapers/`, one adapter per
brand; refresh them with `python -m brand_scrapers` (or name brands: `python -m brand_scrapers
giant cube`). It writes a new snapshot to `data/<Brand>/` and one photo per model and one per
colour to `images/<Brand>/`, and the seed picks the newest snapshot. `python -m
brand_scrapers.colour_photos` adds the colour photos to the newest snapshots without collecting
the rest again (Scott from `data/Scott/scott_gallery.json`; Orbea only from a home PC). On the NAS the catalogue reloads by
itself on the next start when a new snapshot is in `main`.

Only road, gravel, cyclocross and time trial bikes are collected, like the Trek and Canyon data.
Factor has no Dutch site, so its prices come from the EU store. Scott and Orbea block requests
from servers and headless browsers (Imperva and Cloudflare), so `brand_scrapers/browser.py` opens a
visible Chrome window through Playwright: run `python -m brand_scrapers scott orbea` on a home PC
with `pip install playwright`. Their rider heights come from the brands' general size guides.
See `docs/scraper-plan.md`.

## Known limits

- Model years exist only for a few Trek generations, entered by hand.
- The spec sheet has a tab per year from 2020. Earlier years come from `data/years/<Brand>.json`
  (spec sheets read from Wayback Machine copies of the brand's NL site); a brand without that file
  shows only the year of our own scrape, and the other tabs say the archive wasn't searched yet.
- The catalogue photo on a check shows the colour the ad names (title, a "kleur:" line, or "zwarte racefiets"), matched to the brand's colour names (`webapp/colour_match.py`); without a colour in the text it shows the model's first colour. Trek's colours aren't collected per model, and Orbea's colour photos wait for a run from a home PC.
- The age check also estimates the model year from the ad's details: groupset generation, a named frame generation, rim brakes and a named colourway we have a dated photo of (`GROUPSET_YEARS` in `webapp/reference.py`). The ad's photos aren't read: without a vision model their colours are mostly the background.
- Rider heights per model come from Trek, Canyon and Cannondale; Specialized, Giant, Cube and Factor only publish sizes and geometry per model, so their heights come from the brand size guide. Refresh with `python -m brand_scrapers.sizing`.
- The value is a simple age and condition curve; comparable ads aren't used.
- Only the 2025 catalogue is covered, so older generations can't be matched yet.
