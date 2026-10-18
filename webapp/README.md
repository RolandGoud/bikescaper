# Bike Compare prototype

A first working version of the Bike Compare site: paste a second-hand bike ad and get a
check report on age, specs, size and value, matched against the Trek and Canyon NL catalogue
that bikescaper collected in July and August 2025.

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r webapp/requirements.txt
python -m webapp.seed                 # loads data/Trek and data/Canyon into instance/bikecompare.sqlite3
flask --app webapp.app run --debug    # http://127.0.0.1:5000
python -m pytest tests                # tests
```

Set `BIKECOMPARE_DB` to use a different database file.

## Run it in Docker (e.g. on a UGREEN NAS)

```bash
docker compose up -d --build          # http://<host>:8085
```

On a UGREEN NAS (UGOS Pro): copy or clone this repo into a shared folder, open the Docker app,
go to Project > Create, point it at that folder so it picks up `docker-compose.yml`, and deploy.
Or SSH into the NAS, `cd` to the folder and run the command above.

The catalogue is loaded on first start. Saved checks live in the `bikecompare-data` volume, so
they survive restarts and rebuilds. To reload the catalogue after new scrapes:
`docker compose exec bikecompare python -m webapp.seed`. To change the port, edit `8085` in
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

Code: `webapp/checks.py` reads the seller's claims and runs the checks, `webapp/reference.py` holds
hand-entered reference data (brands, Trek generation years, generic size charts, groupsets),
`webapp/seed.py` loads the scraped JSON.

## Brands

Trek and Canyon have data. Specialized, Giant, Cannondale, Scott, Orbea, Cube and Factor are
recognised in ads and listed on the site as coming next; their scrapers are not written yet.
See `docs/scraper-plan.md`.

## Known limits

- Model years exist only for a few Trek generations, entered by hand.
- Size charts are generic per brand; geometry isn't collected.
- The value is a simple age and condition curve; comparable ads aren't used.
- Only the 2025 catalogue is covered, so older generations can't be matched yet.
