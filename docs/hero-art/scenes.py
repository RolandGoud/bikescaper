"""Ten generated hero backgrounds, 1920x1080. Everything is drawn from code: no photos."""
import math, random, sys
sys.path.insert(0, '.')
from bike import bike
W, H = 1920, 1080

GRAIN = '''<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3"/>
<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.9 0"/></filter>'''
def grain(op=0.06):
    return f'<rect width="{W}" height="{H}" filter="url(#grain)" opacity="{op}"/>'
def lin(id, stops, x2=0, y2=1):
    s = ''.join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return f'<linearGradient id="{id}" x1="0" y1="0" x2="{x2}" y2="{y2}">{s}</linearGradient>'
def rad(id, stops, cx=.5, cy=.5, r=.5):
    s = ''.join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
    return f'<radialGradient id="{id}" cx="{cx}" cy="{cy}" r="{r}">{s}</radialGradient>'
def ridge(rng, y0, amp, rough, n=9, ymax=H):
    """Midpoint-displacement ridgeline, returned as closed path down to ymax."""
    pts = [y0 + rng.uniform(-amp, amp), y0 + rng.uniform(-amp, amp)]
    a = amp
    for _ in range(n):
        new = []
        for i in range(len(pts)-1):
            new += [pts[i], (pts[i]+pts[i+1])/2 + rng.uniform(-a, a)]
        new.append(pts[-1]); pts = new; a *= rough
    step = W / (len(pts)-1)
    d = f'M0 {ymax} ' + ' '.join(f'L{i*step:.0f} {y:.1f}' for i, y in enumerate(pts)) + f' L{W} {ymax} Z'
    return d, pts
def riders(x, y, s, n, gap, color, sw, rng, jitter=0):
    out = []
    for i in range(n):
        ox = x + i*gap + rng.uniform(-jitter, jitter)
        out.append(f'<g stroke="{color}" stroke-width="{sw}">' + ''.join(bike(ox, y + rng.uniform(-jitter, jitter)*0.2, s, crank=rng.uniform(0, 360), rider=True)) + '</g>')
    return ''.join(out)
def wrap(defs, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" fill="none" '
            f'stroke-linecap="round" stroke-linejoin="round"><defs>{GRAIN}{defs}</defs>{body}</svg>')

