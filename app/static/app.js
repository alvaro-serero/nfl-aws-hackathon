// Chip Advisor frontend: controls -> /api/advice (verdict, bars, real plays) -> /api/play (animated field).
const $ = (s) => document.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
const SITS = [["all", "Toutes"], ["early", "1er/2e down"], ["short", "3e/4e court"], ["long", "3e/4e long"]];
const SIT_TXT = { all: "Toutes situations", early: "1er ou 2e down", short: "3e ou 4e et court", long: "3e ou 4e et long" };
const QS = ["Faible", "Moyen", "Bon", "Élite"].map((q) => [q, q]);
const PLAYERS = [["TE", "TE"], ["RB", "RB"]];
const COLORS = { off: "#2E6BD6", def: "#EC7A2F", chalk: "#F3F6F1", ink: "#13212E", yellow: "#FFD23F", red: "#E5484D", los: "#4C8DF6" };
const state = { sit: "all", q: "Élite", player: "TE", rusher: "", play: null, advice: null };
let RUSHERS = {};  // name -> quartile
const paint = {};
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const fr = (x, d = 1) => (x == null ? "–" : x.toFixed(d).replace(".", ","));
const pct = (x) => (x == null ? "–" : `${fr(100 * x)} %`);

function svg(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

// ---------- Controls ----------
function seg(id, items, key) {
  const box = $(id);
  box.innerHTML = items.map(([v, l]) => `<button type="button" data-v="${v}">${l}</button>`).join("");
  paint[key] = () => box.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(state[key] === b.dataset.v)));
  box.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    state[key] = b.dataset.v;
    if (key === "q") { state.rusher = ""; $("#rusher").value = ""; }
    paint[key]();
    loadAdvice();
  });
  paint[key]();
}

async function init() {
  seg("#sit", SITS, "sit");
  seg("#q", QS, "q");
  seg("#player", PLAYERS, "player");
  RUSHERS = (await (await fetch("/static/data/meta.json")).json()).rushers;
  $("#rushers").innerHTML = Object.keys(RUSHERS).map((n) => `<option value="${n}">`).join("");
  $("#rusher").addEventListener("change", (e) => {
    const v = e.target.value.trim();
    state.rusher = RUSHERS[v] ? v : "";
    if (state.rusher) state.q = RUSHERS[v];
    loadAdvice();
  });
  $("#brief-btn").addEventListener("click", brief);
  setupTransport();
  loadAdvice();
}

// ---------- Verdict ----------
async function loadAdvice() {
  const qi = QS.findIndex(([q]) => q === state.q);
  const a = await (await fetch(`/static/data/advice/${state.sit}_${qi}_${state.player}.json`)).json();
  if (a.error) { $("#v-title").textContent = "Données indisponibles"; $("#v-sub").textContent = a.error; return; }
  state.advice = a;
  state.q = a.quartile;
  paint.q();
  renderVerdict(a);
  renderBars(a);
  renderPlays(a.plays);
}

function renderVerdict(a) {
  const v = a.verdict, P = state.player;
  $("#context").textContent = `${SIT_TXT[state.sit]}, face à un rusher ${a.quartile.toLowerCase()}${state.rusher ? ` (${state.rusher})` : ""}`;
  const t = $("#v-title");
  t.textContent = v.chip ? `Chip ${P}, contact ${v.length === "long" ? "long" : "court"}` : "Pas de chip";
  t.classList.toggle("no", !v.chip);
  $("#v-sub").textContent = !v.chip
    ? `Envoyez le ${P} directement en route : ici, le chip ne réduit pas la pression.`
    : v.length === "long"
      ? `Gardez le contact plus de 0,6 s, puis partez en route (vers ${fr(v.release)} s).`
      : `Un coup bref suffit, il part en route plus tôt (vers ${fr(v.release)} s).`;
  $("#n-before").textContent = pct(v.base);
  $("#n-after").textContent = pct(v.mine);
  $("#l-after").textContent = `avec chip ${P}`;
  $("#planb").hidden = !v.chip;
  $("#planb-text").textContent = `Rien d’ouvert ? Lancez au ${P} qui a chippé. Sur 88 sacks avec chip, il était libre 36 fois.`;
  const w = $("#warn");
  w.hidden = !v.fragile;
  w.textContent = `Seulement ${v.n} snaps comparables : c’est une tendance, pas une certitude.`;
  $("#brief-text").hidden = true;
  $("#brief-src").textContent = "";
}

