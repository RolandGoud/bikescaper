"""Round 2: alternatives for the dropped backgrounds + reworks. All drawn from code."""
import math, random, sys
sys.path.insert(0, '.')
from bike import bike
from scenes import W, H, GRAIN, grain, lin, rad, ridge, wrap

def bikes(x, y, s, n, gap, color, sw, rng, jitter=0, rows=1, row_dy=0, row_dx=0):
    out = []
    for r in range(rows):
        for i in range(n):
            ox = x + i*gap + r*row_dx + rng.uniform(-jitter, jitter)
            oy = y - r*row_dy + rng.uniform(-jitter, jitter)*0.15
            out.append(f'<g stroke="{color}" stroke-width="{sw}">' + ''.join(bike(ox, oy, s*(1-0.06*r), crank=rng.uniform(0, 360))) + '</g>')
    return ''.join(reversed(out))

def clouds(id, y0, y1, freq='0.0022 0.009', seed=2, color='#ffffff', op=0.9, cover=0.55):
    """Fractal-noise clouds in a band, alpha thresholded so there are gaps of clear sky."""
    k = 3.2; off = -cover*k + 0.35
    f = (f'<filter id="{id}" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="6" seed="{seed}"/>'
         f'<feColorMatrix values="0 0 0 0 {int(color[1:3],16)/255:.2f}  0 0 0 0 {int(color[3:5],16)/255:.2f}  0 0 0 0 {int(color[5:7],16)/255:.2f}  {k} 0 0 0 {off:.2f}"/><feGaussianBlur stdDeviation="1.2"/></filter>'
         f'<linearGradient id="{id}m" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset=".6" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
         f'<mask id="{id}k"><rect y="{y0}" width="{W}" height="{y1-y0}" fill="url(#{id}m)"/></mask>')
    body = (f'<g mask="url(#{id}k)" opacity="{op}"><rect y="{y0}" width="{W}" height="{y1-y0}" filter="url(#{id})"/></g>'
)
    return f, body

def tex(id, freq, octs, seed, alpha, color='#000000'):
    r, g, b = int(color[1:3], 16)/255, int(color[3:5], 16)/255, int(color[5:7], 16)/255
    return (f'<filter id="{id}" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="{octs}" seed="{seed}"/>'
            f'<feColorMatrix values="0 0 0 0 {r:.2f}  0 0 0 0 {g:.2f}  0 0 0 0 {b:.2f}  {alpha} 0 0 0 {-alpha/2:.2f}"/><feComposite in2="SourceGraphic" operator="in"/></filter>')

def tinted_clouds(id, y0, y1, light, shade, **kw):
    """Two cloud passes: shaded underside, then a lighter, slightly smaller top shifted up, for some volume."""
    f1, b1 = clouds(id+'a', y0, y1, color=shade, **kw)
    kw2 = dict(kw); kw2['cover'] = kw.get('cover', 0.55) - 0.1
    f2, b2 = clouds(id+'b', y0, y1, color=light, **kw2)
    return f1 + f2, b1 + f'<g transform="translate(0,-10)">{b2}</g>'

