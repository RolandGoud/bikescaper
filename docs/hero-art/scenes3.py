"""Round 2 reworks of 01, 02, 04, 05, 08."""
import math, random, sys
sys.path.insert(0, '.')
import scenes
from scenes import W, H, grain, lin, rad, ridge, wrap
from scenes2 import bikes, tinted_clouds, tex

def windmill(x, base, h, ang, col):
    """Dutch smock mill: tapered octagonal body, stage with railing, cap, four lattice sails."""
    bw, tw = h*0.36, h*0.17; sh = base - h*0.36; top = base - h
    o = f'<g fill="{col}" stroke="{col}">'
    o += f'<path d="M{x-bw/2:.0f} {base} L{x-tw/2:.0f} {top:.0f} L{x+tw/2:.0f} {top:.0f} L{x+bw/2:.0f} {base} Z" stroke="none"/>'
    o += f'<rect x="{x-bw*0.62:.0f}" y="{sh-4:.0f}" width="{bw*1.24:.0f}" height="8" stroke="none"/>'
    for k in range(13):
        px = x - bw*0.62 + k*bw*1.24/12
        o += f'<path d="M{px:.0f} {sh:.0f} v{-h*0.05:.0f}" stroke-width="2"/>'
    o += f'<path d="M{x-bw*0.62:.0f} {sh-h*0.05:.0f} h{bw*1.24:.0f}" stroke-width="3"/>'
    o += f'<path d="M{x-bw*0.62:.0f} {sh:.0f} L{x-bw*0.45:.0f} {base:.0f} M{x+bw*0.62:.0f} {sh:.0f} L{x+bw*0.45:.0f} {base:.0f}" stroke-width="3"/>'
    o += f'<rect x="{x-bw*0.1:.0f}" y="{base-h*0.12:.0f}" width="{bw*0.2:.0f}" height="{h*0.12:.0f}" fill="#000" opacity=".25" stroke="none"/>'
    cy = top - h*0.03
    o += f'<path d="M{x-tw*0.75:.0f} {top+2:.0f} Q{x-tw*0.6:.0f} {top-h*0.11:.0f} {x+tw*0.15:.0f} {top-h*0.11:.0f} Q{x+tw*0.75:.0f} {top-h*0.08:.0f} {x+tw*0.8:.0f} {top+2:.0f} Z" stroke="none"/>'
    hub = (x + tw*0.55, cy)
    L = h*0.95
    for k in range(4):
        a = math.radians(ang + k*90)
        ux, uy = math.cos(a), math.sin(a); nx, ny = -uy, ux
        ex, ey = hub[0] + ux*L, hub[1] + uy*L
        o += f'<path d="M{hub[0]:.0f} {hub[1]:.0f} L{ex:.0f} {ey:.0f}" stroke-width="{h*0.022:.1f}"/>'
        wdt = L*0.2; s0 = 0.18
        p = lambda t, w: (hub[0] + ux*L*t + nx*w, hub[1] + uy*L*t + ny*w)
        a1, a2, a3, a4 = p(s0, 0), p(1, 0), p(1, wdt), p(s0, wdt*0.8)
        o += f'<path d="M{a1[0]:.0f} {a1[1]:.0f} L{a4[0]:.0f} {a4[1]:.0f} L{a3[0]:.0f} {a3[1]:.0f} L{a2[0]:.0f} {a2[1]:.0f}" fill="none" stroke-width="{h*0.008:.1f}"/>'
        for j in range(1, 14):
            t = s0 + (1-s0)*j/14; w = wdt*(0.8 + 0.2*j/14)
            q1, q2 = p(t, 0), p(t, w)
            o += f'<path d="M{q1[0]:.0f} {q1[1]:.0f} L{q2[0]:.0f} {q2[1]:.0f}" stroke-width="{h*0.005:.1f}"/>'
        for w in (wdt*0.33, wdt*0.66):
            q1, q2 = p(s0, w*0.85), p(1, w)
            o += f'<path d="M{q1[0]:.0f} {q1[1]:.0f} L{q2[0]:.0f} {q2[1]:.0f}" stroke-width="{h*0.004:.1f}"/>'
    o += f'<circle cx="{hub[0]:.0f}" cy="{hub[1]:.0f}" r="{h*0.025:.0f}" stroke="none"/></g>'
    return o

def polder():
    s = scenes.polder()
    # swap the old windmill group for the new drawing
    a = s.index('<g fill="#0e0c11"><path d="M340')
    e = s.index('</g>', a) + 4
    return s[:a] + windmill(380, 642, 270, 28, '#0e0c11') + s[e:]

