import { $, $$, api, confirmBox, copyText, esc, fmtClock, fmtDur, go, icon, modal, onLeave, parseClock, toast, toggle } from "./core.js";
import { openSchedule, shareClip, captionFor } from "./schedule.js";
import { HOOK_STYLES, LAYOUTS, CORNERS, CLIP_TYPES, LENGTHS, GENRES, MORE_GENRES } from "./create.js";

const STEPS = [["downloading", "download", "Téléchargement"], ["transcribing", "mic", "Transcription"],
  ["analyzing", "sparkles", "Analyse IA"], ["rendering", "scissors", "Montage 9:16"]];
const FILTERS = [["all", "Tous"], ["top", "🔥 Top viral"], ["funny", "😂 Drôles"], ["drama", "🎭 Dramatiques"], ["hype", "⚡ Épiques"]];
const LANG_NAMES = { fr: "français", en: "anglais", es: "espagnol", de: "allemand", it: "italien", pt: "portugais", ar: "arabe", nl: "néerlandais", ja: "japonais" };
const ENGINE_NAMES = { heuristic: "NOXP Local (heuristiques)", ollama: "Ollama (IA locale)", gemini: "Gemini", groq: "Groq" };

function scoreCls(s) { return s >= 85 ? "hi" : s >= 72 ? "mid" : "lo"; }

function trendsPanel(t, clips) {
  if (!t) return "";
  const n = clips.filter((c) => (c.scores || {}).trend_label).length;
  const tags = (t.hashtags || []).slice(0, 10).map((h) => `<span class="chip sm" style="pointer-events:none">${esc(h)}</span>`).join("");
  const tiktok = (t.sources || []).some((s) => s.startsWith("TikTok"));
  return `<details class="card flat small" style="margin-bottom:14px">
    <summary style="cursor:pointer"><b>📈 Tendances du moment</b> · ${n} clip${n > 1 ? "s" : ""} colle${n > 1 ? "nt" : ""} à une tendance
      ${t.title_match && t.title_match.length ? ` · la vidéo parle de <b>${esc(t.title_match.join(", "))}</b>` : ""}</summary>
    <div class="stack" style="margin-top:10px;gap:10px">
      ${tags ? `<div class="chips">${tags}</div>` : ""}
      ${(t.formats || []).length ? `<div><b>Formats qui marchent :</b><ul style="margin:4px 0 0;padding-left:18px">${t.formats.map((f) => `<li>${esc(f)}</li>`).join("")}</ul></div>` : ""}
      ${(t.web || []).length ? `<div class="muted"><b>Recherches Google du jour :</b> ${esc(t.web.slice(0, 10).join(" · "))}</div>` : ""}
      <div class="faint">Sources : ${esc((t.sources || []).join(", ") || "formats habituels de la niche (hors ligne)")}</div>
      ${!tiktok ? `<div style="color:var(--warn)">Pour les tendances TikTok en direct, ajoute ta clé Gemini gratuite dans Réglages.${(t.errors || []).length ? " Détail : " + esc(t.errors.join(" | ")) : ""}</div>` : ""}
    </div></details>`;
}

