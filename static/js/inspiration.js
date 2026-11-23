// Inspiration TikTok : le bot scrolle TikTok et suggère des idées à partir des vidéos qui cartonnent.
import { $, $$, api, copyText, esc, fmtDate, icon, onLeave, toast } from "./core.js";

const n = (v) => (v >= 1e6 ? (v / 1e6).toFixed(1).replace(".0", "") + " M" : v >= 1e3 ? Math.round(v / 1e3) + " k" : String(v));
const ago = (h) => (h < 24 ? `il y a ${h} h` : `il y a ${Math.round(h / 24)} j`);

function card(i) {
  const m = i.metrics || {};
  const cls = m.score >= 75 ? "hi" : m.score >= 60 ? "mid" : "lo";
  return `<div class="card insp" data-id="${esc(i.id)}">
    <div class="insp-top">
      <a class="insp-cover" href="${esc(i.url)}" target="_blank" rel="noopener">${i.cover ? `<img src="${esc(i.cover)}" alt="" loading="lazy">` : icon("tiktok", "lg")}
        <span class="score ${cls}"><div style="text-align:center">${m.score}<small>MARCHE</small></div></span></a>
      <div class="grow" style="min-width:0">
        <div class="small muted">@${esc(i.author)} · ${esc(i.source)} · ${ago(m.age_h || 0)}${i.duration ? ` · ${i.duration} s` : ""}</div>
        <div class="insp-desc">${esc(i.desc || "(sans description)")}</div>
        <div class="insp-stats small"><span>▶ <b>${n(i.plays)}</b></span><span>❤ <b>${n(i.likes)}</b></span><span>💬 <b>${n(i.comments)}</b></span><span>↗ <b>${n(i.shares)}</b></span>
          <span title="engagement pondéré">⚡ <b>${m.er} %</b></span><span title="vues par heure">🚀 <b>${n(m.velocity || 0)}/h</b></span>${m.over >= 2 ? `<span title="vues / abonnés">📈 <b>×${Math.round(m.over)}</b></span>` : ""}</div>
      </div>
    </div>
    ${i.why ? `<div class="small"><b>Pourquoi ça marche :</b> ${esc(i.why)}</div>` : ""}
    ${i.idea ? `<div class="insp-idea small"><b>💡 Ton idée :</b> ${esc(i.idea)}${i.hook ? `<div style="margin-top:4px;color:var(--accent);font-weight:700">« ${esc(i.hook)} »</div>` : ""}${i.format ? `<div class="faint">Format : ${esc(i.format)}</div>` : ""}</div>` : ""}
    ${i.my_clip ? `<div class="small">🎬 Un de tes clips colle à ce format : <a href="#/project/${esc(i.my_clip.project_id)}" style="text-decoration:underline">${esc(i.my_clip.title)}</a></div>` : ""}
    <div class="row wrap" style="gap:8px">
      <a class="btn sm" href="${esc(i.url)}" target="_blank" rel="noopener">${icon("right", "sm")} Voir sur TikTok</a>
      ${i.idea ? `<button class="btn sm" data-copy="${esc([i.idea, i.hook, i.format].filter(Boolean).join(" — "))}">${icon("copy", "sm")} Copier l'idée</button>` : ""}
      ${i.music ? `<button class="btn sm" data-copy="${esc(i.music)}" title="Copier le nom du son">🎵 ${esc(i.music.slice(0, 28))}</button>` : ""}
      <button class="btn ghost sm" data-dismiss="${esc(i.id)}">${icon("x", "sm")} Masquer</button>
    </div></div>`;
}

export async function renderInspiration(view) {
  let all = false;
  let timer = null;
  onLeave(() => clearTimeout(timer));

  const draw = async () => {
    const d = await api(`/api/scout${all ? "?all=1" : ""}`);
    const st = d.status || {};
    const running = st.state === "running";
    if (!$("#insp-root")) return;
    $("#insp-root").innerHTML = `
      <div class="card flat small" style="margin-bottom:14px">
        ${running ? `${icon("refresh", "sm spin")} <b>${esc(st.message || "Le bot scrolle TikTok…")}</b> <div class="bar" style="margin-top:8px"><div style="width:${Math.round((st.progress || 0) * 100)}%"></div></div>`
        : st.state === "error" ? `<span style="color:var(--danger)">${esc(st.message)}</span>`
        : d.last_run ? `Dernier passage : <b>${fmtDate(d.last_run)}</b>${d.runs.length ? ` · ${d.runs[d.runs.length - 1].seen} vidéos regardées, ${d.runs[d.runs.length - 1].good} qui cartonnent` : ""}`
        : "Le bot n'est pas encore passé. Lance un premier scroll (≈ 6 min)."}
      </div>
      <div class="row wrap between" style="gap:10px;margin-bottom:14px">
        <div class="row wrap" style="gap:8px">
          <button class="btn primary" id="run" ${running ? "disabled" : ""}>${icon("bolt", "sm")} ${running ? "Scroll en cours…" : "Lancer le bot maintenant"}</button>
          ${running ? `<button class="btn" id="stop">${icon("x", "sm")} Arrêter</button>` : ""}
        </div>
        <div class="row wrap" style="gap:8px"><button class="chip sm ${!all ? "on" : ""}" data-f="niche">🎯 Ma niche</button><button class="chip sm ${all ? "on" : ""}" data-f="all">🌍 Tout TikTok</button></div>
      </div>
      <div class="insp-grid">${d.items.map(card).join("") || `<div class="empty" style="grid-column:1/-1">${icon("sparkles")}<p>Aucune vidéo qui cartonne pour l'instant.${d.last_run ? " Essaie « Tout TikTok » ou d'autres hashtags." : ""}</p></div>`}</div>`;
    $("#run").onclick = async () => {
      try { await api("/api/scout/run", { method: "POST" }); toast("Le bot commence à scroller TikTok 🤖", "ok"); draw(); }
      catch (e) { toast(e.message, "err"); }
    };
    $("#stop") && ($("#stop").onclick = async () => { await api("/api/scout/cancel", { method: "POST" }); toast("Arrêt demandé"); });
    $$("[data-f]").forEach((b) => (b.onclick = () => { all = b.dataset.f === "all"; draw(); }));
    $$("[data-copy]").forEach((b) => (b.onclick = () => copyText(b.dataset.copy)));
    $$("[data-dismiss]").forEach((b) => (b.onclick = async () => {
      await api(`/api/scout/${b.dataset.dismiss}/dismiss`, { method: "POST" });
      b.closest(".insp").remove();
    }));
    clearTimeout(timer);
    if (running) timer = setTimeout(draw, 4000);
  };

  const s = await api("/api/settings");
  view.innerHTML = `<div class="page-head"><div><h1>Inspiration TikTok</h1>
    <p class="muted" style="margin:0">Un bot scrolle TikTok à ta place (fil « Pour toi » + hashtags de ta niche), repère les vidéos qui cartonnent et te propose des idées à faire avec tes propres vidéos. Il ne republie rien.</p></div></div>
    <details class="card flat" style="margin-bottom:14px"><summary style="cursor:pointer"><b>${icon("settings", "sm")} Réglages du bot</b></summary>
      <div class="stack" style="margin-top:12px">
        <label class="field">Hashtags de ta niche (séparés par des virgules)<input class="input" id="scout_tags" value="${esc(s.scout_tags || "")}" placeholder="gta6, gtarp, squeezie"></label>
        <div class="grid2">
          <label class="field">Vues minimum<input class="input" id="scout_min_views" type="number" min="1000" step="1000" value="${esc(s.scout_min_views || 20000)}"></label>
          <label class="field">Durée de scroll par page (s)<input class="input" id="scout_seconds" type="number" min="30" max="240" value="${esc(s.scout_seconds || 75)}"></label>
        </div>
        <label class="row small" style="gap:8px"><label class="toggle"><input type="checkbox" id="scout_auto" ${s.scout_auto ? "checked" : ""}><span></span></label> Passage automatique une fois par jour (quand ton serveur est allumé)</label>
        <p class="small faint" style="margin:0">Le bot utilise un navigateur à part, non connecté à ton compte : aucun risque pour ton TikTok. Sans clé Gemini, les explications sont plus simples (chiffres uniquement).</p>
        <button class="btn" id="save">${icon("check", "sm")} Enregistrer</button>
      </div></details>
    <div id="insp-root"></div>`;
  $("#save").onclick = async () => {
    await api("/api/settings", { method: "PUT", body: {
      scout_tags: $("#scout_tags").value.trim(), scout_min_views: +$("#scout_min_views").value || 20000,
      scout_seconds: +$("#scout_seconds").value || 75, scout_auto: $("#scout_auto").checked } });
    toast("Réglages du bot enregistrés ✔", "ok");
    draw();
  };
  draw();
}
