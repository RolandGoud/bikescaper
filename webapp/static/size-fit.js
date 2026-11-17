// The model page's sizes: type your height and a sentence says which size fits it ("At 178 cm: M (175–183 cm)")
// and which are borderline, within 4 cm ("Borderline: ML (from 180 cm)"); the pills light up the same way. The
// height is kept in this browser, so the next model page opens with it. Without script, Enter reloads the page
// with ?height= and the server renders the same.
(() => {
  const form = document.querySelector('form.size-fit');
  if (!form) return;
  const input = form.querySelector('input[name=height]');
  const verdict = document.querySelector('.size-verdict');
  const empty = form.dataset.empty;
  const t = form.dataset, KEY = 'bikecheck-height';
  const fill = (text, values) => text.replace(/\{(\w+)\}/g, (_, k) => values[k]);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const store = v => { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (e) {} };
  if (!input.value) { try { input.value = localStorage.getItem(KEY) || ''; } catch (e) {} }

  function update() {
    const h = Number(input.value), valid = h >= 120 && h <= 220;
    const fits = [], near = [];  // fits: one list per size system (frame sizes in cm, letter sizes)
    document.querySelectorAll('.size-pills').forEach(row => {
      row.classList.toggle('fitted', valid);
      const own = [];
      fits.push(own);
      row.querySelectorAll('[data-size]').forEach(p => {
        const lo = +p.dataset.low, hi = +p.dataset.high;
        const on = valid && lo <= h && h <= hi, close = valid && !on && lo - 4 <= h && h <= hi + 4;
        p.classList.toggle('on', on);
        p.classList.toggle('near', close);
        if (on) own.push([p.dataset.size, lo, hi]);
        if (close) near.push([p.dataset.size, lo, hi]);
      });
    });
    const lines = [];
    if (!valid) {
      lines.push(el('p', 'muted', empty));
    } else {
      const p = el('p');
      const groups = fits.filter(g => g.length);
      if (groups.length) {
        p.append(Object.assign(el("span", "size-tick", "✓"), {ariaHidden: "true"}), fill(t.at, {height: h}), ' ');
        groups.forEach((group, g) => {
          if (g) p.append(el('span', 'muted', ' · '));
          group.forEach(([k, lo, hi], i) => {
            if (i) p.append(` ${t.or} `);
            p.append(el('strong', '', k), ' ', el('span', 'muted nowrap', `(${lo}–${hi} cm)`));
          });
        });
      } else {
        p.append(fill(t.none, {height: h}));
      }
      lines.push(p);
      if (near.length) {
        lines.push(el('p', 'muted', `${t.near} ` + near.map(([k, lo, hi]) =>
          `${k} (${lo > h ? fill(t.from, {cm: lo}) : fill(t.to, {cm: hi})})`).join(', ')));
      }
    }
    verdict.replaceChildren(...lines);
  }

  input.addEventListener('input', () => {
    const h = Number(input.value);
    if (h >= 120 && h <= 220) store(input.value); else if (!input.value) store('');
    update();
  });
  form.addEventListener('submit', e => { e.preventDefault(); update(); });
  if (input.value) update();
})();
