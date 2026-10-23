// Dependency-free canvas charts with draw-in animation, live pulse and crosshair.
import { clock, when, n0, price as fprice } from './core.js';

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
let tip;
function tooltip() { if (!tip) { tip = document.createElement('div'); tip.className = 'tooltip hidden'; document.body.appendChild(tip); } return tip; }

class Base {
  constructor(canvas, opts = {}) {
    this.c = canvas; this.o = opts; this.ctx = canvas.getContext('2d'); this.progress = reduce() ? 1 : 0; this.hover = null;
    this.ro = new ResizeObserver(() => this.resize()); this.ro.observe(canvas); this.resize();
    canvas.addEventListener('pointermove', e => { const r = canvas.getBoundingClientRect(); this.hover = { x: e.clientX - r.left, y: e.clientY - r.top, cx: e.clientX, cy: e.clientY }; this.draw(); });
    canvas.addEventListener('pointerleave', () => { this.hover = null; tooltip().classList.add('hidden'); this.draw(); });
    this.loop = this.loop.bind(this); this.alive = true; requestAnimationFrame(this.loop);
  }
  destroy() { this.alive = false; this.ro.disconnect(); tooltip().classList.add('hidden'); }
  resize() {
    const r = this.c.getBoundingClientRect(); const d = devicePixelRatio || 1;
    this.w = Math.max(10, r.width); this.h = Math.max(10, r.height);
    this.c.width = this.w * d; this.c.height = this.h * d; this.ctx.setTransform(d, 0, 0, d, 0, 0); this.draw();
  }
  loop(t) {
    if (!this.alive) return;
    if (this.progress < 1) { this.progress = Math.min(1, this.progress + 0.025); }
    this.t = t; if (!document.hidden) this.draw();
    requestAnimationFrame(this.loop);
  }
  pad() { return { l: 10, r: 64, t: 14, b: 24 }; }
  axes(min, max, t0, t1, p, fmt) {
    const g = this.ctx; g.strokeStyle = '#1e2228'; g.fillStyle = css('--faint') || '#666'; g.font = '11px Vazirmatn, sans-serif'; g.lineWidth = 1;
    const rows = 4;
    for (let i = 0; i <= rows; i++) {
      const y = p.t + (this.h - p.t - p.b) * i / rows; const v = max - (max - min) * i / rows;
      g.beginPath(); g.moveTo(p.l, y); g.lineTo(this.w - p.r, y); g.stroke();
      g.textAlign = 'left'; g.fillText(fmt(v), this.w - p.r + 6, y + 4);
    }
    const cols = Math.max(2, Math.floor((this.w - p.l - p.r) / 130));
    g.textAlign = 'center';
    for (let i = 0; i <= cols; i++) {
      const x = p.l + (this.w - p.l - p.r) * i / cols; const t = t0 + (t1 - t0) * i / cols;
      g.fillText(t1 - t0 > 86400 * 1.5 ? when(t) : clock(t).slice(0, -3), x, this.h - 6);
    }
  }
}

