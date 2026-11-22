import { $, $$, PLATFORMS, STATUS_LABELS, api, esc, fmtDate, icon, toast, uploadWithProgress } from "./core.js";
import { openPost } from "./schedule.js";

const ENGINES = [
  ["auto", "Auto", "Utilise la meilleure IA gratuite disponible, sinon les heuristiques locales."],
  ["heuristic", "NOXP Local", "Volume, cris, rires, mots-clés, pics du chat. Instantané, hors-ligne, illimité."],
  ["ollama", "Ollama (IA locale)", "Une vraie IA sur ton Mac / serveur. Gratuit et illimité (16 Go de RAM conseillés)."],
  ["gemini", "Google Gemini", "Palier gratuit généreux. Clé sur aistudio.google.com."],
  ["groq", "Groq", "Palier gratuit, très rapide. Clé sur console.groq.com."],
];
const WHISPER = [["tiny", "Tiny — ultra rapide, précision moyenne"], ["base", "Base — rapide"], ["small", "Small — bon équilibre (conseillé)"],
  ["medium", "Medium — précis, plus lent"], ["large-v3-turbo", "Large v3 Turbo — le plus précis (GPU / Mac puissant)"]];

export async function renderSettings(view) {
  const [s, sys] = await Promise.all([api("/api/settings"), api("/api/system")]);
  view.innerHTML = `<div class="page-head"><div><h1>Réglages</h1><p class="muted" style="margin:0">Tout est gratuit : choisis simplement les moteurs utilisés.</p></div>
    <button class="btn primary" id="save">${icon("check", "sm")} Enregistrer</button></div>
    <div class="stack" style="gap:18px;max-width:980px">
      <div class="card stack">
        <h2>${icon("sparkles")} IA de détection des moments viraux</h2>
        <div class="engine-cards">${ENGINES.map(([v, t, d]) => `<div class="engine ${s.ai_engine === v ? "on" : ""}" data-e="${v}"><b>${t}</b><span class="small muted">${d}</span></div>`).join("")}</div>
        <div class="small muted">Actuellement utilisée : <b style="color:var(--accent)">${esc(sys.ai_engine)}</b></div>
        <div class="grid2">
          <label class="field">Adresse Ollama<input class="input" id="ollama_url" value="${esc(s.ollama_url)}"></label>
          <label class="field">Modèle Ollama<input class="input" id="ollama_model" value="${esc(s.ollama_model)}" placeholder="qwen2.5:7b"></label>
          <label class="field">Clé API Gemini (gratuite)<input class="input" type="password" id="gemini_api_key" value="${esc(s.gemini_api_key)}" autocomplete="off"></label>
          <label class="field">Modèle Gemini<input class="input" id="gemini_model" value="${esc(s.gemini_model)}"></label>
          <label class="field">Clé API Groq (gratuite)<input class="input" type="password" id="groq_api_key" value="${esc(s.groq_api_key)}" autocomplete="off"></label>
          <label class="field">Modèle Groq<input class="input" id="groq_model" value="${esc(s.groq_model)}"></label>
        </div>
        <div class="row"><button class="btn" id="testai">${icon("bolt", "sm")} Tester l'IA</button><span class="small muted" id="testres"></span></div>
      </div>

      <div class="card stack">
        <h2>${icon("mic")} Transcription (Whisper, local)</h2>
        <label class="field">Modèle<select class="input" id="whisper_model">${WHISPER.map(([v, l]) => `<option value="${v}" ${s.whisper_model === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
        <p class="small faint" style="margin:0">Le modèle est téléchargé automatiquement la première fois (75 Mo à 1,6 Go).</p>
      </div>

      <div class="card stack">
        <h2>${icon("scissors")} Rendu vidéo</h2>
        <div class="grid2">
          <label class="field">Encodeur<select class="input" id="video_encoder">
            <option value="libx264">Processeur (compatible partout)</option>
            <option value="h264_videotoolbox">Puce Apple (Mac M1/M2/M3…, très rapide)</option>
            <option value="h264_nvenc">Carte NVIDIA</option></select></label>
          <label class="field">Vitesse / qualité<select class="input" id="render_preset">
            <option value="ultrafast">Ultra rapide</option><option value="veryfast">Rapide (conseillé)</option><option value="medium">Qualité max</option></select></label>
        </div>
      </div>

      <div class="card stack">
        <h2>${icon("download")} Téléchargement</h2>
        <p class="small muted" style="margin:0">Si YouTube bloque ton serveur (« confirm you're not a bot »), exporte un fichier <code>cookies.txt</code> de ton navigateur (extension « Get cookies.txt LOCALLY ») et importe-le ici.</p>
        <div class="row wrap"><label class="btn">${icon("upload", "sm")} Importer cookies.txt<input type="file" id="cookies" accept=".txt,text/plain" hidden></label>
          ${s.ytdlp_cookies ? `<span class="pill free">Cookies actifs</span><button class="btn ghost danger" id="delcookies">Retirer</button>` : ""}</div>
      </div>

      <div class="card stack">
        <h2>${icon("globe")} Adresse publique</h2>
        <label class="field">URL publique du serveur (pour la connexion des réseaux sociaux)<input class="input" id="public_url" value="${esc(s.public_url)}" placeholder="${esc(sys.base_url)}"></label>
        <p class="small faint" style="margin:0">Laisse vide pour la détection automatique (${esc(sys.base_url)}).</p>
      </div>

      <div class="card"><h2>${icon("info")} Système</h2>
        <div class="row wrap small muted" style="gap:8px 22px"><span>Version ${esc(sys.version)}</span><span>ffmpeg : ${sys.ffmpeg ? "✔" : "✖ manquant"}</span>
        <span>Espace libre : ${sys.disk_free_gb} Go</span><span>Projets : ${sys.projects_size_gb} Go</span></div>
        <p class="small faint">Astuce iPhone / iPad : dans Safari, touche ${icon("share", "sm")} puis « Sur l'écran d'accueil » pour installer NOXPclips comme une appli.</p></div>
    </div>`;

  let engine = s.ai_engine;
  $$("[data-e]").forEach((c) => (c.onclick = () => { engine = c.dataset.e; $$("[data-e]").forEach((x) => x.classList.toggle("on", x === c)); }));
  $("#video_encoder").value = s.video_encoder;
  $("#render_preset").value = s.render_preset;
  const collect = () => {
    const body = { ai_engine: engine };
    ["ollama_url", "ollama_model", "gemini_api_key", "gemini_model", "groq_api_key", "groq_model", "whisper_model", "video_encoder", "render_preset", "public_url"]
      .forEach((k) => (body[k] = $("#" + k).value.trim()));
    return body;
  };
  $("#save").onclick = async () => { await api("/api/settings", { method: "PUT", body: collect() }); toast("Réglages enregistrés ✔", "ok"); renderSettings(view); };
  $("#testai").onclick = async () => {
    await api("/api/settings", { method: "PUT", body: collect() });
    $("#testres").textContent = "Test en cours…";
    try {
      const r = await api("/api/ai/test", { method: "POST" });
      $("#testres").innerHTML = r.ok ? `<span style="color:var(--ok)">✔ ${esc(r.engine)} répond : « ${esc(r.answer)} »</span>` : `<span style="color:var(--warn)">${esc(r.message)}</span>`;
    } catch (e) { $("#testres").textContent = e.message; }
  };
  $("#cookies").onchange = async (e) => {
    if (!e.target.files[0]) return;
    await uploadWithProgress("/api/settings/cookies", e.target.files[0]);
    toast("Cookies importés ✔", "ok");
    renderSettings(view);
  };
  $("#delcookies") && ($("#delcookies").onclick = async () => { await api("/api/settings/cookies", { method: "DELETE" }); renderSettings(view); });
}

export async function renderAnalytics(view) {
  const st = await api("/api/stats");
  const cats = { funny: "😂 Drôles", drama: "🎭 Dramatiques", hype: "⚡ Épiques" };
  const plat = {};
  st.by_platform.forEach((r) => { plat[r.platform] = plat[r.platform] || {}; plat[r.platform][r.status] = r.n; });
  view.innerHTML = `<div class="page-head"><div><h1>Analytics</h1><p class="muted" style="margin:0">Ton activité NOXPclips.</p></div></div>
    <div class="stats-grid">
      <div class="stat"><div class="v">${st.projects}</div><div class="l">Vidéos analysées</div></div>
      <div class="stat"><div class="v">${st.clips}</div><div class="l">Clips créés</div></div>
      <div class="stat"><div class="v" style="color:var(--accent)">${st.avg_score}</div><div class="l">Score viral moyen</div></div>
      <div class="stat"><div class="v">${st.published}</div><div class="l">Publiés</div></div>
      <div class="stat"><div class="v">${st.upcoming}</div><div class="l">À venir</div></div>
      <div class="stat"><div class="v" style="color:${st.failed ? "var(--danger)" : "inherit"}">${st.failed}</div><div class="l">Échecs</div></div>
    </div>
    <div class="grid2" style="margin-top:18px">
      <div class="card"><h3>Clips par catégorie</h3>${st.by_category.map((r) => `<div class="row between" style="padding:8px 0;border-bottom:1px solid var(--border)"><span>${cats[r.category] || r.category}</span><span class="muted">${r.n} clips · score ${Math.round(r.avg)}</span></div>`).join("") || '<p class="muted">Aucun clip.</p>'}</div>
      <div class="card"><h3>Par réseau</h3>${Object.entries(plat).map(([p, s]) => `<div class="row between" style="padding:8px 0;border-bottom:1px solid var(--border)"><span class="row">${icon(p, "sm")} ${esc(PLATFORMS[p]?.short || p)}</span><span class="muted small">${Object.entries(s).map(([k, n]) => `${n} ${STATUS_LABELS[k] || k}`).join(" · ")}</span></div>`).join("") || '<p class="muted">Aucune publication.</p>'}</div>
    </div>
    <div class="card" style="margin-top:18px"><h3>Dernières publications</h3>${st.recent.map((p) => `<div class="agenda-item" data-post="${p.id}" style="margin-bottom:8px">${p.clip && p.clip.thumb_url ? `<img src="${esc(p.clip.thumb_url)}">` : ""}
      <div class="grow"><b>${esc((p.clip || {}).title || "")}</b><div class="small muted row">${icon(p.platform, "sm")} ${fmtDate(p.published_at || p.scheduled_at)}</div></div>
      ${p.result && p.result.url ? `<a class="btn sm" href="${esc(p.result.url)}" target="_blank" rel="noopener">Voir</a>` : ""}</div>`).join("") || '<p class="muted">Rien pour l\'instant.</p>'}</div>`;
  $$("[data-post]").forEach((el) => (el.onclick = (e) => { if (!e.target.closest("a")) openPost(st.recent.find((p) => p.id === el.dataset.post), () => renderAnalytics(view)); }));
}
