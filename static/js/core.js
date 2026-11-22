// NOXPclips — utilitaires partagés
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function h(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

// ---------- Icônes (traits simples, 24x24) ----------
const P = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
  palette: '<path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.6-.9 1.6-1.7 0-1.2-.9-1.6-.9-2.6 0-.9.8-1.7 1.8-1.7H17a4 4 0 0 0 4-4c0-4.4-4-8-9-8Z"/><circle cx="7.5" cy="11" r="1.2"/><circle cx="10.5" cy="7" r="1.2"/><circle cx="15" cy="7.5" r="1.2"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  link: '<path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  scissors: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>',
  sparkles: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8Z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8Z"/>',
  cc: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 10.5a2.5 2.5 0 1 0 0 3M16.5 10.5a2.5 2.5 0 1 0 0 3"/>',
  zoom: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
  transition: '<path d="M4 4l16 16M20 4 4 20"/><rect x="3" y="3" width="18" height="18" rx="3"/>',
  color: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18M12 12 5.6 5.6"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  translate: '<path d="M4 5h9M8.5 3v2M6 5c.6 3.4 2.8 6 6 7.5M11 5c-.8 4-3.6 7.2-7 8.5"/><path d="m13 21 4-9 4 9M14.5 18h5"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  volume: '<path d="M11 5 6 9H3v6h3l5 4Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.9-4M4 4v4h4M4 13a8 8 0 0 0 14.9 4M20 20v-4h-4"/>',
  smile: '<circle cx="12" cy="12" r="9"/><path d="M8.5 14.5a4.5 4.5 0 0 0 7 0M9 9.5h.01M15 9.5h.01"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  hook: '<path d="M9 3v9a4 4 0 1 0 8 0v-2"/><path d="M14 7l3 3 3-3"/>',
  motion: '<circle cx="9" cy="15" r="5"/><path d="M13.5 6.5a6 6 0 0 1 4 4M16 3a9 9 0 0 1 5 5"/>',
  sfx: '<path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2"/>',
  play: '<path d="M7 4v16l13-8Z"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5"/><path d="M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1"/>',
  share: '<path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M9 7V4h6v3"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16Z"/><path d="m14 6 4 4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  up: '<path d="m6 15 6-6 6 6"/>',
  left: '<path d="m15 6-6 6 6 6"/>',
  right: '<path d="m9 6 6 6-6 6"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7Z"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
  brush: '<path d="M18 3 9 12M8 13c-2 0-4 1.5-4 4 0 1-1 2-2 2 2 2 6 2 8-1 1-1.5.5-3.5-2-5Z"/><path d="m14 7 3 3"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
  dots: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
  lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  phone: '<rect x="7" y="2" width="10" height="20" rx="2.5"/><path d="M11 18h2"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5Z"/><path d="m3 13 9 5 9-5"/>',
  send: '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4Z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  flame: '<path d="M12 22c4 0 7-2.7 7-7 0-4-3-6-4-9-1.5 2-2 3.5-2 5-1.5-1-2.5-3-2.5-5C7 8 5 11 5 15c0 4.3 3 7 7 7Z"/>',
  wand: '<path d="m15 4 5 5L8 21l-5-5Z"/><path d="m12 7 5 5M19 2v3M22 3h-3"/>',
};
const BRANDS = {
  youtube: '<svg class="i" viewBox="0 0 24 24" style="fill:currentColor;stroke:none"><path d="M23 7.2a3 3 0 0 0-2.1-2.1C19 4.6 12 4.6 12 4.6s-7 0-8.9.5A3 3 0 0 0 1 7.2 31 31 0 0 0 .5 12a31 31 0 0 0 .5 4.8 3 3 0 0 0 2.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .5-4.8 31 31 0 0 0-.5-4.8ZM9.7 15V9l5.8 3Z"/></svg>',
  tiktok: '<svg class="i" viewBox="0 0 24 24" style="fill:currentColor;stroke:none"><path d="M16.6 3c.3 2.2 1.6 3.6 3.9 3.8v3.1c-1.4.1-2.6-.3-3.9-1.1v5.9c0 7.5-8.2 9.9-11.5 4.5-2.1-3.5-.8-9.6 6-9.8v3.3c-.5.1-1.1.2-1.6.4-1.5.5-2.4 1.5-2.1 3.2.5 3.2 6.4 4.1 5.9-2.1V3Z"/></svg>',
  instagram: '<svg class="i" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".6" fill="currentColor"/></svg>',
  facebook: '<svg class="i" viewBox="0 0 24 24" style="fill:currentColor;stroke:none"><path d="M14 8h3V4h-3c-2.8 0-4.5 1.8-4.5 4.6V11H7v4h2.5v9h4v-9h3l.5-4h-3.5V8.8c0-.5.3-.8.5-.8Z"/></svg>',
  x: '<svg class="i" viewBox="0 0 24 24" style="fill:currentColor;stroke:none"><path d="M17.7 3h3.1l-6.8 7.7L22 21h-6.2l-4.9-6.4L5.3 21H2.2l7.3-8.3L2 3h6.4l4.4 5.8Zm-1.1 16.2h1.7L7.5 4.7H5.7Z"/></svg>',
  other: '<svg class="i" viewBox="0 0 24 24"><path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg>',
};
export function icon(name, cls = "") {
  if (BRANDS[name]) return BRANDS[name].replace('class="i"', `class="i ${cls}"`);
  return `<svg class="i ${cls}" viewBox="0 0 24 24">${P[name] || P.info}</svg>`;
}

