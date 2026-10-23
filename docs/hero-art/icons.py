import sys; sys.path.insert(0, '.')
from bike import bike, svg, figure
def fig(left, bottom, s, crank, rider=True, op=1, sw=8):
    return figure(left+340*s, bottom-340*s, s, crank, rider=rider, sw=sw, opacity=op)
V = {}
V['a-racing-bike'] = svg(bike(134, 226, 0.335, crank=-40), 600, 360, 9)
V['b-rider'] = svg([fig(108, 345, 0.23, -30, sw=8)], 600, 360, 8)
V['c-paceline'] = svg([fig(15, 300, 0.15, 70, op=0.45, sw=6), fig(170, 325, 0.175, 170, op=0.7, sw=7), fig(370, 350, 0.2, -30, sw=8)], 720, 360)
V['d-bunch'] = svg([fig(130, 255, 0.135, 100, op=0.4, sw=5), fig(345, 262, 0.135, 250, op=0.4, sw=5),
                    fig(30, 300, 0.165, 20, op=0.7, sw=6), fig(300, 305, 0.165, 190, op=0.7, sw=6),
                    fig(170, 350, 0.19, -30, sw=8)], 720, 360)
V['e-duo'] = svg([fig(250, 320, 0.2, 140, op=0.6, sw=7), fig(110, 350, 0.225, -30, sw=8)], 640, 360)
V['f-three-bikes'] = svg([fig(15, 290, 0.14, 60, rider=False, op=0.45, sw=6), fig(220, 320, 0.17, 150, rider=False, op=0.7, sw=7),
                          fig(440, 350, 0.2, -40, rider=False, sw=8)], 800, 360)
for k, v in V.items(): open(f'icon-{k}.svg', 'w').write(v)
html = '<html><body style="margin:0;background:#111216;font-family:sans-serif;color:#ddd;display:grid;grid-template-columns:repeat(3,1fr);gap:20px;padding:24px;width:1500px">'
html += ''.join(f'<div style="padding:16px;border:1px solid #2a2b31;border-radius:12px;display:flex;flex-direction:column;gap:12px"><div style="font-size:22px">{k.upper().replace("-"," ",1)}</div><div style="height:250px;display:flex;align-items:center;justify-content:center">{v.replace("<svg ","<svg style=\'max-width:100%;max-height:250px\' ")}</div></div>' for k, v in V.items())
html += '</body></html>'
open('icons.html', 'w').write(html)
# G: bunch of five bikes, no riders (Roland: "D but without the stick figures")
V2 = svg([fig(110, 250, 0.16, 100, rider=False, op=0.4, sw=5), fig(370, 256, 0.16, 250, rider=False, op=0.4, sw=5),
          fig(20, 300, 0.19, 20, rider=False, op=0.7, sw=6), fig(300, 306, 0.19, 190, rider=False, op=0.7, sw=6),
          fig(160, 340, 0.22, -40, rider=False, sw=8)], 720, 360).replace("viewBox=\"0 0 720 360\"", "viewBox=\"0 40 720 315\"")
open('icon-g-bunch-bikes.svg', 'w').write(V2)
open('t.html', 'w').write('<body style="margin:0;background:#111216">' + V2.replace('<svg ', '<svg width="1080" ') + '</body>')