function renderBars(a) {
  const v = a.verdict;
  const picks = v.chip ? [state.player, v.length] : ["none"];
  const max = Math.max(0.05, ...a.options.map((r) => r.hi ?? r.rate ?? 0));
  const w = (x) => (x == null ? 0 : (100 * x) / max);
  $("#bars").innerHTML = a.options.map((r) => `
    <div class="row${picks.includes(r.key) ? " pick" : ""}">
      <span>${r.label}</span>
      <div class="track"><div class="fill" style="width:${w(r.rate)}%"></div>
        ${r.n ? `<div class="ci" style="left:${w(r.lo)}%;width:${w(r.hi) - w(r.lo)}%"></div>` : ""}</div>
      <span class="val">${pct(r.rate)}<small>n=${r.n}</small></span>
    </div>`).join("");
}

async function brief() {
  const a = state.advice, v = a.verdict, btn = $("#brief-btn");
  const title = $("#v-title").textContent, sub = $("#v-sub").textContent;
  const planb = v.chip ? $("#planb-text").textContent : "";
  const facts = [`Situation : ${$("#context").textContent}.`, `Recommandation : ${title}. ${sub}`,
    `Pression du rusher visé : ${pct(v.base)} sans chip, ${pct(v.mine)} avec chip ${state.player} (n=${v.n}).`, planb,
    ...a.options.map((r) => `${r.label} : ${pct(r.rate)} (n=${r.n})`)].join("\n");
  btn.disabled = true; btn.textContent = "Rédaction…";
  try {
    const r = await (await fetch("/api/brief", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ facts, fallback: `${title}. ${sub} ${planb}`.trim() }) })).json();
    $("#brief-text").textContent = r.text;
    $("#brief-text").hidden = false;
    $("#brief-src").textContent = r.source.startsWith("Mistral") ? `Rédigé par ${r.source}` : `Texte automatique : ${r.source}`;
  } finally {
    btn.disabled = false; btn.textContent = "Rédiger le briefing";
  }
}

// ---------- Real plays ----------
function renderPlays(plays) {
  const box = $("#plays");
  if (!plays.length) { box.innerHTML = `<p class="empty">Aucune action filmée pour ce choix.</p>`; return; }
  box.innerHTML = plays.map((p, i) => `
    <button type="button" class="play" data-i="${i}">
      <b>${p.title}</b><span>${p.sit}</span><em class="badge ${p.kind}">${p.badge}</em>
    </button>`).join("");
  box.onclick = (e) => { const b = e.target.closest(".play"); if (b) selectPlay(plays[+b.dataset.i]); };
  const keep = state.play && plays.find((p) => p.g === state.play.g && p.p === state.play.p && p.chipper === state.play.chipper);
  selectPlay(keep || plays[0]);
}

async function selectPlay(p) {
  const same = state.play && state.play.g === p.g && state.play.p === p.p && state.play.chipper === p.chipper;
  state.play = p;
  document.querySelectorAll(".play").forEach((b, i) => {
    const q = state.advice.plays[i];
    b.setAttribute("aria-pressed", String(q.g === p.g && q.p === p.p && q.chipper === p.chipper));
  });
  if (same && F.data) return;
  $("#play-title").textContent = "Chargement de l’action…";
  const d = await (await fetch(`/static/data/plays/${p.g}_${p.p}_${p.chipper}.json`)).json();
  if (d.error) { $("#play-title").textContent = "Action indisponible"; $("#play-sub").textContent = d.error; return; }
  setupField(d);
}

// ---------- Field ----------
const F = { data: null, t: 0, t0: 0, t1: 1, playing: false, speed: 1, last: 0 };
let XMAX = 0;
const sx = (y) => (53.3 - y) * 10;   // end-zone view: offense's left on screen left
const sy = (x) => (XMAX - x) * 10;   // offense moves up the screen

