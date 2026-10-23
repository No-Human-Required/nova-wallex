// Algorithmic ambience: a market graph in the background and a scanner radar.
const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

export function background(canvas) {
  if (reduce()) return;
  const g = canvas.getContext('2d'); let w, h, d, nodes = [], pulses = [], last = 0;
  const resize = () => { d = devicePixelRatio || 1; w = innerWidth; h = innerHeight; canvas.width = w * d; canvas.height = h * d; g.setTransform(d, 0, 0, d, 0, 0); };
  resize(); addEventListener('resize', resize);
  const count = Math.min(70, Math.floor(innerWidth * innerHeight / 22000));
  for (let i = 0; i < count; i++) nodes.push({ x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - .5) * .18, vy: (Math.random() - .5) * .18, r: Math.random() * 1.6 + .6, hot: Math.random() < .12 });
  function frame(t) {
    requestAnimationFrame(frame);
    if (document.hidden || t - last < 33) return; last = t;
    g.clearRect(0, 0, w, h);
    for (const n of nodes) { n.x += n.vx; n.y += n.vy; if (n.x < 0 || n.x > w) n.vx *= -1; if (n.y < 0 || n.y > h) n.vy *= -1; }
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j], dx = a.x - b.x, dy = a.y - b.y, dist = dx * dx + dy * dy;
      if (dist < 20000) { g.strokeStyle = `rgba(122,167,255,${(1 - dist / 20000) * .12})`; g.lineWidth = 1; g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(b.x, b.y); g.stroke();
        if (Math.random() < .0008 && pulses.length < 14) pulses.push({ a, b, k: 0, c: Math.random() < .5 ? '245,195,67' : '52,211,153' }); }
    }
    for (const n of nodes) { g.fillStyle = n.hot ? 'rgba(245,195,67,.55)' : 'rgba(160,170,185,.35)'; g.beginPath(); g.arc(n.x, n.y, n.r, 0, 6.3); g.fill(); }
    pulses = pulses.filter(p => (p.k += .02) < 1);
    for (const p of pulses) { const x = p.a.x + (p.b.x - p.a.x) * p.k, y = p.a.y + (p.b.y - p.a.y) * p.k; g.fillStyle = `rgba(${p.c},${1 - p.k})`; g.beginPath(); g.arc(x, y, 2.2, 0, 6.3); g.fill(); }
  }
  requestAnimationFrame(frame);
}

export class Radar {
  constructor(canvas) {
    this.c = canvas; this.g = canvas.getContext('2d'); this.blips = []; this.pairs = 120; this.alive = true; this.a = 0;
    this.ro = new ResizeObserver(() => this.resize()); this.ro.observe(canvas); this.resize();
    requestAnimationFrame(t => this.frame(t));
  }
  destroy() { this.alive = false; this.ro.disconnect(); }
  resize() { const r = this.c.getBoundingClientRect(), d = devicePixelRatio || 1; this.w = r.width; this.h = r.height; this.c.width = r.width * d; this.c.height = r.height * d; this.g.setTransform(d, 0, 0, d, 0, 0); }
  set(candidates, pairs) {
    this.pairs = pairs || 120;
    this.blips = (candidates || []).map((c, i) => ({ label: c.symbol, fam: (c.strategy || '').startsWith('smc') ? 'smc' : 'ind',
      ang: (hash(c.symbol) % 360) * Math.PI / 180, rad: .35 + .55 * (1 - Math.min(1, (c.score || 0) / 6)), seen: 0 }));
  }
  frame(t) {
    if (!this.alive) return; requestAnimationFrame(tt => this.frame(tt));
    if (document.hidden || !this.w) return;
    const g = this.g, cx = this.w / 2, cy = this.h / 2, R = Math.min(cx, cy) - 14;
    if (!reduce()) this.a = (t / 2600) % (Math.PI * 2);
    g.clearRect(0, 0, this.w, this.h);
    g.strokeStyle = '#232830'; g.lineWidth = 1;
    for (let k = 1; k <= 4; k++) { g.beginPath(); g.arc(cx, cy, R * k / 4, 0, 6.3); g.stroke(); }
    for (let k = 0; k < 12; k++) { const a = k * Math.PI / 6; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R); g.stroke(); }
    for (let i = 0; i < this.pairs; i++) { const a = i / this.pairs * Math.PI * 2; g.fillStyle = '#3a404a'; g.fillRect(cx + Math.cos(a) * (R + 6) - 1, cy + Math.sin(a) * (R + 6) - 1, 2, 2); }
    const grad = g.createConicGradient ? g.createConicGradient(this.a - .9, cx, cy) : null;
    if (grad) { grad.addColorStop(0, 'rgba(245,195,67,0)'); grad.addColorStop(.14, 'rgba(245,195,67,.22)'); grad.addColorStop(.145, 'rgba(245,195,67,0)'); g.fillStyle = grad; g.beginPath(); g.arc(cx, cy, R, 0, 6.3); g.fill(); }
    g.strokeStyle = 'rgba(245,195,67,.8)'; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(this.a) * R, cy + Math.sin(this.a) * R); g.stroke();
    g.font = '10px ui-monospace, monospace'; g.textAlign = 'center';
    for (const b of this.blips) {
      const diff = ((this.a - b.ang) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
      if (diff < .08) b.seen = 1; b.seen = Math.max(.25, b.seen - .004);
      const x = cx + Math.cos(b.ang) * R * b.rad, y = cy + Math.sin(b.ang) * R * b.rad;
      const col = b.fam === 'smc' ? '180,156,255' : '94,234,212';
      g.fillStyle = `rgba(${col},${b.seen})`; g.beginPath(); g.arc(x, y, 4, 0, 6.3); g.fill();
      g.strokeStyle = `rgba(${col},${b.seen * .5})`; g.beginPath(); g.arc(x, y, 4 + 8 * (1 - b.seen), 0, 6.3); g.stroke();
      g.fillStyle = `rgba(230,235,240,${b.seen})`; g.fillText(b.label.replace(/(TMN|USDT)$/, ''), x, y - 9);
    }
    g.fillStyle = '#98a0ab'; g.font = '11px Vazirmatn'; g.fillText(`${this.pairs} جفت مجاز · ${this.blips.length} ستاپ`, cx, this.h - 4);
  }
}
function hash(s) { let x = 7; for (const ch of s) x = (x * 31 + ch.charCodeAt(0)) >>> 0; return x; }