def polder():
    rng = random.Random(1); hz = 640; vp = (1000, hz)
    defs = lin('sky', [(0, '#141a33'), (.55, '#5a2f48'), (.85, '#d7643a'), (1, '#f6a25a')]) + \
           lin('gnd', [(0, '#1d1a1e'), (1, '#0b0c0f')]) + rad('sun', [(0, '#ffd08a', 1), (.25, '#ff9a4a', .6), (1, '#ff7a3a', 0)])
    b = f'<rect width="{W}" height="{hz}" fill="url(#sky)"/><circle cx="1350" cy="{hz-10}" r="420" fill="url(#sun)"/>'
    b += f'<circle cx="1350" cy="{hz}" r="70" fill="#ffd9a0"/>'
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="url(#gnd)"/>'
    # ditches reflecting the sky
    for x in range(-3000, 5000, 260):
        b += f'<path d="M{vp[0]} {hz} L{x} {H}" stroke="#e07a48" stroke-width="2" opacity="0.25"/>'
    for i in range(1, 14):
        y = hz + (H-hz) * (i/14)**2.2
        b += f'<path d="M0 {y:.0f} H{W}" stroke="#000" stroke-width="{1+i*0.6:.1f}" opacity="0.25"/>'
    # road
    b += f'<path d="M{vp[0]-6} {hz} L{vp[0]+6} {hz} L1500 {H} L500 {H} Z" fill="#141518"/>'
    for i in range(18):
        t1, t2 = (i/18)**2, ((i+0.5)/18)**2
        y1, y2 = hz+(H-hz)*t1, hz+(H-hz)*t2
        b += f'<path d="M{vp[0]} {y1:.0f} L{vp[0]} {y2:.0f}" stroke="#d9c6a6" stroke-width="{1+t2*14:.1f}" opacity="0.7"/>'
    # tree line + farms on the horizon
    trees = ''
    for x in range(0, W, 9):
        if rng.random() < 0.5 and not (1250 < x < 1450):
            h = rng.uniform(6, 26); trees += f'<ellipse cx="{x}" cy="{hz-h/2}" rx="{rng.uniform(6, 14):.0f}" ry="{h/2+3:.0f}"/>'
    b += f'<g fill="#120f16">{trees}<rect x="0" y="{hz-4}" width="{W}" height="6"/></g>'
    # windmill
    wx, wy = 380, hz
    b += f'<g fill="#0e0c11"><path d="M{wx-40} {wy} L{wx-24} {wy-230} L{wx+24} {wy-230} L{wx+40} {wy} Z"/><path d="M{wx-30} {wy-228} Q{wx} {wy-275} {wx+30} {wy-228} Z"/>'
    for k in range(4):
        a = math.radians(20 + k*90)
        x2, y2 = wx + 230*math.cos(a), wy-245 + 230*math.sin(a)
        nx, ny = -math.sin(a)*22, math.cos(a)*22
        b += f'<path d="M{wx} {wy-245} L{x2:.0f} {y2:.0f}" stroke="#0e0c11" stroke-width="7"/>'
        b += f'<path d="M{wx+(x2-wx)*.25:.0f} {wy-245+(y2-wy+245)*.25:.0f} L{x2:.0f} {y2:.0f} L{x2+nx:.0f} {y2+ny:.0f} L{wx+(x2-wx)*.25+nx:.0f} {wy-245+(y2-wy+245)*.25+ny:.0f} Z" fill="none" stroke="#0e0c11" stroke-width="3"/>'
    b += '</g>'
    # small group of riders on the road
    b += riders(860, hz+92, 0.05, 3, 72, '#0a0a0c', 4, rng, 6)
    return wrap(defs, b + grain())

