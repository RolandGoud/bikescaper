"""Line-art racing bike (and rider) generator. Coordinates in mm, y up; output SVG y down."""
import math

def ik(a, b, l1, l2, bend=1):
    """Return joint between a and b for 2-link chain; bend=+1 joint to the 'left' of a->b."""
    dx, dy = b[0]-a[0], b[1]-a[1]
    d = math.hypot(dx, dy)
    d = min(d, l1+l2-1e-6)
    ang = math.atan2(dy, dx)
    cosA = (l1*l1 + d*d - l2*l2) / (2*l1*d)
    A = math.acos(max(-1, min(1, cosA)))
    t = ang + bend*A
    return (a[0]+l1*math.cos(t), a[1]+l1*math.sin(t))

R = (0, 0); F = (989, 0); BB = (404, -70)
HTT = (789, 490); HTB = (833, 347); STT = (256, 429)
WHEEL = 340

def bike(ox=0, oy=0, s=1.0, crank=110, rider=False, deep=True, halo=None):
    """Return list of SVG path/circle strings; (ox,oy) = svg position of rear axle; s = px per mm."""
    P = lambda p: (ox + p[0]*s, oy - p[1]*s)
    def L(*pts):
        q = [P(p) for p in pts]
        return '<path d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in q) + '"/>'
    def C(c, r):
        x, y = P(c); return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r*s:.1f}"/>'
    out = []
    for w in (R, F):
        out.append(C(w, WHEEL))
        if deep: out.append(C(w, WHEEL-45))
        out.append(C(w, 18))
    # frame: chainstay, seat stay, seat tube, top tube, down tube, head tube
    out.append(L(R, BB, STT, HTT, HTB, BB))
    out.append(L(R, (262, 405)))
    # fork with slight rake
    x1, y1 = P(HTB); x2, y2 = P(F); cx, cy = P((905, 120))
    out.append(f'<path d="M{x1:.1f} {y1:.1f} Q{cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}"/>')
    # seatpost + saddle
    out.append(L(STT, (222, 560)))
    out.append(L((150, 572), (300, 566)))
    # steerer, stem, drop bar
    out.append(L(HTT, (783, 515), (895, 535)))
    bx, by = P((895, 535)); k = s
    out.append(f'<path d="M{bx:.1f} {by:.1f} h{60*k:.1f} c{45*k:.1f} 0 {58*k:.1f} {48*k:.1f} {42*k:.1f} {90*k:.1f} '
               f'c{-10*k:.1f} {26*k:.1f} {-34*k:.1f} {38*k:.1f} {-62*k:.1f} {36*k:.1f}"/>')
    # crank + chainring
    out.append(C(BB, 95))
    a = math.radians(crank)
    ped = (BB[0]+170*math.cos(a), BB[1]+170*math.sin(a))
    if not rider:
        out.append(L(BB, ped))
        out.append(L((ped[0]-45, ped[1]), (ped[0]+45, ped[1])))
    if rider:
        hip = (205, 610)
        ta = math.radians(27)
        sh = (hip[0]+500*math.cos(ta), hip[1]+500*math.sin(ta))
        hood = (968, 548)
        a2 = a + math.pi
        ped2 = (BB[0]+170*math.cos(a2), BB[1]+170*math.sin(a2))
        knee = ik(hip, ped2, 445, 430, bend=1)
        out.insert(0, L(hip, knee, ped2, (ped2[0]+75, ped2[1]-5)))
        near_start = len(out)
        out.append(L(BB, ped))
        knee = ik(hip, ped, 445, 430, bend=1)
        out.append(L(hip, knee, ped, (ped[0]+75, ped[1]-5)))
        elbow = ik(sh, hood, 240, 225, bend=-1)
        out.append(L(sh, elbow, hood))
        # curved back: hip -> shoulder, bulging up
        (x1, y1), (x2, y2) = P(hip), P(sh)
        mx, my = P(((hip[0]+sh[0])/2 - 15, (hip[1]+sh[1])/2 + 45))
        out.append(f'<path d="M{x1:.1f} {y1:.1f} Q{mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}"/>')
        nk = (sh[0]+80, sh[1]+30)
        out.append(L(sh, nk))
        hx, hy = P((nk[0]+60, nk[1]+75)); r = 88*s
        out.append(f'<path d="M{hx-r*1.3:.1f} {hy+r*0.2:.1f} Q{hx-r*0.6:.1f} {hy-r*1.1:.1f} {hx+r*0.5:.1f} {hy-r*0.85:.1f} '
                   f'Q{hx+r*1.15:.1f} {hy-r*0.45:.1f} {hx+r*0.95:.1f} {hy+r*0.45:.1f} Z"/>')
        if halo:
            near = ''.join(out[near_start:])
            out[near_start:] = [f'<g stroke="{halo[0]}" stroke-width="{halo[1]}">{near}</g>' + near]
    return out

def svg(parts, w, h, sw=10, color="#FF5A1F", extra=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{extra}' + ''.join(parts) + '</svg>')

def figure(ox, oy, s, crank, rider=True, sw=9, halo="#111216", opacity=1, color=None):
    parts = ''.join(bike(ox, oy, s, crank=crank, rider=rider, halo=(halo or '#111216', sw*2.2)))
    c = f' stroke="{color}"' if color else ''
    return (f'<g stroke="{halo}" stroke-width="{sw*2.6:.1f}">{parts}</g>' if halo else '') + \
           f'<g stroke-width="{sw}" opacity="{opacity}"{c}>{parts}</g>'
