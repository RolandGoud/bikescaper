import glob, os
from playwright.sync_api import sync_playwright
from PIL import Image
CH = '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CH); pg = b.new_page(viewport={'width': 1920, 'height': 1080})
    for f in sorted(glob.glob('bg-*.svg')):
        pg.goto('file://' + os.path.abspath(f)); pg.wait_for_timeout(200)
        pg.screenshot(path=f[:-4] + '.png')
    b.close()
os.makedirs('bg', exist_ok=True)
for f in sorted(glob.glob('bg-*.png')):
    Image.open(f).convert('RGB').save('bg/' + f[3:-4] + '.jpg', quality=82, optimize=True, progressive=True)
