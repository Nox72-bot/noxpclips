import { $, $$, api, esc, fmtClock, fmtDur, go, icon, parseClock, store, toast, toggle } from "./core.js";
import { RECIPES } from "./home.js";

export const GENRES = [
  ["auto", "⚡", "Laisser l'IA détecter"], ["gaming", "🎮", "Gaming"], ["lifestyle", "🏡", "Style de vie"],
  ["sports", "🏅", "Sports"], ["marketing", "📈", "Marketing & Webinaire"], ["entertainment", "🎨", "Divertissement"],
  ["news", "📰", "Actualités"], ["education", "📚", "Informatif & Éducatif"],
];
export const MORE_GENRES = [["podcast", "🎙️", "Podcast & Interview"], ["humor", "😂", "Humour"],
  ["reaction", "😮", "Réaction"], ["irl", "📱", "IRL / Just Chatting"]];
export const CLIP_TYPES = [["viral", "🔥", "Viraux (sûrs de marcher)"], ["funny", "😂", "Les plus drôles"],
  ["drama", "🎭", "Les plus dramatiques"], ["hype", "⚡", "Les plus épiques"]];
export const LENGTHS = [["auto", "Auto (<90s)"], ["lt30", "<30s"], ["30_59", "30s~59s"], ["60_89", "60s~89s"],
  ["90_180", "90s~3m"], ["180_300", "3m~5m"]];
export const LANGS = [["auto", "Détection auto"], ["fr", "Français"], ["en", "Anglais"], ["es", "Espagnol"],
  ["de", "Allemand"], ["it", "Italien"], ["pt", "Portugais"], ["ar", "Arabe"], ["nl", "Néerlandais"], ["ja", "Japonais"]];
export const TRANSLATE = ["anglais", "français", "espagnol", "allemand", "italien", "portugais", "arabe"];
export const LAYOUTS = [["", "Auto (IA)"], ["fill", "9:16 Remplir"], ["fit", "9:16 Fond flou"], ["split", "9:16 Facecam + jeu"]];
export const CORNERS = [["top-left", "Facecam en haut à gauche"], ["top-right", "Facecam en haut à droite"],
  ["bottom-left", "Facecam en bas à gauche"], ["bottom-right", "Facecam en bas à droite"]];

const FONT_CSS = {
  "Poppins Black": "font-family:Poppins;font-weight:900", "Poppins Bold": "font-family:Poppins;font-weight:700",
  "Poppins ExtraBold": "font-family:Poppins;font-weight:800", "Luckiest Guy": "font-family:'Luckiest Guy'",
  Anton: "font-family:Anton", "Bebas Neue": "font-family:'Bebas Neue'", Bangers: "font-family:Bangers",
  "Archivo Black": "font-family:'Archivo Black'",
};

export function stylePreview(s, text = "Choisis un style") {
  const words = s.upper ? text.toUpperCase().split(" ") : text.split(" ");
  const stroke = s.outline ? `text-shadow:${[...Array(8)].map((_, i) => {
    const a = (i / 8) * Math.PI * 2; const r = Math.min(3, s.outline / 2.5);
    return `${(Math.cos(a) * r).toFixed(1)}px ${(Math.sin(a) * r).toFixed(1)}px 0 #000`;
  }).join(",")};` : "text-shadow:0 2px 8px #000a;";
  const size = Math.round(s.size / 5.2);
  return `<div style="${FONT_CSS[s.font] || ""};font-size:${size}px;color:${s.color};${stroke}line-height:1.05">${words.map((w, i) => {
    if (i !== 1 || s.effect === "fade") return esc(w);
    if (s.effect === "box") return `<span style="background:${s.highlight};padding:0 4px;border-radius:5px;text-shadow:none;color:#fff">${esc(w)}</span>`;
    return `<span style="color:${s.highlight}">${esc(w)}</span>`;
  }).join(" ")}</div>`;
}

export const HOOK_STYLES = [
  ["editorial", "Éditorial", `<div style="font-family:'DM Serif Display';font-style:italic;font-size:21px;color:#fff;text-shadow:0 2px 6px #000a;line-height:1;padding:0 8px">Le moment <span style="color:#ffd60a">légendaire</span></div>`],
  ["punchy", "Percutant", `<div style="font-family:Poppins;font-weight:900;font-size:17px;color:#fff;-webkit-text-stroke:1px #000;line-height:1.05;padding:0 6px">C'EST PAS<br><span style="color:#ffd60a">POSSIBLE 😱</span></div>`],
  ["classic", "Classique", `<div style="background:#fff;color:#111;font-family:Poppins;font-weight:800;font-size:11px;padding:6px 9px;border-radius:8px;margin:0 8px">ATTENDS LA FIN…</div>`],
];

