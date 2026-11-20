/* Arcade 12 · motor común: progreso, menús, niveles, sonido, bucle y utilidades */
(function () {
  'use strict';
  const STORE = 'arcade12.progress.v1';
  const read = () => { try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch (e) { return {}; } };
  const write = d => { try { localStorage.setItem(STORE, JSON.stringify(d)); } catch (e) { /* sin almacenamiento */ } };

  function progress(id) {
    const p = read()[id] || {};
    return { unlocked: p.unlocked || 1, stars: p.stars || {}, best: p.best || {} };
  }
  function record(id, level, stars, score) {
    const d = read();
    const p = d[id] || {};
    p.stars = p.stars || {}; p.best = p.best || {};
    p.stars[level] = Math.max(p.stars[level] || 0, stars);
    if (score != null) p.best[level] = Math.max(p.best[level] || 0, score);
    p.unlocked = Math.max(p.unlocked || 1, level + 1);
    d[id] = p; write(d); return p;
  }
  const totalStars = id => Object.values(progress(id).stars).reduce((a, b) => a + b, 0);

  /* ---------------- sonido sintetizado (sin archivos) ---------------- */
  let muted = false;
  try { muted = localStorage.getItem('arcade12.muted') === '1'; } catch (e) { }
  const Sound = {
    ctx: null, master: null,
    get muted() { return muted; },
    init() {
      if (!this.ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        this.ctx = new AC();
        this.master = this.ctx.createGain();
        this.master.gain.value = muted ? 0 : .6;
        this.master.connect(this.ctx.destination);
      }
      if (this.ctx.state === 'suspended' && !this.held) this.ctx.resume();
    },
    setMuted(m) {
      muted = m;
      if (this.master) this.master.gain.value = m ? 0 : .6;
      try { localStorage.setItem('arcade12.muted', m ? '1' : '0'); } catch (e) { }
    },
    tone(f, d = .15, o = {}) {
      if (!this.ctx) return;
      const c = this.ctx, t = (o.at != null ? o.at : c.currentTime) + (o.delay || 0);
      const osc = c.createOscillator(), g = c.createGain();
      osc.type = o.type || 'sine';
      osc.frequency.setValueAtTime(f, t);
      if (o.slide) osc.frequency.exponentialRampToValueAtTime(Math.max(30, f * o.slide), t + d);
      const v = o.vol != null ? o.vol : .2;
      g.gain.setValueAtTime(.0001, t);
      g.gain.exponentialRampToValueAtTime(v, t + (o.attack || .008));
      g.gain.exponentialRampToValueAtTime(.0001, t + d);
      osc.connect(g); g.connect(this.master);
      osc.start(t); osc.stop(t + d + .05);
    },
    noise(d = .2, o = {}) {
      if (!this.ctx) return;
      const c = this.ctx, t = (o.at != null ? o.at : c.currentTime) + (o.delay || 0);
      if (!this._nb) {
        const b = c.createBuffer(1, c.sampleRate, c.sampleRate), ch = b.getChannelData(0);
        for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1;
        this._nb = b;
      }
      const src = c.createBufferSource(); src.buffer = this._nb;
      const f = c.createBiquadFilter(); f.type = o.filter || 'bandpass'; f.frequency.value = o.freq || 1200; f.Q.value = o.q || .8;
      const g = c.createGain(); const v = o.vol != null ? o.vol : .2;
      g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(.0001, t + d);
      src.connect(f); f.connect(g); g.connect(this.master);
      src.start(t, Math.random() * .5); src.stop(t + d + .02);
    },
    play(n) {
      if (!this.ctx) return;
      const T = (f, d, o) => this.tone(f, d, o);
      switch (n) {
        case 'click': T(660, .06, { type: 'triangle', vol: .12 }); break;
        case 'move': T(240, .05, { type: 'square', vol: .035 }); break;
        case 'bump': T(110, .08, { type: 'square', vol: .06 }); break;
        case 'coin': T(988, .08, { type: 'square', vol: .07 }); T(1319, .16, { type: 'square', vol: .07, delay: .07 }); break;
        case 'jump': T(300, .18, { type: 'square', vol: .06, slide: 2.2 }); break;
        case 'shoot': T(880, .08, { type: 'sawtooth', vol: .035, slide: .45 }); break;
        case 'laser': T(1400, .14, { type: 'sawtooth', vol: .05, slide: .3 }); break;
        case 'hit': T(160, .12, { type: 'square', vol: .09, slide: .5 }); this.noise(.1, { vol: .14, freq: 800 }); break;
        case 'explode': this.noise(.45, { vol: .32, freq: 380 }); T(90, .4, { type: 'sawtooth', vol: .1, slide: .3 }); break;
        case 'pop': T(520, .09, { vol: .18, slide: 1.8 }); break;
        case 'swap': T(440, .07, { type: 'triangle', vol: .1, slide: 1.3 }); break;
        case 'error': T(150, .14, { type: 'square', vol: .07 }); T(110, .18, { type: 'square', vol: .07, delay: .09 }); break;
        case 'power': [523, 659, 784, 1047].forEach((f, i) => T(f, .12, { type: 'triangle', vol: .1, delay: i * .06 })); break;
        case 'win': [523, 659, 784, 1047, 1319].forEach((f, i) => T(f, .3, { type: 'triangle', vol: .12, delay: i * .09 })); break;
        case 'lose': [392, 330, 262, 196].forEach((f, i) => T(f, .32, { type: 'sawtooth', vol: .06, delay: i * .14 })); break;
        case 'star': T(1568, .25, { vol: .12 }); T(2093, .3, { vol: .08, delay: .05 }); break;
        case 'splash': this.noise(.35, { vol: .25, freq: 1400, q: .5 }); break;
        case 'tick': T(1200, .03, { type: 'square', vol: .03 }); break;
      }
    }
  };

  /* ---------------- utilidades ---------------- */
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k === 'html') e.innerHTML = v;
      else if (k === 'style') e.style.cssText = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? '' : v);
    }
    kids.flat().forEach(c => c != null && e.append(c));
    return e;
  }
  function loadImages(map) {
    return Promise.all(Object.entries(map).map(([k, src]) => new Promise(res => {
      const i = new Image(); i.onload = () => res([k, i]); i.onerror = () => { console.warn('No se pudo cargar', src); res([k, null]); }; i.src = src;
    }))).then(e => Object.fromEntries(e));
  }
  function rng(seed) {
    let a = seed >>> 0;
    return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  }
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const lerp = (a, b, t) => a + (b - a) * t;
  const ease = t => 1 - Math.pow(1 - t, 3);

  class Particles {
    constructor() { this.list = []; }
    burst(x, y, n, o = {}) {
      const cols = [].concat(o.color || '#fff');
      for (let i = 0; i < n; i++) {
        const a = o.angle != null ? o.angle + (Math.random() - .5) * (o.spread || 6.28) : Math.random() * 6.28;
        const s = (o.speed || 200) * (.3 + Math.random() * .7);
        this.list.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: (o.life || .7) * (.6 + Math.random() * .4), t: 0,
          size: (o.size || 4) * (.5 + Math.random() * .7), color: cols[(Math.random() * cols.length) | 0], g: o.gravity || 0, drag: o.drag || 2, shape: o.shape || 'circle' });
      }
    }
    text(x, y, txt, o = {}) { this.list.push({ x, y, vx: 0, vy: -(o.rise || 60), life: o.life || 1, t: 0, txt, size: o.size || 20, color: o.color || '#fff', g: 0, drag: 1 }); }
    update(dt) {
      for (const p of this.list) {
        p.t += dt; p.vy += p.g * dt;
        const k = Math.exp(-p.drag * dt); p.vx *= k; p.vy *= k;
        p.x += p.vx * dt; p.y += p.vy * dt;
      }
      this.list = this.list.filter(p => p.t < p.life);
    }
    draw(ctx) {
      ctx.save();
      for (const p of this.list) {
        const a = 1 - p.t / p.life;
        ctx.globalAlpha = Math.max(0, a);
        ctx.fillStyle = p.color;
        if (p.txt) {
          ctx.font = `800 ${p.size}px Outfit, system-ui, sans-serif`; ctx.textAlign = 'center';
          ctx.strokeStyle = 'rgba(0,0,0,.6)'; ctx.lineWidth = 4; ctx.strokeText(p.txt, p.x, p.y); ctx.fillText(p.txt, p.x, p.y);
        } else if (p.shape === 'square') {
          ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
        } else {
          ctx.beginPath(); ctx.arc(p.x, p.y, p.size * (.4 + a * .6), 0, 6.283); ctx.fill();
        }
      }
      ctx.restore();
    }
    clear() { this.list = []; }
  }

  const ICON = {
    grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    restart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>',
    pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>',
    sound: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 5 6 9H3v6h3l5 4z" fill="currentColor"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/></svg>',
    mute: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 5 6 9H3v6h3l5 4z" fill="currentColor"/><path d="m16 9 6 6M22 9l-6 6"/></svg>',
    lock: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>'
  };

  /* ---------------- creación de un juego ---------------- */
  function create(cfg) {
    document.body.dataset.g = cfg.id;
    const G = { cfg, id: cfg.id, level: 1, paused: true, playing: false, started: false, assets: {}, Sound, scale: 1 };
    document.title = cfg.title + ' · Arcade 12';
    if (cfg.accent) document.documentElement.style.setProperty('--accent', cfg.accent);
    if (cfg.background) document.body.style.backgroundImage = `url("${cfg.background}")`;
    const app = document.getElementById('app');
    const hud = h('div', { class: 'hud' });
    const soundBtn = h('button', { class: 'ib', title: 'Sonido (M)', html: muted ? ICON.mute : ICON.sound, onclick: () => toggleSound() });
    const top = h('header', { class: 'topbar' },
      h('div', { class: 'title' }, cfg.title),
      hud,
      h('div', { class: 'tools' },
        h('button', { class: 'ib', title: 'Pausa (Esc)', html: ICON.pause, onclick: () => pause() }),
        h('button', { class: 'ib', title: cfg.typing ? 'Reiniciar nivel' : 'Reiniciar nivel (R)', html: ICON.restart, onclick: () => restart() }),
        h('button', { class: 'ib', title: 'Niveles', html: ICON.grid, onclick: () => { Sound.play('click'); showLevels(); } })));
    const sndDock = h('div', { class: 'snd-dock' }, soundBtn);
    const stage = h('main', { class: 'stage' });
    const ov = h('div', { class: 'overlay' }, h('div', { class: 'loading' }, 'CARGANDO…'));
    const toastEl = h('div', { class: 'toast' });
    app.append(top, stage, ov, toastEl, sndDock);
    G.stage = stage;

    function toggleSound() { Sound.init(); Sound.setMuted(!muted); soundBtn.innerHTML = muted ? ICON.mute : ICON.sound; }
    function setPaused(p) { if (G.paused === p) return; G.paused = p; cfg.onPause && cfg.onPause(p, G); }
    function showPanel(children, cls) {
      ov.innerHTML = '';
      ov.append(h('div', { class: 'panel ' + (cls || '') }, ...children));
      ov.classList.remove('hidden');
      setPaused(true);
    }
    function hidePanel() { ov.classList.add('hidden'); setPaused(false); }
    const panelOpen = () => !ov.classList.contains('hidden');
    const helpBlock = () => h('ul', { class: 'help' }, ...(cfg.help || []).map(t => h('li', { html: t })));
    const statsBlock = stats => h('div', { class: 'stats' }, ...(stats || []).map(([k, v]) => h('div', {}, h('span', {}, k), h('b', {}, String(v)))));

    function showTitle() {
      G.playing = false;
      showPanel([
        h('img', { class: 'cover', src: `../assets/covers/${cfg.id}.webp`, alt: '' }),
        h('div', { class: 'kicker' }, cfg.genre || ''),
        h('h1', {}, cfg.title),
        h('p', { class: 'lead' }, cfg.tagline || ''),
        helpBlock(),
        h('div', { class: 'meta' }, `★ ${totalStars(cfg.id)} / ${cfg.levels * 3}  ·  ${cfg.levels} niveles`),
        h('div', { class: 'row full' }, h('button', { class: 'btn primary', onclick: () => { Sound.init(); Sound.play('click'); showLevels(); } }, 'Jugar'))
      ]);
    }
    function showLevels() {
      G.playing = false;
      const p = progress(cfg.id);
      const grid = h('div', { class: 'levels' });
      for (let i = 1; i <= cfg.levels; i++) {
        const locked = i > p.unlocked, s = p.stars[i] || 0;
        grid.append(h('button', {
          class: 'lv' + (locked ? ' locked' : '') + (s ? ' done' : ''), disabled: locked,
          onclick: () => { Sound.init(); Sound.play('click'); start(i); }
        }, locked ? h('b', { html: ICON.lock }) : h('b', {}, String(i)), h('small', {}, '★'.repeat(s) + '☆'.repeat(3 - s))));
      }
      showPanel([h('div', { class: 'kicker' }, cfg.title), h('h2', {}, 'Elige un nivel'),
        h('p', { class: 'lead' }, 'Supera un nivel para desbloquear el siguiente.'), grid,
        h('div', { class: 'row' }, h('button', { class: 'btn', onclick: () => { Sound.play('click'); showTitle(); } }, 'Cómo jugar'))]);
    }
    function start(n) {
      G.level = n; G.playing = true; G.started = true;
      hud.innerHTML = ''; hud._keys = null;
      Sound.init();
      cfg.onLevel(n, G);
      hidePanel();
    }
    function restart() { if (G.started) { Sound.play('click'); start(G.level); } }
    function pause() {
      if (!G.playing || panelOpen()) return;
      Sound.play('click');
      showPanel([h('div', { class: 'kicker' }, `${cfg.title} · Nivel ${G.level}`), h('h2', {}, 'Pausa'), helpBlock(),
        h('div', { class: 'row' },
          h('button', { class: 'btn primary', onclick: () => hidePanel() }, 'Continuar'),
          h('button', { class: 'btn', onclick: () => start(G.level) }, 'Reiniciar'),
          h('button', { class: 'btn', onclick: showLevels }, 'Niveles'))]);
    }

    G.win = function (stars, stats, score) {
      if (!G.playing) return;
      G.playing = false;
      stars = clamp(stars | 0, 1, 3);
      record(cfg.id, G.level, stars, score);
      Sound.play('win');
      const last = G.level >= cfg.levels;
      const st = h('div', { class: 'stars' });
      for (let i = 0; i < 3; i++) {
        const s = h('span', { class: i < stars ? 'on' : '' }, '★');
        s.style.animationDelay = (.25 + i * .22) + 's';
        st.append(s);
        if (i < stars) setTimeout(() => Sound.play('star'), 520 + i * 220);
      }
      showPanel([h('div', { class: 'kicker' }, last ? '¡Juego completado!' : 'Nivel superado'),
        h('h1', {}, last ? '¡Eres una leyenda!' : `Nivel ${G.level}`), st, statsBlock(stats),
        h('div', { class: 'row' },
          !last ? h('button', { class: 'btn primary', onclick: () => start(G.level + 1) }, 'Siguiente nivel') : null,
          h('button', { class: last ? 'btn primary' : 'btn', onclick: () => start(G.level) }, 'Repetir'),
          h('button', { class: 'btn', onclick: showLevels }, 'Niveles'))], 'win');
    };
    G.lose = function (msg, stats) {
      if (!G.playing) return;
      G.playing = false;
      Sound.play('lose');
      showPanel([h('div', { class: 'kicker bad' }, 'Fin de la partida'), h('h1', {}, msg || '¡Casi!'), statsBlock(stats),
        h('div', { class: 'row' },
          h('button', { class: 'btn primary', onclick: () => start(G.level) }, 'Reintentar'),
          h('button', { class: 'btn', onclick: showLevels }, 'Niveles'))], 'lose');
    };
    G.hud = function (obj) {
      const keys = Object.keys(obj), sig = keys.join('|');
      if (hud._keys !== sig) {
        hud.innerHTML = ''; hud._els = {};
        keys.forEach(k => { const b = h('b'); hud.append(h('div', { class: 'chip' }, h('span', {}, k), b)); hud._els[k] = b; });
        hud._keys = sig;
      }
      keys.forEach(k => { const v = String(obj[k]); if (hud._els[k].textContent !== v) hud._els[k].textContent = v; });
    };
    let tt;
    G.toast = (msg, ms = 1500) => { toastEl.textContent = msg; toastEl.classList.add('show'); clearTimeout(tt); tt = setTimeout(() => toastEl.classList.remove('show'), ms); };
    G.sfx = n => Sound.play(n);

    G.canvas = function (w, hh) {
      if (!G.cv) { G.cv = document.createElement('canvas'); stage.prepend(G.cv); }
      if (G.cv.width !== w || G.cv.height !== hh) { G.cv.width = w; G.cv.height = hh; }
      G.ctx = G.cv.getContext('2d');
      fit();
      return G.ctx;
    };
    function fit() {
      const cv = G.cv; if (!cv) return;
      const r = stage.getBoundingClientRect();
      let other = 0;
      for (const ch of stage.children) if (ch !== cv && ch.offsetParent !== null && getComputedStyle(ch).position !== 'absolute') other += ch.offsetHeight + 12;
      const s = Math.max(.1, Math.min((r.width - 24) / cv.width, (r.height - 24 - other) / cv.height, cfg.maxScale || 1.6));
      cv.style.width = Math.floor(cv.width * s) + 'px';
      cv.style.height = Math.floor(cv.height * s) + 'px';
      G.scale = s;
    }
    G.fit = fit;
    addEventListener('resize', fit);
    G.pos = function (e) {
      const r = G.cv.getBoundingClientRect();
      return { x: (e.clientX - r.left) * G.cv.width / r.width, y: (e.clientY - r.top) * G.cv.height / r.height };
    };
    G.loop = function (update, render) {
      let last = performance.now();
      function f(t) {
        const dt = Math.min(.05, (t - last) / 1000); last = t;
        if (!G.paused && G.playing) update(dt);
        render(dt);
        requestAnimationFrame(f);
      }
      requestAnimationFrame(f);
    };
    G.keys = {};
    addEventListener('keydown', e => {
      Sound.init();
      G.keys[e.code] = true;
      if (e.key === 'Escape' || (!cfg.typing && (e.key === 'p' || e.key === 'P'))) {
        if (panelOpen()) { if (G.playing) hidePanel(); } else pause();
        e.preventDefault(); return;
      }
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) e.preventDefault();
      if (cfg.typing) return;
      if ((e.key === 'r' || e.key === 'R') && G.started && !panelOpen()) restart();
      if (e.key === 'm' || e.key === 'M') toggleSound();
    });
    addEventListener('keyup', e => { G.keys[e.code] = false; });
    addEventListener('blur', () => { G.keys = {}; if (G.playing && !panelOpen()) pause(); });
    addEventListener('pointerdown', () => Sound.init(), { capture: true });

    /* botones táctiles: [{label, code}] — simulan teclas */
    G.touch = function (left, right) {
      const mk = list => h('div', { class: 'grp' }, ...list.map(b => {
        const el = h('button', { html: b.label });
        const on = e => { e.preventDefault(); G.keys[b.code] = true; el.classList.add('on'); b.down && b.down(); };
        const off = e => { e.preventDefault(); G.keys[b.code] = false; el.classList.remove('on'); };
        el.addEventListener('pointerdown', on); el.addEventListener('pointerup', off); el.addEventListener('pointerleave', off); el.addEventListener('pointercancel', off);
        return el;
      }));
      document.body.append(h('div', { class: 'touch' }, mk(left || []), mk(right || [])));
    };
    G.swipe = function (el, cb) {
      let sx, sy, id = null;
      el.addEventListener('pointerdown', e => { sx = e.clientX; sy = e.clientY; id = e.pointerId; });
      el.addEventListener('pointerup', e => {
        if (id !== e.pointerId) return; id = null;
        const dx = e.clientX - sx, dy = e.clientY - sy;
        if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
        if (Math.abs(dx) > Math.abs(dy)) cb(dx > 0 ? 1 : -1, 0); else cb(0, dy > 0 ? 1 : -1);
      });
    };

    loadImages(cfg.assets || {}).then(a => {
      G.assets = a;
      cfg.onReady && cfg.onReady(G);
      showTitle();
    });
    return G;
  }

  window.Engine = { create, Sound, rng, clamp, lerp, ease, Particles, loadImages, progress, totalStars };
})();
