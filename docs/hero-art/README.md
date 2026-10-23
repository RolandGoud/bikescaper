# Home hero art

The home page hero backgrounds (`webapp/static/hero/*.jpg`) and the bunch-of-bikes icon
(`webapp/static/hero/bikes.svg`) are drawn from code in this folder. No photos are used, so there
is nothing to license. `webapp/app.py` picks one background at random per visit from every `.jpg`
in that folder, so adding or removing a file is all it takes to change the set.

| Script | Draws |
|---|---|
| `bike.py` | Line-art racing bike with optional rider, used by everything else |
| `icons.py` | Icon variants, including `icon-g-bunch-bikes.svg` (the one in use) |
| `scenes.py` | First-round scenes and shared helpers (polder base, route map uses `topo.py`) |
| `scenes2.py` | Tulip fields, dike road, finish line, frame blueprint, wet road, heath path |
| `scenes3.py` | Reworked polder (windmill), alpine switchbacks, peloton sunset, dunes, velodrome |
| `topo.py` | Route map on contour lines (matplotlib) |
| `render.py` | Renders every `bg-*.svg` to 1920x1080 JPG with headless Chromium (Playwright) |

Run from this folder: `python scenes.py && python scenes2.py && python scenes3.py && python topo.py && python render.py`,
then copy the chosen files from `bg/` to `webapp/static/hero/`. `render.py` points at a Chromium
binary path; change `CH` to your own Playwright Chromium if needed.