def alps():
    rng = random.Random(7)
    defs = lin('sky', [(0, '#0d1630'), (.6, '#2c4a73'), (1, '#9fb6c9')])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    cols = ['#6f86a0', '#4d6380', '#33455e', '#1f2b3d', '#121a26']
    defs_extra = lin('far', [(0, '#e8eef4'), (.08, '#c9d5e0'), (.16, '#6f86a0'), (1, '#6f86a0')])
    for i, c in enumerate(cols):
        d, pts = ridge(rng, 420 + i*115, 230 - i*35, 0.5 + i*0.03, n=8)
        b += f'<path d="{d}" fill="{'url(#far)' if i == 0 else c}"/>'
    # switchback road on the near slope
    d = 'M1560 1090'; y = 1090
    for k in range(4):
        x2 = 1260 if k % 2 == 0 else 1600; y2 = y - 52
        d += f' C{1600 if k % 2 == 0 else 1260} {y-6:.0f} {x2:.0f} {y2+20:.0f} {x2:.0f} {y2:.0f}' if False else f' S{x2+(60 if k % 2 == 0 else -60):.0f} {y2+26:.0f} {x2:.0f} {y2:.0f}'
        y = y2
    b += f'<path d="{d}" stroke="#8d98a6" stroke-width="7" opacity="0.6"/>'
    b += riders(1330, 893, 0.022, 4, 26, '#0b1018', 2.5, rng, 2)
    return wrap(defs + defs_extra, b + grain(0.05))

def cobbles():
    rng = random.Random(3); hz = 300
    defs = lin('sky', [(0, '#2a2622'), (1, '#8a7a66')]) + lin('fade', [(0, '#000', ), (1, '#000')]) + \
           rad('light', [(0, '#ffcf9a', .35), (1, '#ffcf9a', 0)], .7, .3, .6) + lin('haze', [(0, '#8a7a66'), (1, '#8a7a66')])
    b = f'<rect width="{W}" height="{H}" fill="#2a2420"/><rect width="{W}" height="{hz}" fill="url(#sky)"/>'
    # grass verges
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#26291d"/>'
    vx = 960; f = 260.0
    b += f'<clipPath id="road"><path d="M{vx-30} {hz+8} L{vx+30} {hz+8} L2500 {H} L-580 {H} Z"/></clipPath><g clip-path="url(#road)">'
    rows = []
    z = 1.0
    while z < 60:
        rows.append(z); z *= 1.11
    for i, z in enumerate(reversed(rows)):
        y = hz + f*4/z*3.2
        if y > H + 80: continue
        rh = f*4/z*3.2 - f*4/(z*1.11)*3.2
        half = 7000/z
        cw = 300/z
        x = vx - half - (i % 2)*cw/2
        while x < vx + half:
            w = cw*rng.uniform(0.8, 1.1)
            g = rng.randint(70, 125); col = f'rgb({g},{int(g*0.92)},{int(g*0.82)})'
            b += f'<rect x="{x+cw*0.06:.1f}" y="{y-rh+rh*0.08:.1f}" width="{w*0.88:.1f}" height="{rh*0.84:.1f}" rx="{min(w, rh)*0.3:.1f}" fill="{col}"/>'
            x += w
    b += '</g>'
    b += f'<rect width="{W}" height="{H}" fill="url(#light)"/>'
    return wrap(defs, b + grain(0.08))

def peloton_sunset():
    rng = random.Random(11); hz = 760
    defs = lin('sky', [(0, '#1a1030'), (.5, '#7a2c3e'), (.8, '#e8673a'), (1, '#ffb35c')]) + rad('sun', [(0, '#fff1c0', 1), (.15, '#ffc070', .8), (1, '#ff7a3a', 0)])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/><circle cx="960" cy="{hz}" r="600" fill="url(#sun)"/><circle cx="960" cy="{hz-30}" r="150" fill="#ffe2a8"/>'
    d, _ = ridge(rng, hz-40, 30, 0.5, ymax=H)
    b += f'<path d="{d}" fill="#3a1c2c" opacity="0.6"/>'
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#100a12"/>'
    b += riders(120, hz-6, 0.085, 14, 135, '#100a12', 7, rng, 30)
    b += riders(80, hz+4, 0.09, 13, 150, '#100a12', 7, rng, 30)
    return wrap(defs, b + grain(0.05))

def dunes():
    rng = random.Random(5); hz = 560
    defs = lin('sky', [(0, '#16233a'), (.7, '#7d8fa8'), (1, '#e6c3a0')]) + lin('sea', [(0, '#6c7f96'), (1, '#1d2a3a')])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/><rect y="{hz}" width="{W}" height="120" fill="url(#sea)"/>'
    for i in range(30):
        y = hz + 6 + i*4; b += f'<path d="M{rng.uniform(0, W):.0f} {y} h{rng.uniform(60, 300):.0f}" stroke="#d9e2ea" stroke-width="1.5" opacity="0.35"/>'
    cols = ['#5b5148', '#3e362f', '#29231f', '#18150f']
    for i, c in enumerate(cols):
        d, pts = ridge(rng, 650 + i*110, 70, 0.5, n=7)
        b += f'<path d="{d}" fill="{c}"/>'
        step = W/(len(pts)-1)
        if i >= 1:
            for j in range(0, len(pts), 2):
                x, y = j*step, pts[j]
                for k in range(3):
                    a = rng.uniform(-0.6, 0.6); l = rng.uniform(20, 46)*(i)
                    b += f'<path d="M{x+k*6:.0f} {y+4:.0f} q{l*a:.0f} {-l*0.5:.0f} {l*a*1.6:.0f} {-l:.0f}" stroke="{cols[min(i+1, 3)]}" stroke-width="{1+i}"/>'
    b += f'<path d="M1920 900 C1500 860 1300 800 900 760 S300 720 0 735" stroke="#8b8378" stroke-width="22" opacity="0.5"/>'
    b += riders(980, 765, 0.035, 3, 46, '#18150f', 3, rng, 4)
    return wrap(defs, b + grain(0.06))

def hills_mist():
    rng = random.Random(9)
    defs = lin('sky', [(0, '#203038'), (1, '#c7cfc3')]) + lin('mist', [(0, '#c7cfc3', ), (1, '#c7cfc3')])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    cols = ['#9aa89a', '#76887a', '#56695c', '#3a4c40', '#24322a', '#141d18']
    for i, c in enumerate(cols):
        base = 470 + i*100; amp = 40 + i*12
        ph = rng.uniform(0, 6); fr = rng.uniform(0.002, 0.004)
        pts = [(x, base - amp*math.sin(x*fr+ph) - amp*0.4*math.sin(x*fr*2.3+ph*2)) for x in range(0, W+20, 20)]
        d = f'M0 {H} ' + ' '.join(f'L{x} {y:.1f}' for x, y in pts) + f' L{W} {H} Z'
        b += f'<path d="{d}" fill="{c}"/>'
        if i == 3:
            road = 'M' + ' L'.join(f'{x} {y+18:.1f}' for x, y in pts[30:80])
            b += f'<path d="{road}" stroke="#c7cfc3" stroke-width="6" opacity="0.5"/>'
            mid = pts[52]
            b += riders(mid[0]-60, mid[1]+14, 0.028, 4, 30, '#24322a', 2.5, rng, 2)
    return wrap(defs, b + grain(0.05))

def city_night():
    rng = random.Random(13)
    defs = lin('sky', [(0, '#05070d'), (1, '#1b2338')]) + '<filter id="blur"><feGaussianBlur stdDeviation="14"/></filter><filter id="glow"><feGaussianBlur stdDeviation="4"/></filter>'
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    x = 0; bld = ''; win = ''
    while x < W:
        w = rng.uniform(70, 180); h = rng.uniform(180, 560)
        bld += f'<rect x="{x:.0f}" y="{700-h:.0f}" width="{w:.0f}" height="{h+400:.0f}"/>'
        for wy in range(int(700-h)+16, 690, 26):
            for wx in range(int(x)+10, int(x+w)-14, 22):
                if rng.random() < 0.22: win += f'<rect x="{wx}" y="{wy}" width="9" height="13" fill="{rng.choice(["#ffcf7a", "#ffe6b0", "#9fc4ff"])}" opacity="{rng.uniform(0.3, 0.9):.2f}"/>'
        x += w + rng.uniform(4, 20)
    b += f'<g fill="#0a0d16">{bld}</g>{win}'
    b += f'<rect y="700" width="{W}" height="380" fill="#07090f"/>'
    bok = ''
    for _ in range(70):
        c = rng.choice(['#ff8a3c', '#ffcf7a', '#ff4a3a', '#ffffff', '#7fb0ff'])
        bok += f'<circle cx="{rng.uniform(0, W):.0f}" cy="{rng.uniform(560, 900):.0f}" r="{rng.uniform(10, 46):.0f}" fill="{c}" opacity="{rng.uniform(0.15, 0.5):.2f}"/>'
    b += f'<g filter="url(#blur)">{bok}</g>'
    tr = ''
    for i in range(16):
        c = '#ff3d2e' if i % 2 else '#fff2d6'
        y0 = 780 + i*14
        tr += f'<path d="M-50 {y0+120} C600 {y0+40} 1300 {y0-80} 1980 {y0-200}" stroke="{c}" stroke-width="{rng.uniform(2, 5):.1f}" opacity="{rng.uniform(0.4, 0.9):.2f}"/>'
    b += f'<g filter="url(#glow)">{tr}</g>{tr}'
    return wrap(defs, b + grain(0.05))

def velodrome():
    rng = random.Random(17)
    defs = lin('wood', [(0, '#3b2a1c'), (.5, '#8a6440'), (1, '#2a1d12')]) + rad('spot', [(0, '#fff3dc', .35), (1, '#000', 0)], .6, .2, .7)
    b = f'<rect width="{W}" height="{H}" fill="#140f0b"/>'
    # banked curve: family of curves
    def curve(t):
        y0 = 120 + t*900
        return f'M-100 {y0+300*t:.0f} C500 {y0-200:.0f} 1300 {y0-260+t*120:.0f} 2050 {y0+100:.0f}'
    for i in range(140):
        t = i/140
        g = 70 + int(60*math.sin(t*9)+rng.uniform(0, 40))
        b += f'<path d="{curve(t)}" stroke="rgb({g+40},{g},{int(g*0.6)})" stroke-width="8" opacity="0.9"/>'
    for t, c, w in [(0.62, '#e8eef5', 10), (0.7, '#1d3f9a', 12), (0.78, '#c7202a', 10), (0.86, '#e8eef5', 10)]:
        b += f'<path d="{curve(t)}" stroke="{c}" stroke-width="{w}"/>'
    b += f'<path d="{curve(0.92)} L2050 1200 L-100 1200 Z" fill="#2b4a8c"/>'
    b += f'<rect width="{W}" height="{H}" fill="url(#spot)"/>'
    return wrap(defs, b + grain(0.07))

def forest():
    rng = random.Random(21); hz = 640
    defs = lin('sky', [(0, '#0d1712'), (.6, '#3c5a46'), (1, '#c9d6b0')]) + lin('ray', [(0, '#fff3c8'), (1, '#fff3c8')]) + \
           '<filter id="soft"><feGaussianBlur stdDeviation="18"/></filter>'
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    layers = [('#7d977c', 40, 10, 0.5), ('#56705a', 26, 22, 0.75), ('#34483a', 14, 44, 0.95), ('#121b15', 7, 110, 1)]
    for col, n, wmax, op in layers:
        for _ in range(n):
            x = rng.uniform(0, W); w = rng.uniform(wmax*0.5, wmax)
            if 820 < x < 1100 and wmax > 20: continue
            b += f'<rect x="{x:.0f}" y="0" width="{w:.0f}" height="{H}" fill="{col}" opacity="{op}"/>'
    rays = ''
    for k in range(6):
        x = 700 + k*120
        rays += f'<path d="M{x} -50 L{x+60} -50 L{x+460} {H} L{x+240} {H} Z" fill="#fff3c8" opacity="0.12"/>'
    b += f'<g filter="url(#soft)">{rays}</g>'
    b += f'<rect y="{hz-180}" width="{W}" height="260" fill="#c9d6b0" opacity="0.18" filter="url(#soft)"/>'
    b += f'<path d="M940 {hz} L980 {hz} L1500 {H} L420 {H} Z" fill="#2a332d"/><path d="M960 {hz} L960 {H}" stroke="#c9c2a0" stroke-width="5" stroke-dasharray="30 40" opacity="0.4"/>'
    b += f'<path d="M0 {H} L0 {hz+40} L940 {hz} L420 {H} Z" fill="#0f1712"/><path d="M{W} {H} L{W} {hz+40} L980 {hz} L1500 {H} Z" fill="#0f1712"/>'
    b += riders(900, hz+70, 0.045, 3, 40, '#0b110d', 3.5, rng, 5)
    return wrap(defs, b + grain(0.06))

SCENES = [('01-polder-dusk', polder), ('02-alpine-switchbacks', alps), ('03-cobbles', cobbles), ('04-peloton-sunset', peloton_sunset),
          ('05-dune-road', dunes), ('06-misty-hills', hills_mist), ('07-city-night', city_night), ('08-velodrome', velodrome),
          ('09-forest-road', forest)]
if __name__ == '__main__':
    for name, fn in SCENES:
        open(f'bg-{name}.svg', 'w').write(fn())