# ---------------------------------------------------------------- alternatives
def tulips():
    rng = random.Random(31); hz = 500; vx = 1180
    cf, cb = tinted_clouds('tc', 0, 430, '#fbe3cf', '#b9a3b3', freq='0.0018 0.007', seed=5, cover=0.62)
    defs = lin('sky', [(0, '#3b5f8f'), (.6, '#9fb3c8'), (1, '#f3d2b4')]) + cf + rad('glow', [(0, '#fff0d8', .7), (1, '#fff0d8', 0)], .65, .95, .5)
    b = f'<rect width="{W}" height="{hz+2}" fill="url(#sky)"/>{cb}<rect width="{W}" height="{hz}" fill="url(#glow)"/>'
    # distant tree line and farm
    trees = ''.join(f'<ellipse cx="{x}" cy="{hz-rng.uniform(4, 18):.0f}" rx="{rng.uniform(8, 22):.0f}" ry="{rng.uniform(8, 20):.0f}"/>' for x in range(0, W, 14) if rng.random() < 0.55)
    b += f'<g fill="#4c5a52" opacity="0.85">{trees}</g><rect y="{hz-3}" width="{W}" height="6" fill="#55625a"/>'
    b += f'<path d="M560 {hz} v-36 l28 -22 l28 22 v36 Z M640 {hz} v-20 h60 v20 Z" fill="#46514b"/>'
    cols = ['#d8263a', '#f2c230', '#e85a8c', '#7b3fa0', '#f07a2a', '#f2a6c4', '#c8203a', '#f2c230']
    stripes = ''; xs = list(range(-4200, 6200, 300))
    for i in range(len(xs)-1):
        c = cols[i % len(cols)] if i % 3 != 2 else '#4f6b33'  # every third strip is a green path between beds
        stripes += f'<path d="M{vx} {hz} L{xs[i]} {H} L{xs[i+1]} {H} Z" fill="{c}"/>'
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#5a6b3c"/><g>{stripes}</g>'
    # flower heads, larger towards the viewer
    dots = ''
    for _ in range(5200):
        t = rng.random()**0.55; y = hz + 4 + (H-hz)*t
        xb = rng.uniform(-4200, 6200); x = vx + (xb-vx)*t
        i = int((xb+4200)//300)
        if i % 3 == 2: continue
        c = cols[i % len(cols)]; r = 0.6 + 7*t*t
        dots += f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{r:.1f}" ry="{r*1.25:.1f}" fill="{c}"/>'
    b += f'<g>{dots}</g>'
    defs += tex('soil', '0.02 0.4', 3, 8, 1.4)
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" filter="url(#soil)" opacity="0.35"/>'
    # haze toward the horizon and shading toward the viewer
    defs += lin('haze', [(0, '#e9d9c6'), (1, '#e9d9c6')]) + '<linearGradient id="hz2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#efe1cf" stop-opacity=".45"/><stop offset=".12" stop-color="#efe1cf" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></linearGradient>'
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="url(#hz2)"/>'
    # farm road on the right edge with a group of bikes
    b += f'<path d="M{vx+6} {hz} L{vx+14} {hz} L{W+900} {H} L{W+300} {H} Z" fill="#5c5852"/>'
    b += bikes(1310, hz+64, 0.045, 3, 60, '#1b1a1a', 4, rng, 6)
    return wrap(defs, b + grain(0.05))

def dike():
    rng = random.Random(41); hz = 560; vx = 760
    cf, cb = tinted_clouds('dc', 0, 520, '#ffd9b0', '#6d5a6e', freq='0.0016 0.006', seed=9, cover=0.5)
    defs = lin('sky', [(0, '#22324f'), (.55, '#8e7a8a'), (.85, '#f0a874'), (1, '#ffd29a')]) + cf + \
           rad('sun', [(0, '#fff2cc', 1), (.1, '#ffc27a', .7), (1, '#ff9a50', 0)]) + \
           lin('water', [(0, '#d99a72'), (.2, '#6f6478'), (1, '#1d2433')]) + tex('ripple', '0.002 0.09', 3, 3, 1.6, '#ffffff') + \
           lin('grass', [(0, '#5d6a3c'), (1, '#1d2414')]) + tex('gtex', '0.6 0.05', 2, 6, 2.0)
    b = f'<rect width="{W}" height="{hz}" fill="url(#sky)"/>{cb}<circle cx="560" cy="{hz-40}" r="520" fill="url(#sun)"/><circle cx="560" cy="{hz-28}" r="34" fill="#fff4d8"/>'
    # water on the left, mirroring the sky
    b += f'<path d="M0 {hz} L{vx} {hz} L-600 {H} Z" fill="url(#water)"/>'
    b += f'<path d="M0 {hz} L{vx} {hz} L-600 {H} Z" fill="#000" filter="url(#ripple)" opacity="0.5"/>'
    b += f'<path d="M500 {hz+2} L620 {hz+2} L560 {H} L180 {H} Z" fill="#ffd9a0" opacity="0.18"/>'
    # stone toe of the dike
    b += f'<path d="M{vx} {hz} L-600 {H} L-200 {H} L{vx+4} {hz} Z" fill="#4a4646"/>'
    # grass slope, road on top, inland slope
    b += f'<path d="M{vx+4} {hz} L-200 {H} L520 {H} L{vx+10} {hz} Z" fill="url(#grass)"/>'
    b += f'<path d="M{vx+10} {hz} L520 {H} L1500 {H} L{vx+28} {hz} Z" fill="#3a3a3d"/>'
    b += f'<path d="M{vx+10} {hz} L520 {H} L1500 {H} L{vx+28} {hz} Z" fill="#000" filter="url(#gtex)" opacity="0.25"/>'
    for i in range(22):
        t1, t2 = (i/22)**2.1, ((i+0.45)/22)**2.1
        y1, y2 = hz+(H-hz)*t1, hz+(H-hz)*t2
        x1, x2 = vx+19+(1010-vx-19)*t1, vx+19+(1010-vx-19)*t2
        b += f'<path d="M{x1:.0f} {y1:.0f} L{x2:.0f} {y2:.0f}" stroke="#e8e2d2" stroke-width="{1+t2*12:.1f}" opacity="0.75"/>'
    b += f'<path d="M{vx+28} {hz} L1500 {H} L{W} {H} L{W} {hz+30} Z" fill="url(#grass)"/>'
    b += f'<path d="M{vx+28} {hz} L1500 {H} L{W} {H} L{W} {hz+30} Z" fill="#000" filter="url(#gtex)" opacity="0.35"/>'
    # sheep-dotted far fields + fence posts along the road
    for i in range(1, 30):
        t = (i/30)**1.8; y = hz+(H-hz)*t; x = vx+28+(1500-vx-28)*t + 30*t
        b += f'<path d="M{x:.0f} {y:.0f} v{-(4+60*t):.0f}" stroke="#2a2a22" stroke-width="{1+5*t:.1f}"/>'
    b += bikes(800, hz+70, 0.04, 3, 52, '#141418', 3.5, rng, 5)
    return wrap(defs, b + grain(0.05))

def finish_line():
    rng = random.Random(51); hz = 520; vx = 960
    defs = lin('sky', [(0, '#3c6fa6'), (1, '#c9dcec')]) + tex('asph', '0.9', 3, 2, 1.8) + \
           lin('road', [(0, '#6c6b6a'), (1, '#2b2b2c')])
    cf, cb = tinted_clouds('fc', 0, 470, '#ffffff', '#b8c6d6', freq='0.002 0.008', seed=12, cover=0.45)
    defs += cf
    b = f'<rect width="{W}" height="{hz}" fill="url(#sky)"/>{cb}'
    # buildings of a finish town
    x = 0
    while x < W:
        w = rng.uniform(80, 200); h = rng.uniform(70, 200); c = rng.choice(['#8d7d6e', '#a58f78', '#6f6a66', '#9a8a7a'])
        b += f'<path d="M{x:.0f} {hz} v{-h:.0f} l{w/2:.0f} {-w*0.35:.0f} l{w/2:.0f} {w*0.35:.0f} v{h:.0f} Z" fill="{c}"/>'
        for wy in range(int(hz-h+16), hz-16, 34):
            for wx in range(int(x)+12, int(x+w)-20, 30):
                b += f'<rect x="{wx}" y="{wy}" width="12" height="18" fill="#3b3a3c" opacity="0.7"/>'
        x += w
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#4d5a3a"/>'
    b += f'<path d="M{vx-50} {hz} L{vx+50} {hz} L2700 {H} L-780 {H} Z" fill="url(#road)"/>'
    b += f'<path d="M{vx-50} {hz} L{vx+50} {hz} L2700 {H} L-780 {H} Z" fill="#000" filter="url(#asph)" opacity="0.3"/>'
    # crowd barriers with spectators, both sides
    for side in (-1, 1):
        for i in range(60):
            t = (i/60)**1.7; y = hz + (H-hz)*t
            x = vx + side*(50 + (1740-50)*t)
            h = 8 + 120*t
            b += f'<rect x="{x - (0 if side > 0 else 0):.0f}" y="{y-h:.0f}" width="{4+60*t:.0f}" height="{h*0.45:.0f}" fill="#d9dde2" stroke="#9aa0a8" stroke-width="{0.5+2*t:.1f}" transform="translate({-(4+60*t)/2 if side < 0 else 0:.0f},0)"/>'
            for k in range(2):
                hx = x + side*rng.uniform(4, 30)*(0.2+t); hy = y - h*0.45 - (8+60*t)*rng.uniform(0.6, 1.1)
                c = rng.choice(['#c0392b', '#f1c40f', '#ecf0f1', '#2c3e50', '#e67e22', '#2980b9'])
                b += f'<path d="M{hx:.0f} {hy:.0f} v{(8+60*t)*0.9:.0f}" stroke="{c}" stroke-width="{3+26*t:.0f}"/><circle cx="{hx:.0f}" cy="{hy-(3+22*t)*0.6:.0f}" r="{2+12*t:.1f}" fill="#d9b59a"/>'
    # checkered finish line across the road
    t = 0.3; yl = hz + (H-hz)*t; half = 50 + (1740-50)*t; sq = 2*half/40
    for i in range(40):
        for r in range(2):
            if (i + r) % 2 == 0:
                b += f'<rect x="{vx-half+i*sq:.0f}" y="{yl+r*14:.0f}" width="{sq:.0f}" height="14" fill="#f4f4f4"/>'
            else:
                b += f'<rect x="{vx-half+i*sq:.0f}" y="{yl+r*14:.0f}" width="{sq:.0f}" height="14" fill="#151515"/>'
    # finish gantry: posts and banner, no brands, just a chequered band
    gy = yl - 300
    b += f'<rect x="{vx-half-30:.0f}" y="{gy:.0f}" width="34" height="{yl-gy:.0f}" fill="#e7e7e7"/><rect x="{vx+half-4:.0f}" y="{gy:.0f}" width="34" height="{yl-gy:.0f}" fill="#e7e7e7"/>'
    b += f'<rect x="{vx-half-30:.0f}" y="{gy-110:.0f}" width="{2*half+64:.0f}" height="120" fill="#ff5a1f"/>'
    for i in range(int((2*half+64)//30)):
        b += f'<rect x="{vx-half-30+i*30:.0f}" y="{gy-110 + (0 if i % 2 else 15):.0f}" width="15" height="15" fill="#111"/><rect x="{vx-half-30+i*30+15:.0f}" y="{gy-110 + (15 if i % 2 else 0):.0f}" width="15" height="15" fill="#111"/>'
    b += f'<rect x="{vx-half-30:.0f}" y="{gy-110:.0f}" width="{2*half+64:.0f}" height="30" fill="none"/>'
    b += bikes(700, yl+330, 0.12, 3, 190, '#111', 7, rng, 20)
    return wrap(defs, b + grain(0.05))

def blueprint():
    defs = '<pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" stroke="#2a3d63" stroke-width="1"/></pattern>' \
           '<pattern id="G" width="200" height="200" patternUnits="userSpaceOnUse"><path d="M200 0H0V200" stroke="#35507f" stroke-width="1.6"/></pattern>' + \
           rad('vig', [(0, '#000', 0), (1, '#000', .55)], .5, .5, .75)
    b = f'<rect width="{W}" height="{H}" fill="#14213d"/><rect width="{W}" height="{H}" fill="url(#g)"/><rect width="{W}" height="{H}" fill="url(#G)"/>'
    s = 0.6; ox, oy = 980, 760
    P = lambda p: (ox + p[0]*s, oy - p[1]*s)
    b += f'<g stroke="#cfe0ff" stroke-width="3" opacity="0.9">' + ''.join(bike(ox, oy, s, crank=-40)) + '</g>'
    # dimension lines
    def dim(a, c, off, label, color='#8fb0e6'):
        (x1, y1), (x2, y2) = P(a), P(c)
        nx, ny = 0, off
        if abs(x2-x1) < 1: nx, ny = off, 0
        return (f'<path d="M{x1+nx:.0f} {y1+ny:.0f} L{x2+nx:.0f} {y2+ny:.0f}" stroke="{color}" stroke-width="2"/>'
                f'<path d="M{x1:.0f} {y1:.0f} L{x1+nx*1.15:.0f} {y1+ny*1.15:.0f} M{x2:.0f} {y2:.0f} L{x2+nx*1.15:.0f} {y2+ny*1.15:.0f}" stroke="{color}" stroke-width="1.2" stroke-dasharray="6 6"/>'
                f'<text x="{(x1+x2)/2+nx:.0f}" y="{(y1+y2)/2+ny-12:.0f}" fill="{color}" stroke="none" font-family="DejaVu Sans Mono, monospace" font-size="24" text-anchor="middle">{label}</text>')
    b += dim((0, 0), (989, 0), 300, 'WHEELBASE 989')
    b += dim((404, -70), (789, -70), 210, 'REACH 385')
    b += f'<path d="M{P((789,490))[0]+260:.0f} {P((789,490))[1]:.0f} V{P((404,-70))[1]:.0f}" stroke="#ff7a45" stroke-width="2.5"/>'
    b += f'<text x="{P((789,490))[0]+280:.0f}" y="{(P((789,490))[1]+P((404,-70))[1])/2:.0f}" fill="#ff7a45" font-family="DejaVu Sans Mono, monospace" font-size="24">STACK 560</text>'
    b += dim((256, 429), (789, 490), -60, 'TOP TUBE 540')
    x, y = P((404, -70))
    b += f'<path d="M{x-120:.0f} {y:.0f} A120 120 0 0 1 {x-34:.0f} {y-115:.0f}" stroke="#8fb0e6" stroke-width="2"/><text x="{x-200:.0f}" y="{y-60:.0f}" fill="#8fb0e6" font-family="DejaVu Sans Mono, monospace" font-size="24">73.5°</text>'
    x, y = P((833, 347))
    b += f'<text x="{x+40:.0f}" y="{y+10:.0f}" fill="#8fb0e6" font-family="DejaVu Sans Mono, monospace" font-size="24">HT 73°</text>'
    b += f'<g font-family="DejaVu Sans Mono, monospace" fill="#5f7fb5" font-size="20"><text x="1460" y="1010">ROAD · SIZE 56 · 700x28C</text><text x="1460" y="1040">SHEET 1/1 · SCALE 1:10</text></g>'
    b += f'<rect x="1440" y="980" width="440" height="72" stroke="#5f7fb5" stroke-width="1.5"/>'
    b += f'<rect width="{W}" height="{H}" fill="url(#vig)"/>'
    return wrap(defs, b + grain(0.04))

def wet_road():
    rng = random.Random(61); hz = 520; vx = 1000
    defs = lin('sky', [(0, '#1d2236'), (.5, '#5a3c52'), (.85, '#d06a45'), (1, '#f7b26a')]) + \
           lin('refl', [(0, '#f7b26a'), (.12, '#b45a48'), (.5, '#3c2c3e'), (1, '#121217')]) + tex('asph', '0.7 0.9', 3, 7, 2.2) + \
           tex('wet', '0.003 0.02', 4, 11, 3.2, '#000000') + '<filter id="blurv"><feGaussianBlur stdDeviation="2 10"/></filter>'
    cf, cb = tinted_clouds('wc', 0, 470, '#f2a07a', '#3a2c40', freq='0.0018 0.008', seed=21, cover=0.5)
    defs += cf
    sky = f'<rect width="{W}" height="{hz}" fill="url(#sky)"/>{cb}<circle cx="{vx+180}" cy="{hz-6}" r="26" fill="#ffe7b8"/>'
    trees = ''.join(f'<ellipse cx="{x}" cy="{hz-rng.uniform(4, 30):.0f}" rx="{rng.uniform(10, 26):.0f}" ry="{rng.uniform(10, 30):.0f}"/>' for x in range(0, W, 12) if rng.random() < 0.6 and abs(x-vx) > 60)
    sky += f'<g fill="#120f16">{trees}</g><rect y="{hz-4}" width="{W}" height="6" fill="#120f16"/>'
    sil = bikes(vx-120, hz+40, 0.06, 3, 80, '#0c0b10', 5, rng, 6)
    b = sky + sil + f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#1a181d"/>'
    # mirrored sky on the wet road, broken up by dry patches
    b += f'<g transform="translate(0,{2*hz}) scale(1,-1)" filter="url(#blurv)" opacity="0.55"><rect width="{W}" height="{hz}" fill="url(#sky)"/>{cb}{sil}<circle cx="{vx+180}" cy="{hz-6}" r="26" fill="#ffe7b8"/></g>'
    b += f'<path d="M0 {hz} H{W} V{H} H0 Z" fill="#141317" filter="url(#wet)"/>'
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#000" filter="url(#asph)" opacity="0.35"/>'
    b += f'<path d="M0 {hz} L{vx-200} {hz} L-2400 {H} L0 {H} Z" fill="#0f1012"/><path d="M{W} {hz} L{vx+200} {hz} L{W+2400} {H} L{W} {H} Z" fill="#0f1012"/>'
    for i in range(16):
        t1, t2 = (i/16)**2, ((i+0.45)/16)**2
        y1, y2 = hz+(H-hz)*t1, hz+(H-hz)*t2
        b += f'<path d="M{vx} {y1:.0f} L{vx} {y2:.0f}" stroke="#e9dcc4" stroke-width="{1+t2*14:.1f}" opacity="0.55"/>'
    b += f'<path d="M{vx-200} {hz} L-2400 {H}" stroke="#d8d0c0" stroke-width="5" opacity="0.4"/><path d="M{vx+200} {hz} L{W+2400} {H}" stroke="#d8d0c0" stroke-width="5" opacity="0.4"/>'
    return wrap(defs, b + grain(0.06))

def heath():
    rng = random.Random(71); hz = 540
    defs = lin('sky', [(0, '#7d9cc0'), (.7, '#d8dee0'), (1, '#f4e3c8')]) + tex('heather', '0.08 0.25', 4, 13, 2.4, '#ffffff') + \
           tex('sand', '0.8', 3, 5, 1.5) + lin('hz', [(0, '#efe4d4'), (1, '#efe4d4')]) + \
           '<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9e2d6" stop-opacity=".7"/><stop offset=".3" stop-color="#e9e2d6" stop-opacity="0"/></linearGradient>'
    cf, cb = tinted_clouds('hc', 0, 470, '#ffffff', '#b9c4d0', freq='0.0024 0.009', seed=31, cover=0.42)
    defs += cf
    b = f'<rect width="{W}" height="{hz}" fill="url(#sky)"/>{cb}'
    # pine tree line: trunks plus irregular crowns
    for layer, (col, base, hmin, hmax) in enumerate([('#617468', hz, 70, 120), ('#3a4a40', hz+6, 110, 200)]):
        x = rng.uniform(-40, 0)
        while x < W:
            if layer == 1 and rng.random() < 0.4: x += rng.uniform(100, 260); continue
            h = rng.uniform(hmin, hmax); lean = rng.uniform(-10, 10)
            top = (x + lean, base - h)
            b += f'<path d="M{x:.0f} {base} Q{x+lean*0.3:.0f} {base-h*0.5:.0f} {top[0]:.0f} {top[1]+h*0.12:.0f}" stroke="{col}" stroke-width="{1.5+layer*2.5}"/>'
            cw = h*rng.uniform(0.35, 0.55)
            for k in range(rng.randint(6, 11)):
                cx = top[0] + rng.uniform(-cw/2, cw/2); cy = top[1] + rng.uniform(-h*0.06, h*0.16)
                r = cw*rng.uniform(0.12, 0.24)
                b += f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{r*1.5:.0f}" ry="{r*0.8:.0f}" fill="{col}"/>'
            x += rng.uniform(22, 70)
    # heather: purple with fine noise, sunlit band in the middle distance
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#6a4a72"/>'
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#000" filter="url(#heather)" opacity="0.55"/>'
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#b07ac0" filter="url(#heather)" opacity="0.25"/>'
    for _ in range(900):
        t = rng.random()**0.6; y = hz + (H-hz)*t; x = rng.uniform(0, W); l = 3 + 26*t
        b += f'<path d="M{x:.0f} {y:.0f} l{rng.uniform(-l/3, l/3):.0f} {-l:.0f}" stroke="{rng.choice(["#3a2a40", "#8a5a9a", "#5a7040"])}" stroke-width="{0.5+2.5*t:.1f}"/>'
    # winding sandy path
    pts = [(1180, hz), (1120, 600), (1290, 700), (980, 840), (1250, H+40)]
    def side(off):
        return ' '.join(f'{x + off*(0.05 + (y-hz)/(H-hz))*1.0:.0f},{y}' for x, y in pts)
    L = [(x - 6 - 260*((y-hz)/(H-hz))**1.4, y) for x, y in pts]; R = [(x + 6 + 260*((y-hz)/(H-hz))**1.4, y) for x, y in pts]
    def smooth(seq):
        d = f'M{seq[0][0]:.0f} {seq[0][1]:.0f}'
        for i in range(1, len(seq)):
            (x0, y0), (x1, y1) = seq[i-1], seq[i]
            d += f' C{x0:.0f} {(y0+y1)/2:.0f} {x1:.0f} {(y0+y1)/2:.0f} {x1:.0f} {y1:.0f}'
        return d
    lp = smooth(L); rp = smooth(list(reversed(R)))
    d = lp + ' L' + rp[1:] + ' Z'
    b += f'<path d="{d}" fill="#d6c3a0"/><path d="{d}" fill="#000" filter="url(#sand)" opacity="0.25"/>'
    b += bikes(1110, 640, 0.035, 3, 40, '#2a2026', 3, rng, 4)
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="url(#fade)"/>'
    return wrap(defs, b + grain(0.05))

ALTS = [('11-tulip-fields', tulips), ('12-dike-road', dike), ('13-finish-line', finish_line), ('14-frame-blueprint', blueprint),
        ('15-wet-road', wet_road), ('16-heath-path', heath)]
if __name__ == '__main__':
    only = sys.argv[1:]
    for name, fn in ALTS:
        if only and not any(o in name for o in only): continue
        open(f'bg-{name}.svg', 'w').write(fn())
