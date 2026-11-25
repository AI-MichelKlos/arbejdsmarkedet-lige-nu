const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const [input, dataDir, output] = process.argv.slice(2);
const dom = new JSDOM(fs.readFileSync(input, 'utf8'));
const document = dom.window.document;
const months = 'januar februar marts april maj juni juli august september oktober november december'.split(' ');
const colors = ['#006d66', '#9b4730', '#80749e'];
const dateKey = /^\d{4}M(0[1-9]|1[0-2])$/;
const pct = new Set(['ledighed', 'andel', 'priser']);
const zero = new Set(['ledighed', 'dimittender', 'langtidsledighed', 'stillinger', 'varslinger']);
const sources = JSON.parse(fs.readFileSync(path.join(__dirname, 'links.json'), 'utf8'));
const missing = 'Mangler';

function format(value, digits = 0) {
  return Number.isFinite(value) ? value.toLocaleString('da-DK', {
    minimumFractionDigits: digits, maximumFractionDigits: digits
  }) : missing;
}

function offset(period, delta) {
  const serial = Number(period.slice(0, 4)) * 12 + Number(period.slice(-2)) - 1 + delta;
  return Math.floor(serial / 12) + 'M' + String(serial % 12 + 1).padStart(2, '0');
}

function label(period) {
  return months[Number(period.slice(-2)) - 1] + ' ' + period.slice(0, 4);
}

function setPeriod(article, period) {
  if (!dateKey.test(period)) throw new Error('Ugyldig periode for ' + article.id);
  const badge = article.querySelector('.eyebrow span');
  const [month, year] = badge.textContent.split(' ');
  const old = year + 'M' + String(months.indexOf(month) + 1).padStart(2, '0');
  if (period < old) throw new Error('Kilden går tilbage i tid for ' + article.id);
  badge.textContent = label(period);
}

function table(scope, rows) {
  const body = scope.querySelector('tbody');
  const count = scope.querySelectorAll('thead th').length;
  body.replaceChildren();
  for (const row of rows) {
    if (row.length !== count) throw new Error('Forkert antal tabelkolonner');
    const tr = body.insertRow();
    row.forEach((value, i) => {
      const cell = document.createElement(i ? 'td' : 'th');
      if (!i) cell.scope = 'row';
      cell.textContent = value;
      tr.appendChild(cell);
    });
  }
}

function scale(id, values) {
  if (id === 'job') return [2600000, 3200000, 100000];
  const low = zero.has(id) ? 0 : Math.min(...values);
  const high = Math.max(...values);
  const raw = Math.max(high - low, pct.has(id) ? 0.5 : 5) / 5;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].find(n => n * power >= raw) * power;
  const start = Math.floor(low / step) * step;
  return [start, Math.max(start + step, Math.ceil(high / step) * step), step];
}

function lines(id, pane, rows) {
  const svg = pane.querySelector('svg');
  const n = ['langtidsledighed', 'priser'].includes(id) ? 2 : 1;
  const values = rows.flatMap(row => row.slice(0, n)).filter(Number.isFinite);
  if (!values.length) throw new Error('Tom graf: ' + id);
  const [start, end, step] = scale(id, values);
  const y = value => (130 - 120 * (value - start) / (end - start)).toFixed(2);
  const clip = 'clip-' + pane.id;
  let content = '<defs><clipPath id="' + clip + '"><rect x="-2" y="9" width="524" height="122"/></clipPath></defs>';
  for (let i = 0; i <= Math.round((end - start) / step); i++) {
    const v = start + i * step;
    const tick = v.toLocaleString('da-DK', { maximumFractionDigits: 3 }) + (pct.has(id) ? ' %' : '');
    content += '<path d="M0 ' + y(v) + 'h520" stroke="#d5dfdc"/><text x="528" y="' + (Number(y(v))+4) + '">' + tick + '</text>';
  }
  for (let column = 0; column < n; column++) {
    let move = true;
    const points = [];
    rows.forEach((row, i) => {
      if (!Number.isFinite(row[column])) { move = true; return; }
      points.push((move ? 'M' : 'L') + (520*i/(rows.length-1)).toFixed(2) + ' ' + y(row[column]));
      move = false;
    });
    content += '<path clip-path="url(#' + clip + ')" d="' + points.join(' ') + '" fill="none" stroke="' + colors[column] + '" stroke-width="3"/>';
  }
  svg.innerHTML = content;
}