function chip(group, val, emoji, label, on) {
  return `<button type="button" class="chip ${on ? "on" : ""}" data-g="${group}" data-v="${val}"><span class="check">${icon("check", "sm")}</span>${emoji ? `<span>${emoji}</span>` : ""}${esc(label)}</button>`;
}

function row(id, ic, name, ctrl, { badge = "", soon = false, on = false } = {}) {
  return `<div class="setting-row ${soon ? "disabled" : ""}" id="row-${id}"><div class="ic ${on ? "on" : ""}">${icon(ic)}</div>
    <div class="name">${name}${badge}${soon ? ' <span class="pill soon">Bientôt</span>' : ""}</div><div class="ctrl">${ctrl}</div></div>`;
}

export async function renderNew(view) {
  const draft = store.draft;
  if (!draft) return go("/");
  const [styles, settings] = await Promise.all([api("/api/styles"), api("/api/settings")]);
  const src = draft.source;
  const o = {
    language: "auto", genre: "auto", clip_length: "auto", clip_types: ["viral", "funny", "drama", "hype"], prompt: "",
    max_clips: 10, ai_engine: "", layout_mode: "", cam_corner: "top-left", captions: true,
    caption_style: settings.brand.caption_style || "neon", caption_position: settings.brand.caption_position || "middle",
    hook: true, hook_style: "punchy", hook_duration: 4, ai_emojis: false, voice_cleanup: "off", enhance_audio: false,
    auto_zoom: false, transitions: false, color_correct: false, translate_to: "", brand_logo: true, split: true,
    ...draft.options,
  };
  const dur = Math.round(src.duration || 0);
  let rs = 0, re = dur;
  const recipe = RECIPES[draft.recipe] || RECIPES.viral;
  const kindLabel = { youtube_live: "Live YouTube", twitch_vod: "VOD Twitch", twitch_live: "Live Twitch", twitch_clip: "Clip Twitch",
    youtube: "YouTube", youtube_short: "Short YouTube", upload: "Fichier importé" }[src.kind] || "Vidéo";

  view.innerHTML = `
  <div class="page-head"><div class="row"><a class="icon-btn" href="#/">${icon("left")}</a>
    <h1 style="margin:0;font-size:20px" class="grow">${esc(src.title || "Nouvelle vidéo")}</h1></div>
    <span class="pill free">${icon("bolt", "sm")} 0 crédit</span></div>
  <div class="create-layout">
    <div class="stack" style="gap:20px">
      <div class="card source-card">
        <div class="source-thumb">${src.thumbnail ? `<img src="${esc(src.thumbnail)}" alt="">` : ""}
          <span class="badge">${esc(kindLabel)}${dur ? " · " + fmtDur(dur) : ""}${src.is_live ? " · 🔴 EN DIRECT" : ""}</span>
          <div class="lang">Langue parlée : <select class="select-inline" id="language">${LANGS.map(([v, l]) => `<option value="${v}" ${o.language === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
        </div>
        <div class="range-box stack">
          <div class="row between"><b>Ajuster la plage ${icon("info", "sm")}</b><span class="small" style="color:var(--warn)" id="rangeinfo">${dur ? "Analyse toute la vidéo" : ""}</span></div>
          ${dur ? `<div class="dual-range" id="dr"><div class="fill" id="drfill"></div>
            <input type="range" id="r1" min="0" max="${dur}" value="0" step="1"><input type="range" id="r2" min="0" max="${dur}" value="${dur}" step="1"></div>` : ""}
          <div class="times"><input class="input" id="t1" value="${fmtClock(0)}"><span class="faint" id="tlen">${dur ? fmtClock(dur) : "Durée inconnue"}</span><input class="input" id="t2" value="${dur ? fmtClock(dur) : ""}" placeholder="fin"></div>
          ${src.is_live ? `<p class="small" style="color:var(--warn);margin:0">Ce live est en cours : choisis une plage (ex. les 30 dernières minutes) ou attends la rediffusion.</p>` : ""}
          <div class="row between wrap" style="margin-top:6px"><span class="muted">Mise en page</span>
            <select class="select-inline" id="layout_mode" style="color:var(--text)">${LAYOUTS.map(([v, l]) => `<option value="${v}" ${o.layout_mode === v ? "selected" : ""}>${icon ? "" : ""}${l}</option>`).join("")}</select></div>
          <div class="row between wrap ${o.layout_mode === "split" ? "" : "hidden"}" id="cornerrow"><span class="muted">Position de la facecam</span>
            <select class="select-inline" id="cam_corner">${CORNERS.map(([v, l]) => `<option value="${v}" ${o.cam_corner === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
        </div>
      </div>

      <div class="card">
        <div class="recipe-cards">
          <div class="recipe-card"><div class="ic" style="background:#3b82f6">${icon("grid")}</div><div class="grow"><b>Recette</b>
            <select class="select-inline" id="recipe" style="display:block;color:var(--muted)">${Object.entries(RECIPES).map(([k, r]) => `<option value="${k}" ${k === draft.recipe ? "selected" : ""}>${r.label}</option>`).join("")}</select></div></div>
          <a class="recipe-card" href="#/brand"><div class="ic" style="background:#65a30d">${icon("brush")}</div><div class="grow"><b>Kit de marque</b>
            <div class="small muted">${esc(settings.brand.name || "Mon kit de marque")}${settings.brand.logo ? " · logo ✔" : ""}</div></div>${icon("right", "sm")}</a>
        </div>
        <p class="muted small" style="margin:14px 4px 0">Ta recette définit les modifications à appliquer. Ton kit de marque définit le style : logo, couleurs, police et style des sous-titres.</p>

        <div class="section-title">Paramètres de la recette</div>
        ${row("split", "scissors", "Découpage", toggle("split", o.split), { on: o.split })}
        <div id="splitbox" class="${o.split ? "" : "hidden"}">
          <div class="row wrap" style="gap:4px 22px;margin:4px 0 14px">
            <span class="muted">Suggestions de l'IA :
              <select class="select-inline" id="ai_engine" style="color:var(--text)">
                <option value="">Auto</option><option value="heuristic">NOXP Local (heuristiques)</option>
                <option value="ollama">Ollama (IA locale)</option><option value="gemini">Gemini (gratuit)</option><option value="groq">Groq (gratuit)</option></select></span>
            <span class="muted">Durée du clip :
              <select class="select-inline" id="clip_length" style="color:var(--text)">${LENGTHS.map(([v, l]) => `<option value="${v}" ${o.clip_length === v ? "selected" : ""}>${l}</option>`).join("")}</select></span>
            <span class="muted">Nombre de clips :
              <select class="select-inline" id="max_clips" style="color:var(--text)">${[3, 5, 8, 10, 15, 20, 30].map((n) => `<option ${+o.max_clips === n ? "selected" : ""}>${n}</option>`).join("")}</select></span>
          </div>
          <p class="muted" style="margin:0 0 12px">Choisis le type de contenu qui correspond à ta vidéo pour aider l'IA à trouver les meilleurs moments.</p>
          <div class="chips" id="genres">${GENRES.map(([v, e, l]) => chip("genre", v, e, l, o.genre === v)).join("")}
            <button type="button" class="chip" id="moregenres">Afficher plus ${icon("down", "sm")}</button></div>
          <p class="muted" style="margin:20px 0 12px">Quels clips veux-tu en priorité ?</p>
          <div class="chips" id="types">${CLIP_TYPES.map(([v, e, l]) => chip("type", v, e, l, o.clip_types.includes(v))).join("")}</div>
          <div class="row between" style="margin:20px 0 8px"><span class="muted">Moments à inclure (facultatif)</span><span class="faint small">ex : « les clutchs, quand il crie, les fous rires »</span></div>
          <textarea class="input" id="prompt" rows="2" placeholder="Trouve les moments les plus hype, les plus drôles et les meilleurs moments.">${esc(o.prompt)}</textarea>
        </div>

        <div class="section-title">Essentiels</div>
        ${row("captions", "cc", "Sous-titres", `<select class="select-inline" id="caption_position"><option value="top">En haut</option><option value="middle">Au milieu</option><option value="bottom">En bas</option></select>${toggle("captions", o.captions)}`, { on: o.captions })}
        <div class="setting-sub ${o.captions ? "" : "hidden"}" id="capbox"><div class="style-scroller" id="styles">
          ${styles.captions.map((s) => `<div class="style-card ${s.id === o.caption_style ? "on" : ""}" data-style="${s.id}">${s.id === o.caption_style ? '<span class="tag">Sélectionné</span>' : `<span class="tag">${esc(s.label)}</span>`}${stylePreview(s)}</div>`).join("")}
        </div></div>
        ${row("hook", "hook", "Accroche auto", `<select class="select-inline" id="hook_duration"><option value="3">3 s</option><option value="4">4 s</option><option value="6">6 s</option><option value="999">Tout le clip</option></select>${toggle("hook", o.hook)}`, { badge: ' <span class="pill beta">Bêta</span>', on: o.hook })}
        <div class="setting-sub ${o.hook ? "" : "hidden"}" id="hookbox"><div class="hook-cards">
          ${HOOK_STYLES.map(([id, l, pv]) => `<div class="hook-card ${id === o.hook_style ? "on" : ""}" data-hook="${id}"><div class="pv">${pv}</div><div class="lbl">${l}</div></div>`).join("")}
        </div></div>
        ${row("motion", "motion", "Motion design", toggle("motion", false, "disabled"), { soon: true })}
        ${row("ai_emojis", "smile", "IA Emojis", toggle("ai_emojis", o.ai_emojis), { on: o.ai_emojis })}
        ${row("broll", "image", "B-roll auto", toggle("broll", false, "disabled"), { soon: true })}

        <div class="section-title">Un son impeccable</div>
        ${row("voice_cleanup", "refresh", "Nettoyage vocal", `<select class="select-inline" id="voice_mode"><option value="both">Pauses + mots parasites</option><option value="pauses">Pauses seulement</option><option value="fillers">« euh », « hum »… seulement</option></select>${toggle("voice_cleanup", o.voice_cleanup !== "off")}`, { on: o.voice_cleanup !== "off" })}
        ${row("enhance_audio", "volume", "Améliorer l'audio", toggle("enhance_audio", o.enhance_audio), { on: o.enhance_audio })}
        ${row("sfx", "sfx", "Auto SFX", toggle("sfx", false, "disabled"), { soon: true })}

        <div class="section-title">Un rendu soigné</div>
        ${row("auto_zoom", "zoom", "Zoom automatique", toggle("auto_zoom", o.auto_zoom), { on: o.auto_zoom })}
        ${row("transitions", "transition", "Transitions automatiques", toggle("transitions", o.transitions), { on: o.transitions })}
        ${row("color_correct", "color", "Correction automatique des couleurs", toggle("color_correct", o.color_correct), { on: o.color_correct })}
        ${row("brand_logo", "brush", "Logo du kit de marque", toggle("brand_logo", o.brand_logo && !!settings.brand.logo, settings.brand.logo ? "" : "disabled"), { on: o.brand_logo && !!settings.brand.logo })}
        ${row("eye", "eye", "Correction du contact visuel", toggle("eye", false, "disabled"), { soon: true })}

        <div class="section-title">Traduction</div>
        ${row("dub", "globe", "Doublage vocal", toggle("dub", false, "disabled"), { soon: true })}
        ${row("translate", "translate", "Traduction des sous-titres", `<select class="select-inline" id="translate_lang">${TRANSLATE.map((l) => `<option ${o.translate_to === l ? "selected" : ""}>${l}</option>`).join("")}</select>${toggle("translate", !!o.translate_to)}`, { on: !!o.translate_to })}
        <p class="small faint" style="margin:0 0 0 54px">La traduction utilise ton IA gratuite (Ollama, Gemini ou Groq) — à configurer dans Réglages.</p>
      </div>
    </div>

    <aside class="card summary">
      <div class="details">
        <h3>Résumé</h3>
        <div class="line">Traitement vidéo <b>Gratuit</b></div>
        <div class="line">Découpage IA <b>Gratuit</b></div>
        <div class="line">Sous-titres <b>Gratuit</b></div>
        <hr>
        <div class="line">Fonctionnalités premium <b id="premcount">Gratuit</b></div>
        <div class="line">Titres & hashtags <b>Gratuit</b></div>
        <hr>
      </div>
      <div class="total"><span>Total</span><span style="color:var(--accent)">${icon("bolt", "sm")} 0 crédit</span></div>
      <button class="btn primary lg block" id="create">Créer</button>
      <p class="faint small details" style="text-align:center;margin:14px 0 0">En continuant, tu confirmes disposer des droits d'utilisation de cette vidéo.</p>
    </aside>
  </div>`;

  // ----- liaisons
  const bindToggle = (id, key, box) => {
    const el = $("#" + id);
    if (!el) return;
    el.onchange = () => {
      if (key) o[key] = el.checked;
      $(`#row-${id} .ic`)?.classList.toggle("on", el.checked);
      if (box) $("#" + box).classList.toggle("hidden", !el.checked);
    };
  };
  bindToggle("split", "split", "splitbox");
  bindToggle("captions", "captions", "capbox");
  bindToggle("hook", "hook", "hookbox");
  ["ai_emojis", "enhance_audio", "auto_zoom", "transitions", "color_correct", "brand_logo"].forEach((k) => bindToggle(k, k));
  bindToggle("voice_cleanup");
  bindToggle("translate");
  $("#caption_position").value = o.caption_position;
  $("#hook_duration").value = String(o.hook_duration >= 999 ? 999 : o.hook_duration);
  $("#ai_engine").value = o.ai_engine || "";
  if (o.voice_cleanup !== "off") $("#voice_mode").value = o.voice_cleanup;

  $("#layout_mode").onchange = (e) => $("#cornerrow").classList.toggle("hidden", e.target.value !== "split");
  $("#recipe").onchange = (e) => {
    store.draft.recipe = e.target.value;
    store.draft.options = { ...RECIPES[e.target.value].options };
    renderNew(view);
  };

  $$("#styles .style-card").forEach((c) => (c.onclick = () => {
    o.caption_style = c.dataset.style;
    $$("#styles .style-card").forEach((x) => {
      x.classList.toggle("on", x === c);
      const s = styles.captions.find((y) => y.id === x.dataset.style);
      x.querySelector(".tag").textContent = x === c ? "Sélectionné" : s.label;
    });
  }));
  $$(".hook-card").forEach((c) => (c.onclick = () => {
    o.hook_style = c.dataset.hook;
    $$(".hook-card").forEach((x) => x.classList.toggle("on", x === c));
  }));

  const bindChips = () => {
    $$('[data-g="genre"]').forEach((c) => (c.onclick = () => {
      o.genre = c.dataset.v;
      $$('[data-g="genre"]').forEach((x) => x.classList.toggle("on", x === c));
    }));
  };
  bindChips();
  $("#moregenres").onclick = (e) => {
    e.currentTarget.insertAdjacentHTML("beforebegin", MORE_GENRES.map(([v, em, l]) => chip("genre", v, em, l, o.genre === v)).join(""));
    e.currentTarget.remove();
    bindChips();
  };
  $$('[data-g="type"]').forEach((c) => (c.onclick = () => {
    c.classList.toggle("on");
    o.clip_types = $$('[data-g="type"].on').map((x) => x.dataset.v);
  }));

  // ----- plage
  const sync = (from) => {
    if (from === "slider") {
      rs = +$("#r1").value; re = +$("#r2").value;
      if (rs > re - 5) { if (document.activeElement === $("#r1")) rs = Math.max(0, re - 5); else re = Math.min(dur, rs + 5); }
      $("#t1").value = fmtClock(rs); $("#t2").value = fmtClock(re);
    } else {
      const a = parseClock($("#t1").value), b = parseClock($("#t2").value);
      if (a !== null) rs = Math.max(0, a);
      if (b !== null && $("#t2").value) re = dur ? Math.min(dur, b) : b;
    }
    if ($("#r1")) {
      $("#r1").value = rs; $("#r2").value = re;
      $("#drfill").style.left = (rs / dur) * 100 + "%";
      $("#drfill").style.width = ((re - rs) / dur) * 100 + "%";
    }
    if (dur) {
      $("#tlen").textContent = fmtClock(re - rs);
      $("#rangeinfo").textContent = rs === 0 && re === dur ? "Analyse toute la vidéo" : `Analyse ${fmtDur(re - rs)} sur ${fmtDur(dur)}`;
    }
  };
  if (dur) {
    $("#r1").oninput = () => sync("slider");
    $("#r2").oninput = () => sync("slider");
    sync("slider");
  }
  $("#t1").onchange = () => sync("text");
  $("#t2").onchange = () => sync("text");

  $("#create").onclick = async () => {
    const btn = $("#create");
    const opts = { ...o };
    opts.language = $("#language").value;
    opts.layout_mode = $("#layout_mode").value;
    opts.cam_corner = $("#cam_corner").value;
    opts.ai_engine = $("#ai_engine").value;
    opts.clip_length = $("#clip_length").value;
    opts.max_clips = +$("#max_clips").value;
    opts.prompt = $("#prompt").value.trim();
    opts.caption_position = $("#caption_position").value;
    opts.hook_duration = +$("#hook_duration").value;
    opts.voice_cleanup = $("#voice_cleanup").checked ? $("#voice_mode").value : "off";
    opts.translate_to = $("#translate").checked ? $("#translate_lang").value : "";
    if (!opts.clip_types.length) opts.clip_types = ["viral"];
    if (dur && (rs > 0 || re < dur)) { opts.range_start = rs; opts.range_end = re; }
    else if (!dur && $("#t2").value) { opts.range_start = rs; opts.range_end = re; }
    if (src.is_live && opts.range_end == null) return toast("Live en cours : choisis une plage à analyser.", "err");
    btn.disabled = true;
    btn.textContent = "Création…";
    try {
      const body = { title: src.title, thumbnail: src.thumbnail, duration: src.duration, options: opts };
      if (src.upload_id) body.upload_id = src.upload_id; else body.url = src.url;
      const p = await api("/api/projects", { method: "POST", body });
      store.draft = null;
      go(`/project/${p.id}`);
    } catch (err) {
      toast(err.message, "err");
      btn.disabled = false;
      btn.textContent = "Créer";
    }
  };
}