def alps():
    rng = random.Random(7)
    defs = lin('sky', [(0, '#0d1630'), (.55, '#2c4a73'), (1, '#b3c4d3')]) + \
           lin('far', [(0, '#eef2f6'), (.1, '#cdd8e2'), (.2, '#7189a3'), (1, '#6f86a0')]) + \
           lin('face', [(0, '#46525f'), (1, '#1a222c')], x2=1, y2=0.5) + tex('rock', '0.01 0.025', 5, 4, 2.0) + \
           '<filter id="cl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="30"/></filter>'
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    b += '<g filter="url(#cl)" fill="#dfe6ee" opacity=".35">' + ''.join(
        f'<ellipse cx="{rng.uniform(0, W):.0f}" cy="{rng.uniform(80, 330):.0f}" rx="{rng.uniform(120, 320):.0f}" ry="{rng.uniform(20, 50):.0f}"/>' for _ in range(14)) + '</g>'
    for i, c in enumerate(['url(#far)', '#4d6380', '#33455e']):
        d, _ = ridge(rng, 430 + i*110, 230 - i*40, 0.5, n=8)
        b += f'<path d="{d}" fill="{c}"/>'
    # steep near slope rising to the upper right, irregular ridge line
    rid = [(520, 1080), (760, 820), (900, 700), (1010, 560), (1120, 470), (1230, 380), (1330, 300), (1420, 255), (1500, 240), (1600, 290), (1720, 330), (1820, 360), (1920, 380)]
    jag = ' '.join(f'L{x + rng.uniform(-14, 14):.0f} {y + rng.uniform(-10, 10):.0f}' for x, y in rid)
    face = f'M{rid[0][0]} {rid[0][1]} {jag} L1920 1080 Z'
    b += f'<path d="{face}" fill="url(#face)"/><path d="{face}" fill="#000" filter="url(#rock)" opacity=".4"/>'
    b += f'<path d="M1380 290 L1500 236 L1620 300 L1560 310 L1500 280 L1440 320 Z" fill="#dde5ec" opacity=".85"/>'
    b += f'<clipPath id="fc"><path d="{face}"/></clipPath><g clip-path="url(#fc)">'
    def xl(y):
        # left edge of the slope at height y, plus a margin
        for (x1, y1), (x2, y2) in zip(rid, rid[1:]):
            if y2 <= y <= y1: return x1 + (x2-x1)*(y1-y)/(y1-y2) + 60
        return 1500
    XR = 1860
    y = 1120; k = 0
    while y > 300:
        w = 5 + 30*((y-280)/840)**1.6
        rise = 34 + 60*((y-280)/840)          # steep traverses
        gap = w*2.4                            # space between stacked traverses
        y2 = y - rise
        if k % 2 == 0: x1, x2, sweep = XR + (120 if k == 0 else 0), xl(y2), 1
        else: x1, x2, sweep = xl(y), XR, 0
        r = gap/2
        d = f'M{x1:.0f} {y:.0f} L{x2:.0f} {y2:.0f} A{r*1.4:.1f} {r:.1f} 0 0 {sweep} {x2:.0f} {y2-gap:.0f}'
        b += f'<path d="{d}" stroke="#10151c" stroke-width="{w*1.6:.1f}" stroke-linecap="butt"/>'
        b += f'<path d="{d}" stroke="#a3adb9" stroke-width="{w:.1f}" stroke-linecap="butt"/>'
        b += f'<path d="M{x1:.0f} {y:.0f} L{x2:.0f} {y2:.0f}" stroke="#e5e9ee" stroke-width="{max(1, w*0.07):.1f}" stroke-dasharray="{w*0.9:.0f} {w*1.5:.0f}"/>'
        if k == 1:
            t = 0.5; bx, by = x1 + (x2-x1)*t, y + (y2-y)*t
        y = y2 - gap; k += 1
    b += '</g>'
    from scenes import riders
    b += riders(bx-60, by+4, 0.032, 4, 36, '#0b0f15', 3, rng, 2)
    return wrap(defs, b + grain(0.05))

