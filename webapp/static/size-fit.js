// The model page's sizes: type your height and the sizes that fit it turn green, as chips beside the box and as
// pills below; sizes within 4 cm get a dashed edge, the rest dim. The height is kept in this browser, so the next
// model page opens with it. Without script, Enter reloads the page with ?height= and the server does the same.
(() => {
  const form = document.querySelector('form.size-fit');
  if (!form) return;
  const input = form.querySelector('input[name=height]');
  const answer = form.querySelector('.size-fit-answer');
  const none = answer.querySelector('.size-fit-none');
  const KEY = 'bikecheck-height';
  const store = v => { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (e) {} };
  if (!input.value) { try { input.value = localStorage.getItem(KEY) || ''; } catch (e) {} }

  function chip(pill) {
    const span = document.createElement('span');
    span.className = 'size-chip';
    span.append(pill.dataset.size + ' ');
    const small = document.createElement('small');
    small.textContent = pill.querySelector('small').textContent;
    span.append(small);
    return span;
  }

  function update() {
    const h = Number(input.value);
    const valid = h >= 120 && h <= 220;
    let any = false;
    document.querySelectorAll('.size-pills').forEach(row => {
      row.classList.toggle('fitted', valid);
      const fits = [];
      row.querySelectorAll('[data-size]').forEach(p => {
        const lo = +p.dataset.low, hi = +p.dataset.high;
        const on = valid && lo <= h && h <= hi;
        p.classList.toggle('on', on);
        p.classList.toggle('near', valid && !on && lo - 4 <= h && h <= hi + 4);
        if (on) fits.push(p);
      });
      const group = answer.querySelector(`.size-fit-group[data-system="${row.dataset.system}"]`);
      if (!group) return;
      const label = group.firstElementChild;
      group.replaceChildren(label);
      fits.forEach((p, i) => {
        if (i) { const or = document.createElement('span'); or.className = 'muted'; or.textContent = form.dataset.or; group.append(or); }
        group.append(chip(p));
      });
      group.hidden = !fits.length;
      any = any || fits.length > 0;
    });
    none.textContent = form.dataset.none.replace('{height}', h);
    none.hidden = !valid || any;
  }

  input.addEventListener('input', () => { update(); if (Number(input.value) >= 120 && Number(input.value) <= 220) store(input.value); else if (!input.value) store(''); });
  form.addEventListener('submit', e => { e.preventDefault(); update(); });
  update();
})();