function timeSeries(article, data) {
  const id = article.id;
  const period = Object.keys(data).sort().at(-1);
  setPeriod(article, period);
  const metrics = [...article.querySelectorAll('.metrics > div')];
  const units = metrics.map(div => div.querySelector('em').textContent);
  const current = data[period];
  if (current.length !== units.length || !current.every(Number.isFinite)) throw new Error('Seneste observation mangler for ' + id);
  for (const [p, row] of Object.entries(data)) {
    if (!dateKey.test(p) || row.length !== units.length || row.some(v => v !== null && !Number.isFinite(v))) throw new Error('Ugyldig observation for ' + id);
  }
  metrics.forEach((metric, i) => {
    const percent = units[i] === '%';
    const em = metric.querySelector('em');
    metric.querySelector('b').replaceChildren(format(current[i], Number(percent)) + ' ', em);
    [...metric.querySelectorAll('small')].forEach((small, k) => {
      const monthsBack = k ? 1 : 12;
      const prev = data[offset(period, -monthsBack)]?.[i];
      const delta = Number.isFinite(prev) ? Number((current[i] - prev).toFixed(Number(percent))) : null;
      const suffix = k ? ' siden sidste måned' : ' på et år';
      small.textContent = delta === null ? 'Sammenligning mangler' : (delta > 0 ? '+' : '') +
        format(delta || 0, Number(percent)) + ' ' + (percent ? 'procentpoint' : units[i]) + suffix;
    });
  });
  const hero = document.querySelector('.hero a[href="#' + id + '"]');
  if (hero) {
    hero.querySelector('strong').textContent = format(current[0], Number(units[0] === '%')) + (units[0] === '%' ? ' %' : '');
    hero.querySelector('small:last-child').textContent = label(period);
  }
  for (const pane of article.querySelectorAll('.period-pane')) {
    const span = Number(pane.dataset.years) * 12;
    const periods = Array.from({ length: span+1 }, (_, i) => offset(period, i-span));
    const rows = periods.map(p => data[p] ?? units.map(() => null));
    lines(id, pane, rows);
    const axis = pane.querySelectorAll('.axis span');
    axis[0].textContent = label(periods[0]);
    axis[1].textContent = label(period);
    table(pane, rows.map((row,i) => [label(periods[i]), ...row.map((v,j) => format(v, Number(units[j] === '%')))]).reverse());
  }
}

function snapshot(article, [period, rows]) {
  setPeriod(article, period);
  const id = article.id;
  const senior = id === 'seniorer';
  const samples = [...article.querySelectorAll(senior ? '.stackrow' : '.barrow')];
  if (!rows.length || (senior && (rows.length !== 21 || !rows.some(r => r.slice(1).every(Number.isFinite))))) throw new Error('Ufuldstændig figur ' + id);
  const template = samples[0].cloneNode(true);
  const before = article.querySelector('details');
  samples.forEach(node => node.remove());
  const max = Math.max(1, ...rows.map(r => Math.abs(r[1])));
  for (const [name, ...values] of rows) {
    const bar = template.cloneNode(true);
    bar.querySelector('span').textContent = name;
    const sticks = [...bar.querySelectorAll('i')];
    sticks.forEach((stick, i) => {
      const v = values[i];
      stick.style.width = Number.isFinite(v) ? (senior ? v : 100*Math.abs(v)/max).toFixed(4) + '%' : '0%';
      stick.style.background = senior ? colors[i] : colors[Number(id === 'brancher' && v < 0)];
    });
    if (!senior) bar.querySelector('strong').textContent = format(values[0], Number(id !== 'brancher'));
    article.insertBefore(bar, before);
  }
  table(article, rows.map(([name, ...v]) => [name, ...v.map((n,i) => {
    if (id === 'alder' && i === 1) return format(Math.round(n/100)*100);
    return format(n, id === 'brancher' && i === 0 ? 0 : 1);
  })]));
}

for (const article of document.querySelectorAll('main article')) {
  const id = article.id;
  const data = JSON.parse(fs.readFileSync(path.join(dataDir, id+'.json'), 'utf8'));
  if (Array.isArray(data)) snapshot(article, data);
  else timeSeries(article, data);
  article.querySelector('footer a').href = sources[id];
}
fs.writeFileSync(output, dom.serialize());