def peloton_sunset():
    rng = random.Random(11); hz = 760
    defs = lin('sky', [(0, '#1a1030'), (.5, '#7a2c3e'), (.8, '#e8673a'), (1, '#ffb35c')]) + rad('sun', [(0, '#fff1c0', 1), (.15, '#ffc070', .8), (1, '#ff7a3a', 0)])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/><circle cx="960" cy="{hz}" r="600" fill="url(#sun)"/><circle cx="960" cy="{hz-30}" r="150" fill="#ffe2a8"/>'
    d, _ = ridge(rng, hz-40, 30, 0.5, ymax=H)
    b += f'<path d="{d}" fill="#3a1c2c" opacity="0.6"/>'
    b += f'<rect y="{hz}" width="{W}" height="{H-hz}" fill="#100a12"/>'
    # a bunch of bikes in the icon style: two rows, rolling past the sun
    b += bikes(140, hz-14, 0.1, 11, 160, '#100a12', 8, rng, 30, rows=1)
    b += bikes(60, hz+6, 0.11, 10, 185, '#100a12', 8, rng, 30, rows=1)
    return wrap(defs, b + grain(0.05))

def dunes():
    rng = random.Random(5); hz = 520
    cf, cb = tinted_clouds('uc', 0, 470, '#fbf3ea', '#a3a9b8', freq='0.0018 0.007', seed=3, cover=0.5)
    defs = lin('sky', [(0, '#4b6f99'), (.7, '#a9bfd3'), (1, '#efe0c8')]) + cf + \
           lin('sea', [(0, '#8aa3b8'), (.4, '#557089'), (1, '#3c5368')]) + tex('wave', '0.003 0.12', 3, 7, 2.4, '#ffffff') + \
           tex('sandt', '0.5', 3, 9, 1.3) + tex('ripple', '0.004 0.06', 2, 4, 1.6)
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>{cb}'
    b += f'<rect y="{hz}" width="{W}" height="140" fill="url(#sea)"/><rect y="{hz}" width="{W}" height="140" filter="url(#wave)" opacity=".35"/>'
    # dunes: lit on the sun side, shaded behind the crest
    layers = [('#d8c6a4', '#b39e7c', 600, 60), ('#cdb892', '#a08a68', 680, 80), ('#c2ab83', '#8e7858', 790, 90), ('#b49c74', '#7d684a', 920, 70)]
    for i, (lit, shade, base, amp) in enumerate(layers):
        ph = rng.uniform(0, 6); fr = rng.uniform(0.0025, 0.004)
        pts = [(x, base - amp*math.sin(x*fr+ph) - amp*0.35*math.sin(x*fr*2.7+ph*1.7)) for x in range(-20, W+40, 20)]
        dd = f'M-20 {H} ' + ' '.join(f'L{x} {y:.1f}' for x, y in pts) + f' L{W+40} {H} Z'
        gid = f'dg{i}'
        defs += f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{lit}"/><stop offset="1" stop-color="{shade}"/></linearGradient>'
        b += f'<path d="{dd}" fill="url(#{gid})"/><path d="{dd}" fill="#000" filter="url(#sandt)" opacity=".18"/><path d="{dd}" fill="#000" filter="url(#ripple)" opacity=".12"/>'
        # marram grass clumps along and below the crest
        g = ''
        for x, y in pts[::1]:
            if rng.random() < 0.55:
                n = rng.randint(6, 14); scale = 0.5 + i*0.55
                for _ in range(n):
                    l = rng.uniform(14, 40)*scale; a = rng.uniform(-0.5, 0.5)
                    ox = x + rng.uniform(-10, 10)*scale; oy = y + rng.uniform(2, 30)*scale
                    col = rng.choice(['#7d8456', '#9a9b64', '#5f6a40', '#b0a874'])
                    g += f'<path d="M{ox:.0f} {oy:.0f} q{l*a*0.5:.0f} {-l*0.6:.0f} {l*a*1.3:.0f} {-l:.0f}" stroke="{col}" stroke-width="{0.8+0.6*i:.1f}"/>'
        b += g
        if i == 2:
            # red-brown Dutch cycle path winding through the dunes
            road = 'M1960 1000 C1600 960 1450 860 1180 840 S700 860 420 812 S80 780 -40 790'
            b += f'<path d="{road}" stroke="#5b2f27" stroke-width="34"/><path d="{road}" stroke="#7d4436" stroke-width="28"/>'
            b += f'<path d="{road}" stroke="#e8dcc8" stroke-width="2" stroke-dasharray="18 26" opacity=".6"/>'
            b += bikes(1080, 838, 0.035, 3, 46, '#2a2018', 3, rng, 4)
    return wrap(defs, b + grain(0.06))

