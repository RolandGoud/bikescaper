// The size finder's steps as a stage race: a pack of the site's bike icons rides along the progress bar. At the
// first steps they ride as one bunch; from the model step on a breakaway in green pulls clear and the pack behind
// strings out along the filled bar. The last step you were on is kept in sessionStorage, so on the next step the
// riders roll forward from where they were instead of appearing in place.
(() => {
  const nav = document.querySelector('.size-wizard[data-step]');
  if (!nav) return;
  const ol = nav.querySelector('ol'), lis = [...ol.children];
  const at = +nav.dataset.step, kind = nav.dataset.kind;
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const types = kind ? [kind] : ['road', 'gravel', 'road', 'tt', 'fitness', 'road', 'gravel', 'road'];
  const pel = document.createElement('div');
  pel.className = 'peloton'; pel.setAttribute('aria-hidden', 'true');
  nav.insertBefore(pel, ol);
  const base = nav.dataset.icons;
  let riders = [];

  function build() {
    const phone = innerWidth < 700, n = phone ? 6 : 8;
    pel.textContent = ''; riders = [];
    pel.classList.toggle('phone', phone);
    for (let i = 0; i < n; i++) {
      const r = document.createElement('span');
      r.style.setProperty('--icon', `url('${base}${types[i % types.length]}.svg')`);
      if (!still) {
        r.style.animationDuration = (0.8 + ((i * 7) % 8) / 10).toFixed(1) + 's';
        r.style.animationDelay = (-((i * 3) % 10) / 10).toFixed(1) + 's';
      }
      pel.appendChild(r); riders.push(r);
    }
    return n;
  }

  // Each rider's left edge, in px from the bar's left, for step `step`.
  function layout(step) {
    const o = ol.getBoundingClientRect(), rw = riders[0].offsetWidth || 30;
    const seg = lis[step].getBoundingClientRect();
    const front = seg.right - o.left;
    const brk = [0, 0, 1, 2, 3][step], n = riders.length;
    const spread = rw * [0.55, 0.85, 1.3, 1.7, 2.1][step];
    return riders.map((_, i) => {
      const isBrk = i < brk, idx = isBrk ? i : i - brk;
      let x, back = false;
      if (isBrk) x = front - i * rw * 1.05;
      else if (step < 2) { back = idx % 2 === 1; x = front - idx * rw * 0.45; }
      else x = front - (brk ? (seg.right - seg.left) * 0.3 : 0) - idx * spread;
      return { x: Math.max(0, x - rw), isBrk, back };
    });
  }

  function place(step, instant) {
    const pos = layout(step);
    riders.forEach((r, i) => {
      const p = pos[i];
      r.style.transitionDuration = instant || still ? '0s' : (p.isBrk ? 1.1 + i * .08 : 1.6 + i * .06) + 's';
      r.style.transform = `translate(${p.x}px, ${p.back ? -5 : 0}px)`;
      r.style.zIndex = p.back ? 1 : 20 - i;
      r.classList.toggle('back', p.back);
      r.classList.toggle('brk', p.isBrk);
    });
  }

  let from = at;
  try { const was = +sessionStorage.getItem('size-step'); if (was >= 0 && was < at) from = was; sessionStorage.setItem('size-step', at); } catch (e) {}
  build();
  place(from, true);
  if (from !== at) requestAnimationFrame(() => requestAnimationFrame(() => place(at)));
  let w = innerWidth;
  addEventListener('resize', () => { if ((innerWidth < 700) !== (w < 700)) build(); w = innerWidth; place(at, true); });
})();
