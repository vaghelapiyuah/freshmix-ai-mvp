"use strict";
const API = () => window.FRESHMIX_API;
const MOODS = ["Focus", "Gym", "Chill", "Travel", "Happy", "Sad"];
const ACTS = ["Work", "Commute", "Workout", "Study", "Relax"];

const $ = (id) => document.getElementById(id);
const state = { moods: new Set(["Focus"]), acts: new Set(), queue: [] };

// ---- taste profile (previously listened songs), persisted in the browser ----
const taste = load("freshmix_taste", { g: {}, a: {}, fs: {}, fn: 0 });
const saved = new Set(load("freshmix_saved", []));
const recent = load("freshmix_recent", []);

function load(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }
function save(k, v) { localStorage.setItem(k, JSON.stringify(v)); }
function topK(o, k) { return Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, k).map((x) => x[0]); }
function tasteVector() {
  if (!taste.fn) return {};
  const out = {}; for (const k in taste.fs) out[k] = +(taste.fs[k] / taste.fn).toFixed(3);
  return out;
}
function learn(t, w) {
  if (t.genre) taste.g[t.genre] = (taste.g[t.genre] || 0) + w;
  if (t.artist) taste.a[t.artist] = (taste.a[t.artist] || 0) + w;
  for (const k of ["energy", "valence", "tempo"]) if (t[k] != null) taste.fs[k] = (taste.fs[k] || 0) + t[k] * w;
  taste.fn += w; save("freshmix_taste", taste);
}
function showTaste() {
  const g = topK(taste.g, 3);
  $("taste").textContent = g.length ? "🎧 Tuned to your listening: " + g.join(", ") : "";
}

// ---- chips ----
function chips(host, items, set) {
  host.innerHTML = "";
  items.forEach((m) => {
    const b = document.createElement("button");
    b.className = "chip" + (set.has(m) ? " active" : "");
    b.textContent = m;
    b.onclick = () => { set.has(m) ? set.delete(m) : set.add(m); b.classList.toggle("active"); };
    host.appendChild(b);
  });
}

function payload(extra) {
  return Object.assign({
    free_text: $("prompt").value.trim(),
    moods: [...state.moods], activities: [...state.acts],
    freshness: +$("fresh").value,
    recent_track_ids: recent.slice(-40), saved_track_ids: [...saved],
    taste_genres: topK(taste.g, 3), taste_artists: topK(taste.a, 3),
    taste_vector: tasteVector(),
  }, extra || {});
}

async function api(path, body) {
  const r = await fetch(API() + path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

// ---- render ----
function card(item, idx) {
  const t = item.track;
  const el = document.createElement("div");
  el.className = "card" + (saved.has(t.id) ? " saved" : "");
  const art = t.artwork_url || "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='72' height='72'><rect width='72' height='72' fill='%231f1f1f'/><text x='36' y='44' font-size='30' text-anchor='middle'>🎵</text></svg>";
  const title = t.url ? `<a class="title" href="${t.url}" target="_blank" rel="noopener">${esc(t.name)}</a>`
    : `<span class="title">${esc(t.name)}</span>`;
  const tag = t.new_artist ? `<span class="tag fresh">✨ fresh find</span>` : `<span class="tag">familiar</span>`;
  const audio = t.preview_url ? `<audio controls preload="none" src="${t.preview_url}"></audio>` : "";
  el.innerHTML = `
    <img class="art" src="${art}" alt="" loading="lazy"/>
    <div class="meta">
      ${title}
      <div class="artist">${esc(t.artist)} · ${esc(t.genre || "Music")}</div>
      <div class="why">${esc(item.reason || "")}</div>
      ${tag} ${audio}
    </div>
    <div class="acts">
      <button class="save ${saved.has(t.id) ? "on" : ""}">${saved.has(t.id) ? "Saved" : "Save"}</button>
      <button class="skip">Skip</button>
    </div>`;
  el.querySelector(".save").onclick = () => { saved.add(t.id); save("freshmix_saved", [...saved]); learn(t, 2.0); render(); showTaste(); };
  el.querySelector(".skip").onclick = () => replace(idx, t.id);
  return el;
}
function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

function render() {
  const host = $("results"); host.innerHTML = "";
  if (!state.queue.length) { host.innerHTML = `<p class="empty">Pick a mood and tap <b>Generate FreshMix</b>.</p>`; return; }
  state.queue.forEach((it, i) => host.appendChild(card(it, i)));
}

async function generate() {
  $("go").disabled = true; $("status").textContent = "Mixing your fresh queue…";
  const slow = setTimeout(() => { $("status").textContent = "Waking the server (first request can take ~30s)…"; }, 3500);
  try {
    const q = await api("/v1/freshmix/generate", payload());
    clearTimeout(slow);
    state.queue = q.items || [];
    for (const it of state.queue) { const id = it.track.id; if (!recent.includes(id)) recent.push(id); learn(it.track, 0.5); }
    save("freshmix_recent", recent.slice(-60));
    $("status").textContent = `${q.freshness_applied ?? $("fresh").value}% fresh · ${q.note || ""}`.trim();
    render(); showTaste();
  } catch (e) {
    clearTimeout(slow);
    $("status").textContent = "Couldn't reach the API. Set the backend URL with the “API” button. (" + e.message + ")";
  } finally { $("go").disabled = false; }
}

// Pre-warm the backend the moment the page opens (Render free tier sleeps), and
// keep it warm while the tab is open — so Generate feels instant.
function warm() { fetch(API() + "/v1/health", { mode: "cors" }).catch(() => {}); }
warm();
setInterval(warm, 240000);   // every 4 min

async function replace(idx, trackId) {
  const shown = state.queue.map((it) => it.track.id);
  try {
    const r = await api("/v1/freshmix/feedback", payload({ action: "skip", track_id: trackId, exclude: shown }));
    if (r.next) { state.queue[idx] = r.next; learn(r.next.track, 0.3); save("freshmix_taste", taste); render(); }
  } catch { $("status").textContent = "Refresh failed — check the API URL."; }
}

// (Backend URL comes from config.js — default Render API, overridable via ?api=)

// ---- init ----
chips($("moods"), MOODS, state.moods);
chips($("acts"), ACTS, state.acts);
$("fresh").oninput = () => $("freshVal").textContent = $("fresh").value;
$("go").onclick = generate;
showTaste(); render();