export class LineChart extends Base {
  set(points, opts = {}) { this.pts = points || []; Object.assign(this.o, opts); this.draw(); }
  draw() {
    const g = this.ctx; if (!g || !this.w) return; g.clearRect(0, 0, this.w, this.h);
    const pts = (this.pts || []).filter(p => p[1] !== null && isFinite(p[1]));
    if (pts.length < 2) { g.fillStyle = '#5d6470'; g.font = '13px Vazirmatn'; g.textAlign = 'center'; g.fillText(this.o.empty || 'در انتظار داده…', this.w / 2, this.h / 2); return; }
    const p = this.pad(); const base = this.o.baseline;
    let min = Math.min(...pts.map(x => x[1])), max = Math.max(...pts.map(x => x[1]));
    if (base !== undefined) { min = Math.min(min, base); max = Math.max(max, base); }
    const span = (max - min) || Math.abs(max) * 0.002 || 1; min -= span * 0.12; max += span * 0.12;
    const t0 = pts[0][0], t1 = pts[pts.length - 1][0];
    const X = t => p.l + (this.w - p.l - p.r) * (t - t0) / Math.max(1, t1 - t0);
    const Y = v => p.t + (this.h - p.t - p.b) * (1 - (v - min) / (max - min));
    const fmt = this.o.fmt || n0; this.axes(min, max, t0, t1, p, fmt);
    const upto = Math.max(2, Math.floor(pts.length * this.progress));
    const last = pts[upto - 1]; const up = base === undefined ? last[1] >= pts[0][1] : last[1] >= base;
    const color = this.o.color || (up ? css('--green') : css('--red'));
    if (base !== undefined) {
      g.setLineDash([4, 5]); g.strokeStyle = '#f5c34366'; g.beginPath(); g.moveTo(p.l, Y(base)); g.lineTo(this.w - p.r, Y(base)); g.stroke(); g.setLineDash([]);
      g.fillStyle = '#f5c343aa'; g.textAlign = 'left'; g.fillText(this.o.baselineLabel || '', p.l + 4, Y(base) - 5);
    }
    const grad = g.createLinearGradient(0, p.t, 0, this.h - p.b); grad.addColorStop(0, color + '44'); grad.addColorStop(1, color + '00');
    g.beginPath(); pts.slice(0, upto).forEach((q, i) => i ? g.lineTo(X(q[0]), Y(q[1])) : g.moveTo(X(q[0]), Y(q[1])));
    g.lineTo(X(last[0]), this.h - p.b); g.lineTo(X(pts[0][0]), this.h - p.b); g.closePath(); g.fillStyle = grad; g.fill();
    g.beginPath(); pts.slice(0, upto).forEach((q, i) => i ? g.lineTo(X(q[0]), Y(q[1])) : g.moveTo(X(q[0]), Y(q[1])));
    g.strokeStyle = color; g.lineWidth = 2; g.lineJoin = 'round'; g.stroke();
    for (const m of this.o.markers || []) {
      if (m.t < t0 || m.t > t1) continue;
      const near = pts.reduce((a, b) => Math.abs(b[0] - m.t) < Math.abs(a[0] - m.t) ? b : a);
      const x = X(m.t), y = Y(near[1]); const buy = m.side === 'BUY';
      g.fillStyle = buy ? css('--green') : css('--red'); g.beginPath();
      if (buy) { g.moveTo(x, y + 6); g.lineTo(x - 6, y + 16); g.lineTo(x + 6, y + 16); } else { g.moveTo(x, y - 6); g.lineTo(x - 6, y - 16); g.lineTo(x + 6, y - 16); }
      g.fill();
    }
    if (this.progress >= 1 && this.o.live !== false) {
      const x = X(last[0]), y = Y(last[1]); const k = ((this.t || 0) % 1800) / 1800;
      g.beginPath(); g.arc(x, y, 3 + 10 * k, 0, Math.PI * 2); g.fillStyle = color + Math.round((1 - k) * 90).toString(16).padStart(2, '0'); g.fill();
      g.beginPath(); g.arc(x, y, 3.5, 0, Math.PI * 2); g.fillStyle = color; g.fill();
    }
    if (this.hover && this.hover.x > p.l && this.hover.x < this.w - p.r) {
      const t = t0 + (this.hover.x - p.l) / (this.w - p.l - p.r) * (t1 - t0);
      const q = pts.reduce((a, b) => Math.abs(b[0] - t) < Math.abs(a[0] - t) ? b : a);
      const x = X(q[0]), y = Y(q[1]); g.strokeStyle = '#ffffff30'; g.beginPath(); g.moveTo(x, p.t); g.lineTo(x, this.h - p.b); g.stroke();
      g.beginPath(); g.arc(x, y, 4, 0, Math.PI * 2); g.fillStyle = '#fff'; g.fill();
      const tt = tooltip(); tt.classList.remove('hidden'); tt.style.left = (this.hover.cx + 14) + 'px'; tt.style.top = (this.hover.cy - 10) + 'px';
      tt.innerHTML = `<div class="muted">${when(q[0])}</div><b>${fmt(q[1])}</b>${base !== undefined && this.o.relative ? `<div class="${q[1] >= base ? 'pos' : 'neg'}">${((q[1] / base - 1) * 100).toFixed(3)}%</div>` : ''}`;
    }
  }
}