function clipCard(c) {
  const busy = c.status === "queued" || c.status === "rendering";
  const err = c.status === "error";
  const s = c.scores || {};
  return `<div class="clip-card" data-id="${c.id}">
    <div class="clip-video">
      ${c.video_url && !busy ? `<video src="${esc(c.video_url)}" poster="${esc(c.thumb_url || "")}" controls playsinline preload="none"></video>` : (c.thumb_url ? `<img src="${esc(c.thumb_url)}" alt="">` : "")}
      <span class="rank">#${c.rank} · ${fmtDur(c.duration)}</span>
      <div class="score ${scoreCls(c.score)}"><div style="text-align:center">${c.score}<small>VIRAL</small></div></div>
      ${busy ? `<div class="rendering">${icon("refresh", "lg spin")}<div>${c.status === "queued" ? "En attente…" : "Montage en cours…"}</div></div>` : ""}
      ${err ? `<div class="rendering" style="color:var(--danger)">${icon("info", "lg")}<div class="small">${esc((c.error || "Erreur").slice(0, 160))}</div></div>` : ""}
    </div>
    <div class="clip-body">
      <div class="row wrap" style="gap:6px"><span class="pill cat-${c.category}">${esc(c.category_label)}</span>
        ${c.score >= 85 ? '<span class="pill cat-viral">🔥 Sûr de marcher</span>' : ""}
        ${s.trend_label ? `<span class="pill free" title="Colle à une tendance actuelle">📈 ${esc(s.trend_label)}</span>` : ""}</div>
      <div class="clip-title">${esc(c.title)}</div>
      ${c.hook ? `<div class="small" style="color:var(--accent);font-weight:650">« ${esc(c.hook)} »</div>` : ""}
      <div class="scores-mini"><span>😂 <b>${s.funny ?? "-"}</b></span><span>🎭 <b>${s.drama ?? "-"}</b></span><span>⚡ <b>${s.hype ?? "-"}</b></span><span class="faint">${fmtClock(c.start)} → ${fmtClock(c.end)}</span></div>
      ${c.reason ? `<div class="clip-reason">${esc(c.reason)}</div>` : ""}
      <div class="small faint">${esc((c.hashtags || []).join(" "))}</div>
      ${(c.overrides || {})._translation && (c.overrides._translation.includes("échec")) ? `<div class="small" style="color:var(--warn)">⚠️ Sous-titres non traduits (${esc(c.overrides._translation.split("échec : ")[1] || "")}). Ajoute une clé Gemini gratuite dans Réglages puis « Modifier → Regénérer ».</div>` : ""}
      <div class="clip-actions">
        <a class="btn" ${c.file && !busy ? `href="/api/clips/${c.id}/download" download` : "disabled"}>${icon("download", "sm")}Télécharger</a>
        <button class="btn" data-act="share" ${c.file && !busy ? "" : "disabled"}>${icon("share", "sm")}Partager</button>
        <button class="btn" data-act="schedule" ${c.file && !busy ? "" : "disabled"}>${icon("calendar", "sm")}Planifier</button>
        <button class="btn" data-act="edit">${icon("edit", "sm")}Modifier</button>
      </div>
    </div></div>`;
}