function setupField(d) {
  F.data = d;
  const m = d.meta, root = $("#field");
  XMAX = m.los + 22;
  const xmin = XMAX - 34;
  root.innerHTML = "";
  $("#play-title").textContent = m.title;
  $("#play-sub").textContent = m.sub;

  const turf = svg("g", {}, root);
  for (let x = Math.floor(xmin / 5) * 5; x < XMAX; x += 5) {
    const endzone = x < 10 || x >= 110;
    svg("rect", { x: 0, y: sy(x + 5), width: 533, height: 50, fill: endzone ? "#184C30" : (x / 5) % 2 ? "#1F5E3A" : "#236840" }, turf);
  }
  for (let x = Math.ceil(xmin); x <= XMAX; x++) {
    if (x < 10 || x > 110) continue;
    if (x % 5 === 0) {
      svg("line", { x1: 0, x2: 533, y1: sy(x), y2: sy(x), stroke: COLORS.chalk, "stroke-opacity": 0.55, "stroke-width": x === 10 || x === 110 ? 3 : 1.5 }, turf);
    } else {
      for (const y of [0.9, 23.58, 29.73, 52.4]) {
        svg("line", { x1: sx(y) - 3, x2: sx(y) + 3, y1: sy(x), y2: sy(x), stroke: COLORS.chalk, "stroke-opacity": 0.45, "stroke-width": 1.2 }, turf);
      }
    }
    if (x % 10 === 0 && x > 10 && x < 110) {
      const n = x <= 60 ? x - 10 : 110 - x;
      for (const [y, rot] of [[12, 90], [41.3, -90]]) {
        const t = svg("text", { x: sx(y), y: sy(x), transform: `rotate(${rot} ${sx(y)} ${sy(x)})`, "text-anchor": "middle",
          "dominant-baseline": "central", fill: COLORS.chalk, "fill-opacity": 0.4, "font-size": 22, "font-weight": 700, "font-family": "Barlow Condensed" }, turf);
        t.textContent = n;
      }
    }
  }
  svg("line", { x1: 0, x2: 533, y1: sy(m.los), y2: sy(m.los), stroke: COLORS.los, "stroke-width": 3 }, turf);
  if (m.fd < XMAX) svg("line", { x1: 0, x2: 533, y1: sy(m.fd), y2: sy(m.fd), stroke: COLORS.yellow, "stroke-width": 3 }, turf);

  const idx = (role) => d.players.findIndex((p) => p.role === role);
  F.ci = idx("chipper"); F.ri = idx("rusher"); F.qi = idx("qb");
  F.defs = d.players.map((p, i) => (p.side === "def" ? i : -1)).filter((i) => i >= 0);
  F.trails = {};
  const trails = svg("g", { fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round" }, root);
  for (const [i, color, dash] of [[F.qi, COLORS.chalk, "4 5"], [F.ri, COLORS.red, ""], [F.ci, COLORS.yellow, ""]]) {
    if (i >= 0) F.trails[i] = svg("polyline", { stroke: color, "stroke-width": 3, "stroke-opacity": 0.85, "stroke-dasharray": dash }, trails);
  }
  F.link = svg("line", { stroke: COLORS.yellow, "stroke-width": 5, "stroke-linecap": "round", opacity: 0 }, root);

  const layer = svg("g", { "font-family": "Barlow Condensed", "font-weight": 700, "text-anchor": "middle", "dominant-baseline": "central" }, root);
  F.nodes = d.players.map((p) => {
    const g = svg("g", {}, layer);
    if (p.role === "chipper" || p.role === "rusher" || p.role === "qb") {
      svg("circle", { r: 16, fill: "none", stroke: p.role === "chipper" ? COLORS.yellow : p.role === "rusher" ? COLORS.red : COLORS.chalk, "stroke-width": 3.5 }, g);
    }
    if (p.side === "off") svg("circle", { r: 11, fill: COLORS.off, stroke: COLORS.chalk, "stroke-width": 1.5 }, g);
    else svg("rect", { x: -10.5, y: -10.5, width: 21, height: 21, rx: 5, fill: COLORS.def, stroke: COLORS.chalk, "stroke-width": 1.5 }, g);
    const t = svg("text", { "font-size": 12, fill: p.side === "off" ? "#FFFFFF" : COLORS.ink }, g);
    t.textContent = p.num;
    return g;
  });
  F.ball = svg("ellipse", { rx: 3.5, ry: 5.5, fill: "#8B5A2B", stroke: COLORS.chalk, "stroke-width": 1 }, root);

  const tags = svg("g", { "font-family": "Barlow", "font-weight": 600, "font-size": 13, "paint-order": "stroke", stroke: COLORS.ink, "stroke-width": 4, "stroke-linejoin": "round" }, root);
  const chipper = d.players[F.ci], tagText = { [F.ci]: `${chipper?.pos || ""} ${chipper?.num ?? ""}`, [F.ri]: "Rusher visé", [F.qi]: "QB" };
  F.tags = {};
  for (const i of [F.ci, F.ri, F.qi]) {
    if (i < 0) continue;
    F.tags[i] = svg("text", { fill: i === F.ci ? COLORS.yellow : i === F.ri ? "#FF8A8D" : COLORS.chalk }, tags);
    F.tags[i].textContent = tagText[i];
  }
  F.open = svg("text", { fill: COLORS.ink, "font-size": 14, "font-weight": 700, "font-family": "Barlow", "text-anchor": "middle" }, root);
  F.openBg = svg("rect", { rx: 6, fill: COLORS.yellow }, root);
  root.insertBefore(F.openBg, F.open);

  F.t0 = d.frames[0].t; F.t1 = d.frames[d.frames.length - 1].t;
  const scrub = $("#scrub");
  scrub.min = F.t0; scrub.max = F.t1;
  const at = (t) => `${(100 * (t - F.t0)) / (F.t1 - F.t0)}%`;
  const band = $("#band");
  band.hidden = m.chip_start == null;
  if (m.chip_start != null) { band.style.left = at(m.chip_start); band.style.width = `calc(${at(m.release)} - ${at(m.chip_start)})`; }
  const chipMid = m.chip_start == null ? null : (m.chip_start + m.release) / 2;
  const ticks = [[0, "Snap", "up"], [chipMid, "Chip", "down"], [m.end_t, m.end_label, "up"]];
  $("#ticks").innerHTML = ticks.filter(([t]) => t != null)
    .map(([t, l, row]) => `<button type="button" class="tick ${row}" data-t="${t}" style="left:${at(t)}">${l}</button>`).join("");
  F.t = F.t0;
  draw();
  if (!reduceMotion) start();
}

function posAt(t, get) {
  const fr_ = F.data.frames, k = (t - fr_[0].t) * 10;
  const a = Math.max(0, Math.min(fr_.length - 1, Math.floor(k))), b = Math.min(fr_.length - 1, a + 1), u = Math.max(0, Math.min(1, k - a));
  const pa = get(fr_[a]), pb = get(fr_[b]);
  if (!pa || !pb) return pa || pb;
  return [pa[0] + (pb[0] - pa[0]) * u, pa[1] + (pb[1] - pa[1]) * u];
}

function draw() {
  const d = F.data, m = d.meta, t = F.t;
  const pos = d.players.map((_, i) => posAt(t, (f) => f.p[i]));
  pos.forEach((p, i) => {
    F.nodes[i].setAttribute("visibility", p ? "visible" : "hidden");
    if (p) F.nodes[i].setAttribute("transform", `translate(${sx(p[1])} ${sy(p[0])})`);
  });
  const b = posAt(t, (f) => f.b);
  F.ball.setAttribute("visibility", b ? "visible" : "hidden");
  if (b) { F.ball.setAttribute("cx", sx(b[1])); F.ball.setAttribute("cy", sy(b[0])); }

  const last = Math.max(0, Math.min(d.frames.length - 1, Math.floor((t - F.t0) * 10)));
  for (const i in F.trails) {
    const pts = [];
    for (let k = 0; k <= last; k++) { const p = d.frames[k].p[i]; if (p) pts.push(`${sx(p[1])},${sy(p[0])}`); }
    if (pos[i]) pts.push(`${sx(pos[i][1])},${sy(pos[i][0])}`);
    F.trails[i].setAttribute("points", pts.join(" "));
  }
  // Tags sit on the outer side of the ball so they don't cover the line.
  const mid = b ? sx(b[1]) : 266;
  for (const i in F.tags) {
    const p = pos[i];
    F.tags[i].setAttribute("visibility", p ? "visible" : "hidden");
    if (!p) continue;
    const x = sx(p[1]), left = i == F.qi ? false : x < mid;
    F.tags[i].setAttribute("text-anchor", left ? "end" : "start");
    F.tags[i].setAttribute("x", left ? x - 20 : x + 20);
    F.tags[i].setAttribute("y", sy(p[0]) + (i == F.ri ? -14 : i == F.ci ? 18 : 5));
  }

  const c = pos[F.ci], r = pos[F.ri];
  const inChip = m.chip_start != null && t >= m.chip_start - 0.1 && t <= m.release + 0.1;
  const touching = c && r && inChip && Math.hypot(c[0] - r[0], c[1] - r[1]) < 1.8;
  F.link.setAttribute("opacity", touching ? 0.9 : 0);
  if (touching) { F.link.setAttribute("x1", sx(c[1])); F.link.setAttribute("y1", sy(c[0])); F.link.setAttribute("x2", sx(r[1])); F.link.setAttribute("y2", sy(r[0])); }

  // Is the chipper open? Nearest defender >= 3 yd, past the line, after his release.
  let sep = Infinity;
  if (c) for (const i of F.defs) { const p = pos[i]; if (p) sep = Math.min(sep, Math.hypot(c[0] - p[0], c[1] - p[1])); }
  const open = c && m.release != null && t > m.release && c[0] > m.los && sep >= 3;
  F.open.setAttribute("visibility", open ? "visible" : "hidden");
  F.openBg.setAttribute("visibility", open ? "visible" : "hidden");
  if (open) {
    F.open.textContent = `Libre, ${fr(sep)} yd`;
    const x = sx(c[1]), y = sy(c[0]) - 26;
    F.open.setAttribute("x", x); F.open.setAttribute("y", y + 5);
    const w = F.open.getComputedTextLength() + 14;
    F.openBg.setAttribute("x", x - w / 2); F.openBg.setAttribute("y", y - 10); F.openBg.setAttribute("width", w); F.openBg.setAttribute("height", 21);
  }

  const chipper = d.players[F.ci];
  const phase = $("#phase");
  let label = "Avant le snap", hot = false;
  if (t >= m.end_t) { label = m.end_label; hot = true; }
  else if (m.chip_start != null && t >= m.chip_start && t <= m.release) { label = "Chip en cours"; hot = true; }
  else if (m.release != null && t > m.release) label = open ? `${chipper.pos} libre` : `${chipper.pos} en route`;
  else if (t >= 0) label = "Snap";
  phase.textContent = label;
  phase.classList.toggle("hot", hot);
  $("#scrub").value = t;
  $("#clock").textContent = `${t < 0 ? "−" : ""}${fr(Math.abs(t))} s`;
}

// ---------- Transport ----------
const ICON_PLAY = `<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2l12 7-12 7z" fill="currentColor"/></svg>`;
const ICON_PAUSE = `<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2h4v14H4zM10 2h4v14h-4z" fill="currentColor"/></svg>`;

function paintButton() {
  const b = $("#playpause");
  b.innerHTML = F.playing ? ICON_PAUSE : ICON_PLAY;
  b.setAttribute("aria-label", F.playing ? "Pause" : "Lecture");
}
function frame(now) {
  if (!F.playing) return;
  F.t = Math.min(F.t1, F.t + ((now - F.last) / 1000) * F.speed);
  F.last = now;
  draw();
  if (F.t >= F.t1) { F.playing = false; paintButton(); return; }
  requestAnimationFrame(frame);
}
function start() {
  if (!F.data) return;
  if (F.t >= F.t1) F.t = F.t0;
  F.playing = true; F.last = performance.now();
  paintButton();
  requestAnimationFrame(frame);
}
function stop() { F.playing = false; paintButton(); }

function setupTransport() {
  paintButton();
  $("#playpause").addEventListener("click", () => (F.playing ? stop() : start()));
  $("#scrub").addEventListener("input", (e) => { stop(); F.t = +e.target.value; draw(); });
  $("#ticks").addEventListener("click", (e) => { const b = e.target.closest(".tick"); if (b) { stop(); F.t = +b.dataset.t; draw(); } });
  $("#speed").addEventListener("click", (e) => {
    F.speed = F.speed === 1 ? 0.5 : F.speed === 0.5 ? 0.25 : 1;
    e.target.textContent = `Vitesse ${fr(F.speed, F.speed === 0.25 ? 2 : F.speed === 1 ? 0 : 1)}×`;
  });
  document.addEventListener("keydown", (e) => {
    if (e.code !== "Space" || e.target.closest("input, button")) return;
    e.preventDefault();
    F.playing ? stop() : start();
  });
}

init();