export class CandleChart extends Base {
  set(c, opts = {}) { this.d = c; Object.assign(this.o, opts); this.draw(); }
  draw() {
    const g = this.ctx; if (!g || !this.w) return; g.clearRect(0, 0, this.w, this.h);
    const d = this.d; if (!d || !d.t || d.t.length < 2) { g.fillStyle = '#5d6470'; g.font = '13px Vazirmatn'; g.textAlign = 'center'; g.fillText(this.o.empty || 'در انتظار کندل‌ها…', this.w / 2, this.h / 2); return; }
    const p = this.pad(); const n = d.t.length; const lines = (this.o.lines || []).filter(l => l.y && isFinite(l.y));
    let min = Math.min(...d.l), max = Math.max(...d.h);
    for (const l of lines) { if (this.o.fitLines !== false) { min = Math.min(min, l.y); max = Math.max(max, l.y); } }
    const span = (max - min) || max * 0.002 || 1; min -= span * 0.08; max += span * 0.08;
    const t0 = d.t[0], t1 = d.t[n - 1];
    const X = i => p.l + (this.w - p.l - p.r) * (i + 0.5) / n;
    const Y = v => p.t + (this.h - p.t - p.b) * (1 - (v - min) / (max - min));
    this.axes(min, max, t0, t1, p, fprice);
    const bw = Math.max(1, (this.w - p.l - p.r) / n * 0.62); const upto = Math.max(2, Math.floor(n * this.progress));
    for (let i = 0; i < upto; i++) {
      const up = d.c[i] >= d.o[i]; g.strokeStyle = g.fillStyle = up ? css('--green') : css('--red');
      const x = X(i); g.beginPath(); g.moveTo(x, Y(d.h[i])); g.lineTo(x, Y(d.l[i])); g.lineWidth = 1; g.stroke();
      const y1 = Y(Math.max(d.o[i], d.c[i])), y2 = Y(Math.min(d.o[i], d.c[i])); g.fillRect(x - bw / 2, y1, bw, Math.max(1, y2 - y1));
    }
    g.font = '11px Vazirmatn';
    for (const l of lines) {
      const y = Y(l.y); g.setLineDash(l.dash || [5, 4]); g.strokeStyle = l.color; g.lineWidth = 1.2; g.beginPath(); g.moveTo(p.l, y); g.lineTo(this.w - p.r, y); g.stroke(); g.setLineDash([]);
      g.fillStyle = l.color; g.textAlign = 'right'; g.fillText(l.label + ' ' + fprice(l.y), this.w - p.r - 4, y - 4);
    }
    if (this.progress >= 1) {
      const x = X(n - 1), y = Y(d.c[n - 1]); const k = ((this.t || 0) % 1600) / 1600;
      g.beginPath(); g.arc(x, y, 2 + 8 * k, 0, Math.PI * 2); g.fillStyle = `rgba(245,195,67,${(1 - k) * 0.5})`; g.fill();
      g.fillStyle = '#f5c343'; g.fillRect(this.w - p.r + 2, y - 9, p.r - 4, 18); g.fillStyle = '#111'; g.textAlign = 'left'; g.fillText(fprice(d.c[n - 1]), this.w - p.r + 5, y + 4);
    }
    if (this.hover && this.hover.x > p.l && this.hover.x < this.w - p.r) {
      const i = Math.max(0, Math.min(n - 1, Math.floor((this.hover.x - p.l) / (this.w - p.l - p.r) * n)));
      g.strokeStyle = '#ffffff30'; g.beginPath(); g.moveTo(X(i), p.t); g.lineTo(X(i), this.h - p.b); g.stroke();
      const tt = tooltip(); tt.classList.remove('hidden'); tt.style.left = (this.hover.cx + 14) + 'px'; tt.style.top = (this.hover.cy - 10) + 'px';
      tt.innerHTML = `<div class="muted">${when(d.t[i])}</div><div>O ${fprice(d.o[i])} · H ${fprice(d.h[i])}</div><div>L ${fprice(d.l[i])} · C <b>${fprice(d.c[i])}</b></div>`;
    }
  }
}