export async function renderProject(view, { id }) {
  let project = null;
  let filter = "all";
  let timer = null;
  onLeave(() => clearTimeout(timer));

  const load = async () => {
    try { project = await api(`/api/projects/${id}`); }
    catch (e) { view.innerHTML = `<div class="empty">${icon("info")}<p>${esc(e.message)}</p><a class="btn" href="#/">Retour</a></div>`; return; }
    draw();
    const busy = !["done", "error"].includes(project.status) || project.clips.some((c) => ["queued", "rendering"].includes(c.status));
    clearTimeout(timer);
    if (busy) timer = setTimeout(load, 2500);
  };

  const head = () => `<div class="page-head"><div class="row grow" style="min-width:0"><a class="icon-btn" href="#/projects">${icon("left")}</a>
      <div class="grow" style="min-width:0"><h1 style="margin:0;font-size:20px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(project.title)}</h1>
      <div class="small muted">${project.source_url ? `<a href="${esc(project.source_url)}" target="_blank" rel="noopener" style="text-decoration:underline">Source</a> · ` : ""}${new Date(project.created_at * 1000).toLocaleString("fr-FR")}</div></div></div>
    <div class="row wrap">${project.status === "done" ? `<button class="btn" id="reanalyze">${icon("refresh", "sm")} Relancer l'analyse</button><button class="btn primary" id="scheduleall">${icon("calendar", "sm")} Planifier une série</button>` : ""}</div></div>`;

  const draw = () => {
    const p = project;
    if (p.status === "error") {
      view.innerHTML = head() + `<div class="card progress-card"><div style="color:var(--danger)">${icon("info", "lg")}</div><h2>Le traitement a échoué</h2>
        <p class="muted" style="white-space:pre-wrap;text-align:left;max-height:200px;overflow:auto" class="small">${esc(p.error || "Erreur inconnue")}</p>
        <div class="row" style="justify-content:center"><button class="btn primary" id="retry">${icon("refresh", "sm")} Réessayer</button>
        <button class="btn danger" id="delete">${icon("trash", "sm")} Supprimer</button></div></div>`;
      $("#retry").onclick = async () => { await api(`/api/projects/${id}/retry`, { method: "POST" }); load(); };
      $("#delete").onclick = async () => { if (await confirmBox("Supprimer ce projet ?", "Supprimer")) { await api(`/api/projects/${id}`, { method: "DELETE" }); go("/projects"); } };
      return;
    }
    if (p.status !== "done") {
      const idx = STEPS.findIndex(([s]) => s === p.status);
      const pct = Math.round((p.progress || 0) * 100);
      view.innerHTML = head() + `<div class="card progress-card">
        <h2 style="margin-bottom:4px">${p.status === "queued" ? "En file d'attente…" : "NOXPclips travaille sur ta vidéo"}</h2>
        <p class="muted" style="margin-top:0">${esc(p.message || "")}</p>
        <div class="row" style="gap:12px"><div class="bar grow"><div style="width:${pct}%"></div></div><b>${pct}%</b></div>
        <div class="steps">${STEPS.map(([s, ic, l], i) => `<div class="step ${i < idx ? "done" : i === idx ? "on" : ""}">${i < idx ? icon("check") : icon(ic, i === idx ? "spin-slow" : "")}${l}</div>`).join("")}</div>
        <p class="faint small">Tu peux fermer cette page : le traitement continue sur le serveur. Les longs lives peuvent prendre un moment.</p></div>`;
      return;
    }
    const meta = p.meta || {};
    const clips = p.clips.filter((c) => filter === "all" || (filter === "top" ? c.score >= 80 : c.category === filter))
      .sort((a, b) => (filter === "all" ? a.rank - b.rank : filter === "top" ? b.score - a.score : (b.scores?.[filter] || 0) - (a.scores?.[filter] || 0)));
    view.innerHTML = head() + `
      <div class="row wrap small muted" style="gap:8px 16px;margin-bottom:14px">
        <span>${icon("sparkles", "sm")} IA : <b style="color:var(--text)">${esc(ENGINE_NAMES[meta.ai_engine_used] || meta.ai_engine_used || "—")}</b></span>
        <span>🎯 Catégorie : <b style="color:var(--text)">${esc((([...GENRES, ...MORE_GENRES].find(([v]) => v === meta.genre)) || [0, 0, meta.genre || "auto"])[2])}</b></span>
        ${meta.chat ? `<span>💬 Chat du live analysé</span>` : ""}
        ${(meta.audience_signals || {}).heatmap ? `<span>📈 « Moments les plus revus » YouTube</span>` : ""}
        ${(meta.audience_signals || {}).comments ? `<span>💬 ${meta.audience_signals.comments} commentaires horodatés</span>` : ""}
        ${meta.language ? `<span>🗣️ Vidéo en ${esc(LANG_NAMES[meta.language] || meta.language)} · textes en ${meta.text_language === "en" ? "anglais" : "français"}${meta.language !== "fr" && p.options.captions_fr !== false ? " · sous-titres traduits en français" : ""}</span>` : ""}
        <span>📐 ${esc({ full: "Gameplay entier", split: "Facecam + jeu recadré", fill: "Recadrage 9:16", fit: "Fond flou" }[(p.options.layout_mode || (meta.layout || {}).mode)] || "Auto")}</span>
      </div>
      ${meta.warning ? `<div class="card flat small" style="border-color:#ffb02055;color:var(--warn);margin-bottom:14px">${esc(meta.warning)}</div>` : ""}
      ${trendsPanel(meta.trends, p.clips)}
      <div class="filters">${FILTERS.map(([k, l]) => `<button class="chip sm ${k === filter ? "on" : ""}" data-f="${k}">${l} <span class="faint">${k === "all" ? p.clips.length : p.clips.filter((c) => (k === "top" ? c.score >= 80 : c.category === k)).length}</span></button>`).join("")}</div>
      <div class="clips-grid">${clips.map(clipCard).join("") || `<div class="empty" style="grid-column:1/-1">Aucun clip dans cette catégorie.</div>`}</div>`;
    $$("[data-f]").forEach((b) => (b.onclick = () => { filter = b.dataset.f; draw(); }));
    $("#scheduleall").onclick = () => openSchedule(p.clips.filter((c) => c.status === "done"), () => {});
    $("#reanalyze").onclick = () => reanalyzeModal(p, load);
    $$(".clip-card").forEach((card) => {
      const c = p.clips.find((x) => x.id === card.dataset.id);
      card.addEventListener("click", (e) => {
        const a = e.target.closest("[data-act]");
        if (!a || a.disabled) return;
        if (a.dataset.act === "share") shareClip(c);
        if (a.dataset.act === "schedule") openSchedule([c], () => {});
        if (a.dataset.act === "edit") editClip(c, p, load);
      });
      // une seule vidéo joue à la fois
      const v = card.querySelector("video");
      v && v.addEventListener("play", () => $$("video").forEach((o) => o !== v && o.pause()));
    });
  };
  view.innerHTML = `<div class="empty">${icon("refresh", "spin")}</div>`;
  await load();
}

