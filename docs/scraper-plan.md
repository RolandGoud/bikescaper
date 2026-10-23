# Scraper plan

The site reads only from its database; scrapers fill it. This replaces the CSV/Excel/WordPress
exports with one catalogue collector that has an adapter per brand.

## Per brand

Each adapter reads the brand's own Dutch site, prefers the product JSON the page embeds over
HTML parsing, and stores per model year: model, variant (colour, SKU), spec lines, sizes with
rider heights and geometry, and the price with the date it was seen. Snapshots are kept, never
overwritten, so the catalogue builds history over time.

| Brand | Dutch site (starting point, not yet verified) | Status |
|---|---|---|
| Trek | https://www.trekbikes.com/nl/nl_NL/ | Scraper exists (`trek_bikes_scraper.py`); add model year, sizes, geometry |
| Canyon | https://www.canyon.com/nl-nl/ | Scraper exists (`canyon_bikes_scraper.py`); add model year, sizes, geometry |
| Specialized | https://www.specialized.com/nl/nl | Built (`brand_scrapers/specialized.py`): Next.js product data |
| Giant | https://www.giant-bicycles.com/nl | Built (`brand_scrapers/giant.py`): NL sitemap, model years 2025+, 4 s crawl delay |
| Cannondale | https://www.cannondale.com/nl-nl | Built (`brand_scrapers/cannondale.py`): sitemap + schema.org product JSON |
| Scott | https://www.scott-sports.com/nl/en/ | Built (`brand_scrapers/scott.py`): /nl/en/ sitemap and JSON-LD, fetched with a visible Chrome window from a home PC (Imperva blocks servers and headless browsers) |
| Orbea | https://www.orbea.com/nl-nl/ | Built (`brand_scrapers/orbea.py`): family pages and embedded product data, fetched with a visible Chrome window from a home PC (Cloudflare blocks servers and headless browsers) |
| Cube | https://www.cube.eu/nl-nl/ | Built (`brand_scrapers/cube.py`): family pages, one product per colour |
| Factor | https://eu.factorbikes.com/ | Built (`brand_scrapers/factor.py`): EU store (eu.factorbikes.com), euro prices |

Before building each adapter: check the site's terms and robots.txt, and whether the brand
offers a dealer or product feed instead.

## Older model years

Brand archive pages where they exist, and Web Archive snapshots of the Dutch sites. Third-party
databases (99 Spokes, Geometry Geeks) only with a licence.

## Listings

Not crawled. Marktplaats's terms haven't been checked, so the prototype works on text the user
pastes.
