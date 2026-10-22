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
| Specialized | https://www.specialized.com/nl/nl | To build |
| Giant | https://www.giant-bicycles.com/nl | To build |
| Cannondale | https://www.cannondale.com/nl-nl | To build |
| Scott | https://www.scott-sports.com/nl/nl/ | To build |
| Orbea | https://www.orbea.com/nl-nl/ | To build |
| Cube | https://www.cube.eu/nl-nl/ | To build |
| Factor | https://factorbikes.com/ | To build; no Dutch site known, prices may be in EUR via the EU store |

Before building each adapter: check the site's terms and robots.txt, and whether the brand
offers a dealer or product feed instead.

## Older model years

Brand archive pages where they exist, and Web Archive snapshots of the Dutch sites. Third-party
databases (99 Spokes, Geometry Geeks) only with a licence.

## Listings

Not crawled. Marktplaats's terms haven't been checked, so the prototype works on text the user
pastes.