def velodrome():
    rng = random.Random(17)
    defs = lin('roof', [(0, '#0b0c10'), (1, '#24262d')]) + tex('crowd', '0.35 0.6', 2, 5, 2.2, '#ffffff') + \
           tex('woodt', '0.004 0.9', 2, 9, 1.4) + rad('lamp', [(0, '#fff8e6', 1), (.2, '#fff1cc', .5), (1, '#fff1cc', 0)]) + \
           rad('pool', [(0, '#fff6e0', .35), (1, '#fff6e0', 0)], .5, .55, .55)
    b = f'<rect width="{W}" height="{H}" fill="url(#roof)"/>'
    # roof trusses
    for i in range(-6, 7):
        x = 960 + i*170
        b += f'<path d="M{x*1.6-576:.0f} -20 Q{x:.0f} 140 {960+i*120:.0f} 300" stroke="#3a3d46" stroke-width="5"/>'
    for y in (40, 110, 180):
        b += f'<path d="M-50 {y} Q960 {y+120} 1970 {y}" stroke="#30333b" stroke-width="3"/>'
    # stands on the far side: rows of seats with a crowd texture
    b += f'<path d="M0 300 Q960 220 1920 300 L1920 520 Q960 430 0 520 Z" fill="#2c3550"/>'
    b += f'<path d="M0 300 Q960 220 1920 300 L1920 520 Q960 430 0 520 Z" fill="#000" filter="url(#crowd)" opacity=".45"/>'
    for k in range(10):
        y0 = 300 + k*22
        b += f'<path d="M0 {y0} Q960 {y0-80+k*1} 1920 {y0}" stroke="#1d2338" stroke-width="2"/>'
    # banked oval: concentric ellipses from the inner edge (low) to the top rail (high)
    cx = 960
    def ell(t):
        rx = 620 + t*560; ry = 150 + t*250; cy = 690 - t*140
        return rx, ry, cy
    for i in range(160, -1, -1):
        t = i/160
        rx, ry, cy = ell(t)
        g = 120 + int(50*math.sin(t*40)*0.3 + rng.uniform(-12, 12)) + int(40*(1-t))
        b += f'<ellipse cx="{cx}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="rgb({g+50},{int(g*0.78)},{int(g*0.5)})"/>'
    b += f'<ellipse cx="{cx}" cy="{ell(1)[2]:.0f}" rx="{ell(1)[0]:.0f}" ry="{ell(1)[1]:.0f}" fill="#000" filter="url(#woodt)" opacity=".18"/>'
    for t, c, w in [(0.97, '#d8dde3', 6), (0.36, '#1f4bb0', 6), (0.2, '#c62828', 6), (0.1, '#111', 6)]:
        rx, ry, cy = ell(t)
        b += f'<ellipse cx="{cx}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" stroke="{c}" stroke-width="{w}"/>'
    # blue cote d'azur band and infield
    rx, ry, cy = ell(0)
    b += f'<ellipse cx="{cx}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#2d5aa8"/>'
    b += f'<ellipse cx="{cx}" cy="{cy+6:.1f}" rx="{rx-40:.1f}" ry="{ry-22:.1f}" fill="#3b4d63"/>'
    b += f'<ellipse cx="{cx}" cy="{cy+8:.1f}" rx="{rx-120:.1f}" ry="{ry-60:.1f}" fill="#4a6b5a"/>'
    # top rail and the near stands cutting across the bottom
    rx, ry, cy = ell(1)
    b += f'<ellipse cx="{cx}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{ry:.0f}" stroke="#9aa3ad" stroke-width="5"/>'
    b += f'<path d="M-20 980 Q960 1080 1940 980 L1940 1100 L-20 1100 Z" fill="#14161b"/>'
    # floodlights and a light pool on the boards
    b += f'<rect width="{W}" height="{H}" fill="url(#pool)"/>'
    for i in range(7):
        x = 260 + i*233; y = 70 + 25*math.cos((i-3)/3)
        b += f'<circle cx="{x}" cy="{y:.0f}" r="70" fill="url(#lamp)"/><rect x="{x-14}" y="{y-5:.0f}" width="28" height="10" fill="#fffbe8"/>'
    # a small group riding the black line
    rx, ry, cy = ell(0.1)
    b += bikes(cx-260, cy+ry-6, 0.05, 3, 64, '#0d0d10', 4, rng, 4)
    return wrap(defs, b + grain(0.07))

REWORK = [('01-polder-dusk', polder), ('02-alpine-switchbacks', alps), ('04-peloton-sunset', peloton_sunset),
          ('05-dune-road', dunes), ('08-velodrome', velodrome)]
if __name__ == '__main__':
    only = sys.argv[1:]
    for name, fn in REWORK:
        if only and not any(o in name for o in only): continue
        open(f'bg-{name}.svg', 'w').write(fn())