// Schematic, animated pattern illustrations (generic, not real data).
export const ART = {
  smc_liquidity_sweep: `<svg viewBox="0 0 150 104"><line x1="8" y1="70" x2="142" y2="70" stroke="#f5c34366" stroke-dasharray="4 3"/><text x="10" y="66" fill="#f5c343aa" font-size="8">کف ۲۴ساعته</text>
    <polyline class="draw" fill="none" stroke="#98a0ab" stroke-width="1.6" points="10,40 30,55 45,48 60,66 75,60 90,88 98,64 112,44 128,30 142,24"/>
    <circle class="blink" cx="90" cy="88" r="5" fill="none" stroke="#fb7185"/><path class="blink" d="M112 44 l6 -10 l6 10z" fill="#34d399"/><line class="blink" x1="8" y1="24" x2="142" y2="24" stroke="#34d39966" stroke-dasharray="3 3"/></svg>`,
  smc_bos_orderblock: `<svg viewBox="0 0 150 104"><line x1="8" y1="42" x2="142" y2="42" stroke="#f5c34366" stroke-dasharray="4 3"/><rect class="blink" x="40" y="60" width="26" height="12" fill="#b49cff22" stroke="#b49cff"/>
    <polyline class="draw" fill="none" stroke="#98a0ab" stroke-width="1.6" points="8,70 25,55 40,66 52,70 70,40 84,26 98,48 108,64 118,52 132,30 142,20"/><text x="86" y="20" fill="#f5c343aa" font-size="8">BOS</text><text x="38" y="84" fill="#b49cffaa" font-size="8">OB</text></svg>`,
  smc_fvg_continuation: `<svg viewBox="0 0 150 104"><rect class="blink" x="58" y="44" width="84" height="14" fill="#b49cff18" stroke="#b49cff88"/>
    <polyline class="draw" fill="none" stroke="#98a0ab" stroke-width="1.6" points="8,84 30,76 48,70 58,58 70,30 86,26 100,40 112,52 124,38 142,18"/><text x="64" y="54" fill="#b49cffcc" font-size="8">FVG</text></svg>`,
  ind_ema_macd_trend: `<svg viewBox="0 0 150 104"><polyline class="draw" fill="none" stroke="#5eead4" stroke-width="1.4" points="8,80 40,70 70,56 100,42 142,24"/><polyline class="draw" fill="none" stroke="#7aa7ff" stroke-width="1.4" points="8,84 40,78 70,66 100,54 142,40"/>
    <polyline class="draw" fill="none" stroke="#98a0ab" stroke-width="1.2" points="8,76 25,72 40,62 55,66 70,50 85,52 100,36 120,32 142,18"/>${[0,1,2,3,4,5,6,7,8].map(i => `<rect class="blink" x="${12 + i * 15}" y="${96 - i * 1.5}" width="8" height="${3 + i * 1.5}" fill="#34d39988"/>`).join('')}</svg>`,
  ind_rsi_bollinger_reversion: `<svg viewBox="0 0 150 104"><path d="M8 30 Q75 18 142 30" fill="none" stroke="#7aa7ff66"/><path d="M8 82 Q75 94 142 82" fill="none" stroke="#7aa7ff66"/><path d="M8 56 Q75 56 142 56" fill="none" stroke="#f5c34366" stroke-dasharray="4 3"/>
    <polyline class="draw" fill="none" stroke="#98a0ab" stroke-width="1.6" points="8,50 25,60 42,72 58,92 70,84 84,74 98,64 112,58 128,54 142,52"/><circle class="blink" cx="58" cy="92" r="5" fill="none" stroke="#5eead4"/></svg>`,
  ind_relative_strength: `<svg viewBox="0 0 150 104"><polyline fill="none" stroke="#fb718599" stroke-width="1.4" points="8,30 40,44 70,52 100,66 142,80"/><text x="110" y="92" fill="#fb7185aa" font-size="8">BTC</text>
    <polyline class="draw" fill="none" stroke="#5eead4" stroke-width="1.8" points="8,60 40,56 70,48 100,40 142,24"/><text x="104" y="20" fill="#5eead4cc" font-size="8">قدرت نسبی</text></svg>`
};