function editClip(c, project, reload) {
  const o = { ...project.options, ...(c.overrides || {}) };
  const dur = (project.meta?.media || {}).duration || c.end + 60;
  const m = modal(`
    <div class="modal-head"><h2>Modifier le clip #${c.rank}</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <div class="edit-layout">
      <div>${c.video_url ? `<video src="${esc(c.video_url)}" poster="${esc(c.thumb_url || "")}" controls playsinline></video>` : ""}
        <div class="row wrap" style="margin-top:10px;gap:6px">
          <a class="btn sm" href="/api/clips/${c.id}/download?kind=srt" download>${icon("cc", "sm")} .SRT</a>
          <button class="btn sm" id="copycap">${icon("copy", "sm")} Légende</button>
          <button class="btn sm danger" id="delclip">${icon("trash", "sm")} Supprimer</button></div></div>
      <div class="stack">
        <label class="field">Titre<input class="input" id="title" value="${esc(c.title)}"></label>
        <label class="field">Accroche affichée à l'écran<input class="input" id="hook" value="${esc(c.hook || "")}"></label>
        <label class="field">Description<textarea class="input" id="desc" rows="2">${esc(c.description || "")}</textarea></label>
        <label class="field">Hashtags<input class="input" id="tags" value="${esc((c.hashtags || []).join(" "))}"></label>
        <div class="grid2">
          <label class="field">Début<div class="nudge"><button class="btn sm" data-n="s,-1">−1s</button><input class="input" id="start" value="${fmtClock(c.start)}"><button class="btn sm" data-n="s,1">+1s</button></div></label>
          <label class="field">Fin<div class="nudge"><button class="btn sm" data-n="e,-1">−1s</button><input class="input" id="end" value="${fmtClock(c.end)}"><button class="btn sm" data-n="e,1">+1s</button></div></label>
        </div>
        <div class="grid2">
          <label class="field">Style des sous-titres<select class="input" id="caption_style"></select></label>
          <label class="field">Style de l'accroche<select class="input" id="hook_style">${HOOK_STYLES.map(([v, l]) => `<option value="${v}" ${o.hook_style === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <label class="field">Mise en page<select class="input" id="layout_mode">${LAYOUTS.map(([v, l]) => `<option value="${v}" ${(o.layout_mode || "") === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <label class="field">Facecam<select class="input" id="cam_corner">${CORNERS.map(([v, l]) => `<option value="${v}" ${o.cam_corner === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
        </div>
        <div class="row wrap" style="gap:14px">
          ${[["captions", "Sous-titres"], ["hook", "Accroche"], ["ai_emojis", "Emojis"], ["auto_zoom", "Zoom auto"], ["progress_bar", "Barre de progression"], ["transitions", "Transitions"], ["color_correct", "Couleurs"], ["enhance_audio", "Audio+"]]
            .map(([k, l]) => `<label class="row small" style="gap:8px">${toggle("o_" + k, !!o[k])} ${l}</label>`).join("")}
        </div>
      </div>
    </div>
    <div class="modal-foot"><button class="btn" id="savetext">Enregistrer le texte</button>
      <button class="btn primary" id="rerender">${icon("refresh", "sm")} Regénérer la vidéo</button></div>`, { wide: true });
  api("/api/styles").then((s) => {
    $("#caption_style", m.el).innerHTML = s.captions.map((x) => `<option value="${x.id}" ${x.id === o.caption_style ? "selected" : ""}>${x.label}</option>`).join("");
  });
  $$("[data-n]", m.el).forEach((b) => (b.onclick = () => {
    const [w, d] = b.dataset.n.split(",");
    const inp = $(w === "s" ? "#start" : "#end", m.el);
    inp.value = fmtClock(Math.max(0, Math.min(dur, (parseClock(inp.value) || 0) + +d)));
  }));
  const texts = () => ({ title: $("#title", m.el).value, hook: $("#hook", m.el).value, description: $("#desc", m.el).value,
    hashtags: $("#tags", m.el).value.split(/[\s,]+/).filter(Boolean).map((t) => "#" + t.replace(/^#/, "")) });
  $("#copycap", m.el).onclick = () => copyText(captionFor({ ...c, ...texts() }));
  $("#delclip", m.el).onclick = async () => {
    if (!(await confirmBox("Supprimer ce clip ?", "Supprimer"))) return;
    await api(`/api/clips/${c.id}`, { method: "DELETE" });
    m.close(); reload();
  };
  $("#savetext", m.el).onclick = async () => {
    await api(`/api/clips/${c.id}`, { method: "PATCH", body: texts() });
    toast("Enregistré ✔ (l'accroche à l'écran change après « Regénérer »)", "ok");
    m.close(); reload();
  };
  $("#rerender", m.el).onclick = async () => {
    const options = { caption_style: $("#caption_style", m.el).value, hook_style: $("#hook_style", m.el).value,
      layout_mode: $("#layout_mode", m.el).value, cam_corner: $("#cam_corner", m.el).value };
    ["captions", "hook", "ai_emojis", "auto_zoom", "progress_bar", "transitions", "color_correct", "enhance_audio"].forEach((k) => (options[k] = $("#o_" + k, m.el).checked));
    try {
      await api(`/api/clips/${c.id}/rerender`, { method: "POST", body: { ...texts(), start: parseClock($("#start", m.el).value), end: parseClock($("#end", m.el).value), options } });
      toast("Nouveau montage lancé…", "ok");
      m.close(); reload();
    } catch (e) { toast(e.message, "err"); }
  };
}

// ---------- Relancer l'analyse (avec la facecam : l'utilisateur dessine le rectangle de la webcam) ----------
function reanalyzeModal(p, reload) {
  const o = p.options;
  const meta = p.meta || {};
  const media = meta.media || {};
  const times = p.clips.length ? p.clips.map((c) => (c.start + c.end) / 2) : [10, 60, 180];
  let ti = 0;
  let box = o.cam_box || (meta.layout || {}).cam || null;
  let drawn = false;  // l'utilisateur a dessiné ou effacé le rectangle
  const m = modal(`<div class="modal-head"><h2>Relancer l'analyse</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <p class="muted" style="margin-top:0">Pas besoin de retélécharger : NOXPclips réutilise la vidéo et la transcription.</p>
    <div class="grid2">
      <label class="field">Catégorie<select class="input" id="genre">${[...GENRES, ...MORE_GENRES].map(([v, e, l]) => `<option value="${v}" ${o.genre === v ? "selected" : ""}>${e} ${l}</option>`).join("")}</select></label>
      <label class="field">Durée des clips<select class="input" id="clip_length">${LENGTHS.map(([v, l]) => `<option value="${v}" ${o.clip_length === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
      <label class="field">Nombre de clips<select class="input" id="max_clips">${[3, 5, 8, 10, 15, 20, 30].map((n) => `<option ${+o.max_clips === n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
      <label class="field">Moteur IA<select class="input" id="ai_engine"><option value="">Auto</option><option value="heuristic">NOXP Local</option><option value="ollama">Ollama</option><option value="gemini">Gemini</option><option value="groq">Groq</option></select></label>
    </div>
    <h3 style="margin:18px 0 6px;font-size:16px">${icon("eye", "sm")} Facecam & mise en page</h3>
    <label class="field">Mise en page<select class="input" id="layout_mode">${LAYOUTS.map(([v, l]) => `<option value="${v}" ${(o.layout_mode || "") === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
    <div id="fczone">
      <p class="small muted" style="margin:8px 0">Dessine au doigt un rectangle autour de la webcam du streamer : il sera <b>en haut</b>, avec <b>tout le gameplay en dessous</b> et des zooms dynamiques.</p>
      <div id="fcwrap" style="position:relative;touch-action:none;user-select:none;-webkit-user-select:none;border-radius:14px;overflow:hidden;background:#000;aspect-ratio:${media.width || 16}/${media.height || 9}">
        <img id="fcimg" alt="" style="width:100%;height:100%;object-fit:contain;pointer-events:none" draggable="false">
        <div id="fcbox" style="position:absolute;border:3px solid var(--accent);box-shadow:0 0 0 9999px #0008;border-radius:6px;display:none;pointer-events:none"></div>
      </div>
      <div class="row wrap" style="margin-top:8px;gap:8px">
        <button class="btn sm" id="fcnext">${icon("refresh", "sm")} Autre image</button>
        <button class="btn sm" id="fcclear">${icon("x", "sm")} Pas de facecam</button>
        <span class="small faint" id="fchint"></span>
      </div>
    </div>
    <p class="muted" style="margin-top:16px">Types de clips</p><div class="chips">${CLIP_TYPES.map(([v, e, l]) => `<button class="chip sm ${o.clip_types.includes(v) ? "on" : ""}" data-t="${v}">${e} ${l}</button>`).join("")}</div>
    <label class="field" style="margin-top:12px">Moments à inclure<textarea class="input" id="prompt" rows="2">${esc(o.prompt || "")}</textarea></label>
    <label class="row small" style="margin-top:12px;gap:8px">${toggle("rtrends", o.trends !== false)} 📈 Suivre les tendances TikTok du moment</label>
    <label class="row small" style="margin-top:8px;gap:8px">${toggle("retr", false)} Refaire aussi la transcription (si la langue était mal détectée)</label>
    <div class="modal-foot">
      <button class="btn" data-close>Annuler</button>
      ${p.clips.length ? `<button class="btn" id="layoutonly">${icon("eye", "sm")} Mise en page seule (garder les clips)</button>` : ""}
      <button class="btn primary" id="go">${icon("refresh", "sm")} Relancer</button>
    </div>`, { wide: true });
  $("#ai_engine", m.el).value = o.ai_engine || "";
  $$("[data-t]", m.el).forEach((b) => (b.onclick = () => b.classList.toggle("on")));

  // --- facecam ---
  const sel = $("#layout_mode", m.el), zone = $("#fczone", m.el);
  const wrap = $("#fcwrap", m.el), img = $("#fcimg", m.el), rect = $("#fcbox", m.el), hint = $("#fchint", m.el);
  const show = () => {
    if (!box) rect.style.display = "none";
    else {
      const [x, y, w, h] = box;
      Object.assign(rect.style, { display: "block", left: x * 100 + "%", top: y * 100 + "%", width: w * 100 + "%", height: h * 100 + "%" });
    }
    hint.textContent = box ? (drawn ? "Facecam enregistrée ✔" : "Facecam détectée — redessine-la si elle est mal placée.")
      : "Aucune facecam : dessine-la si le streamer apparaît à l'écran.";
  };
  const syncZone = () => zone.classList.toggle("hidden", ["fill", "fit"].includes(sel.value));
  sel.onchange = syncZone;
  syncZone();
  const loadImg = () => { img.src = `/api/projects/${p.id}/frame?t=${Math.round(times[ti % times.length] || 10)}`; };
  img.onload = show;
  img.onerror = () => { hint.textContent = "Image indisponible (vidéo source supprimée ?)"; };
  loadImg();
  show();
  $("#fcnext", m.el).onclick = () => { ti++; loadImg(); };
  $("#fcclear", m.el).onclick = () => { box = null; drawn = true; show(); };
  let start = null;
  const pos = (e) => {
    const r = wrap.getBoundingClientRect();
    return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))];
  };
  wrap.addEventListener("pointerdown", (e) => { e.preventDefault(); wrap.setPointerCapture(e.pointerId); start = pos(e); });
  wrap.addEventListener("pointermove", (e) => {
    if (!start) return;
    const [x2, y2] = pos(e);
    box = [Math.min(start[0], x2), Math.min(start[1], y2), Math.abs(x2 - start[0]), Math.abs(y2 - start[1])];
    show();
  });
  wrap.addEventListener("pointerup", () => {
    start = null;
    if (box && (box[2] < 0.03 || box[3] < 0.03)) {  // simple tape : on ignore
      box = null;
      rect.style.display = "none";
      hint.textContent = "Rectangle trop petit : fais glisser ton doigt pour l'agrandir.";
      return;
    }
    if (!box) return;
    drawn = true;
    if (!sel.value) sel.value = "full";  // facecam dessinée → gameplay entier + facecam
    show();
  });

  const layoutOptions = () => {
    const opts = { layout_mode: sel.value };
    if (["fill", "fit"].includes(sel.value)) opts.cam_box = null;
    else if (drawn) opts.cam_box = box ? box.map((v) => Math.round(v * 10000) / 10000) : null;
    if (drawn && !box && sel.value === "split") opts.layout_mode = "fill";  // plus de facecam → recadrage du jeu
    if (opts.layout_mode === "full") Object.assign(opts, { auto_zoom: true, progress_bar: true });
    return opts;
  };
  const lo = $("#layoutonly", m.el);
  if (lo) lo.onclick = async () => {
    try {
      const r = await api(`/api/projects/${p.id}/rerender-all`, { method: "POST", body: { options: layoutOptions() } });
      toast(`${r.count} clips en cours de remontage…`, "ok");
      m.close(); reload();
    } catch (e) { toast(e.message, "err"); }
  };
  $("#go", m.el).onclick = async () => {
    const options = { genre: $("#genre", m.el).value, clip_length: $("#clip_length", m.el).value, max_clips: +$("#max_clips", m.el).value,
      ai_engine: $("#ai_engine", m.el).value, prompt: $("#prompt", m.el).value, clip_types: $$("[data-t].on", m.el).map((b) => b.dataset.t),
      trends: $("#rtrends", m.el).checked, ...layoutOptions() };
    if (!options.clip_types.length) options.clip_types = ["viral"];
    try {
      await api(`/api/projects/${p.id}/reanalyze`, { method: "POST", body: { options, retranscribe: $("#retr", m.el).checked } });
      m.close(); reload();
    } catch (e) { toast(e.message, "err"); }
  };
}
