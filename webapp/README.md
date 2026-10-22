# Bike Compare prototype

A first working version of the Bike Compare site: paste a second-hand bike ad and get a
check report on age, specs, size and value, matched against the road and gravel catalogue
that bikescaper collected from the brands' own sites: Trek and Canyon in July and August 2025,
Specialized, Giant, Cannondale, Cube and Factor in October 2026.

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
start the container downloads the latest `main` from GitHub, so restarting it is how you update.

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
| Listings | `/listings` | Every saved check, filterable by result. |
| Models | `/models`, `/models/<slug>` | The seeded catalogue with spec sheets. |
| Size finder | `/size` | Height to frame size per brand. |
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
Specialized, Giant, Cannondale, Cube and Factor come from `brand_scrapers/`, one adapter per
brand; refresh them with `python -m brand_scrapers` (or name brands: `python -m brand_scrapers
giant cube`). It writes a new snapshot to `data/<Brand>/` and one photo per model to
`images/<Brand>/`, and the seed picks the newest snapshot. On the NAS the catalogue reloads by
itself on the next start when a new snapshot is in `main`.

Only road, gravel, cyclocross and time trial bikes are collected, like the Trek and Canyon data.
Factor has no Dutch site, so its prices come from the EU store. Scott and Orbea are recognised in
ads and listed as coming next: their sites block requests from servers (Imperva and Cloudflare),
so they need a run from a home connection with a real browser. See `docs/scraper-plan.md`.

## Known limits

- Model years exist only for a few Trek generations, entered by hand.
- Size charts are generic per brand; geometry isn't collected.
- The value is a simple age and condition curve; comparable ads aren't used.
- Only the 2025 catalogue is covered, so older generations can't be matched yet.