export const PLATFORMS = {
  youtube: { name: "YouTube Shorts", short: "YouTube" },
  tiktok: { name: "TikTok", short: "TikTok" },
  instagram: { name: "Instagram Reels", short: "Instagram" },
  facebook: { name: "Facebook Reels", short: "Facebook" },
  x: { name: "X (Twitter)", short: "X" },
};

// ---------- API ----------
export class ApiError extends Error {}
export async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {}, credentials: "same-origin" };
  if (opts.body instanceof FormData) init.body = opts.body;
  else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    init.headers["Content-Type"] = "application/json";
  }
  const r = await fetch(path, init);
  if (r.status === 401 && path !== "/api/login") {
    window.dispatchEvent(new Event("noxp-auth"));
    throw new ApiError("Connexion requise");
  }
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new ApiError((data && data.detail) || `Erreur ${r.status}`);
  return data;
}

export function uploadWithProgress(path, file, onProgress, field = "file") {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let data = null;
      try { data = JSON.parse(xhr.responseText); } catch { data = xhr.responseText; }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError((data && data.detail) || `Erreur ${xhr.status}`));
    };
    xhr.onerror = () => reject(new ApiError("Erreur réseau pendant l'envoi"));
    const fd = new FormData();
    fd.append(field, file);
    xhr.send(fd);
  });
}

// ---------- Toasts / modales ----------
export function toast(msg, kind = "") {
  const el = h(`<div class="toast ${kind}">${esc(msg)}</div>`);
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "err" ? 6500 : 3500);
}

export function modal(html, { wide = false, onClose } = {}) {
  const back = h(`<div class="modal-back"><div class="modal ${wide ? "wide" : ""}">${html}</div></div>`);
  const close = () => {
    back.remove();
    document.removeEventListener("keydown", onKey);
    onClose && onClose();
  };
  const onKey = (e) => e.key === "Escape" && close();
  back.addEventListener("click", (e) => {
    if (e.target === back || e.target.closest("[data-close]")) close();
  });
  document.addEventListener("keydown", onKey);
  document.body.append(back);
  return { el: back.querySelector(".modal"), close };
}

export function confirmBox(msg, okLabel = "Confirmer", danger = true) {
  return new Promise((resolve) => {
    const m = modal(`<h2>${esc(msg)}</h2><div class="modal-foot"><button class="btn" data-close>Annuler</button>
      <button class="btn ${danger ? "danger" : "primary"}" id="ok">${esc(okLabel)}</button></div>`, { onClose: () => resolve(false) });
    $("#ok", m.el).onclick = () => { resolve(true); m.close(); };
  });
}

// ---------- Formats ----------
export function fmtDur(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  const hh = Math.floor(sec / 3600), mm = Math.floor((sec % 3600) / 60), ss = sec % 60;
  return hh ? `${hh}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}` : `${mm}:${String(ss).padStart(2, "0")}`;
}
export function fmtClock(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  const hh = Math.floor(sec / 3600), mm = Math.floor((sec % 3600) / 60), ss = sec % 60;
  return `${hh}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}
export function parseClock(s) {
  const parts = String(s).trim().split(":").map(Number);
  if (parts.some(isNaN)) return null;
  return parts.reduce((acc, v) => acc * 60 + v, 0);
}
export function fmtDate(ts, opts = { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) {
  return new Date(ts * 1000).toLocaleString("fr-FR", opts);
}
export function toLocalInput(ts) {
  const d = new Date(ts * 1000);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
export function fromLocalInput(v) {
  return Math.round(new Date(v).getTime() / 1000);
}
export const STATUS_LABELS = {
  scheduled: "Programmé", reminder: "Rappel", due: "À publier", publishing: "Envoi…", published: "Publié",
  scheduled_on_platform: "Programmé sur YouTube", failed: "Échec",
};

export async function copyText(t) {
  try { await navigator.clipboard.writeText(t); toast("Copié ✔", "ok"); }
  catch { toast("Copie impossible sur cet appareil", "err"); }
}

export function toggle(id, checked, attrs = "") {
  return `<label class="toggle"><input type="checkbox" id="${id}" ${checked ? "checked" : ""} ${attrs}><span></span></label>`;
}

// ---------- Routeur ----------
const routes = [];
export function route(pattern, render) {
  const keys = [];
  const re = new RegExp("^" + pattern.replace(/:(\w+)/g, (_, k) => (keys.push(k), "([^/]+)")) + "$");
  routes.push({ re, keys, render });
}
let cleanup = null;
export function onLeave(fn) { cleanup = fn; }
export async function router() {
  const raw = location.hash.slice(1) || "/";
  const [path, qs] = raw.split("?");
  const query = Object.fromEntries(new URLSearchParams(qs || ""));
  if (cleanup) { try { cleanup(); } catch {} cleanup = null; }
  for (const r of routes) {
    const m = path.match(r.re);
    if (m) {
      const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
      window.dispatchEvent(new CustomEvent("noxp-route", { detail: path }));
      const view = $("#view");
      view.innerHTML = "";
      window.scrollTo(0, 0);
      try { await r.render(view, params, query); }
      catch (e) { view.innerHTML = `<div class="empty">${icon("info")}<p>${esc(e.message)}</p></div>`; }
      return;
    }
  }
  location.hash = "#/";
}
export function go(path) { location.hash = "#" + path; }

// État partagé (brouillon de projet en cours de configuration)
export const store = { draft: null, settings: null, accounts: null };
