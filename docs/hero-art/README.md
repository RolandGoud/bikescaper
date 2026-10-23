# Home hero art

The home page hero backgrounds (`webapp/static/hero/*.jpg`) are ten openly licensed photos from
Wikimedia Commons, cropped to 1920x1080 (three of them also shifted or mirrored so the riders sit
on the left, behind the headline). `webapp/app.py` picks one at random per visit from every `.jpg`
in that folder and shows a credit line ("Photo: author · licence", linking to the source) at the
bottom right of the hero. Every photo needs an entry in `webapp/static/hero/credits.json`.

| Photo | Author | Licence | Change |
|---|---|---|---|
| [peloton-country-road.jpg](https://commons.wikimedia.org/wiki/File:P_is_for_Peloton_-_E_X_P_L_O_R_E_D_-_Flickr_-_Clint_Budd.jpg) | Clint Budd | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | cropped |
| [peloton-hedge-road.jpg](https://commons.wikimedia.org/wiki/File:Baugy_080_peloton-4.jpg) | Cjp24 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | cropped |
| [stelvio-hairpins.jpg](https://commons.wikimedia.org/wiki/File:Lombardia_Passo_dello_Stelvio_Ovest_31.jpg) | Zairon | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | cropped |
| [stelvio-panorama.jpg](https://commons.wikimedia.org/wiki/File:Passo_dello_Stelvio_(2.757_m).jpg) | Giorsch | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | cropped |
| [mtb-alpine-trail.jpg](https://commons.wikimedia.org/wiki/File:Mountain_Biking_In_Lenzerheide,_Switzerland_-_29591826245.jpg) | TRAILSOURCE.COM | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) | cropped |
| [small-group-country-road.jpg](https://commons.wikimedia.org/wiki/File:2017_Boels_Ladies_Tour_5e_etappe_019.jpg) | Hoebele | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | cropped |
| [small-group-valley.jpg](https://commons.wikimedia.org/wiki/File:8e_%C3%A9tape_Tour_de_France_Femmes_2025_-_D%C3%A9but_Madeleine_-_%C3%89chapp%C3%A9e_3.JPG) | Florian Pépellin | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | cropped |
| [amateur-group-dolomites.jpg](https://commons.wikimedia.org/wiki/File:Maratona_dles_Dolomites.jpg) | MPhernambucq | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) | mirrored, cropped |
| [bw-rider-cobbles.jpg](https://commons.wikimedia.org/wiki/File:Acht_van_Chaam,_wielrennen,_Bestanddeelnr_924-7505.jpg) | Rob Mieremet / Anefo | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | cropped |
| [lone-climb-ventoux.jpg](https://commons.wikimedia.org/wiki/File:Mt_Ventoux_cyclists.jpg) | FrogsLegs71 | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) | cropped |

The bunch-of-bikes icon (`webapp/static/hero/bikes.svg`) is drawn from code in this folder. The
scripts also still draw the earlier illustrated backgrounds, which are no longer used.

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
