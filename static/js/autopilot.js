// Pilote automatique : tu ajoutes des vidéos, NOXPclips crée les clips, les programme et les publie tout seul.
import { $, $$, PLATFORMS, api, confirmBox, esc, icon, onLeave, toast, uploadWithProgress } from "./core.js";

const STATUS = {
  scheduled: ["Programmé", ""], publishing: ["Publication…", "free"], published: ["Publié ✔", "free"],
  scheduled_on_platform: ["Publié ✔", "free"], failed: ["Échec", "danger"],
};
const TZS = ["Europe/Paris", "Europe/Brussels", "Europe/Zurich", "America/Montreal", "Africa/Casablanca", "Africa/Abidjan", "Indian/Reunion", "UTC"];

const dayLabel = (ts) => {
  const d = new Date(ts * 1000), t = new Date();
  const diff = Math.round((new Date(d.toDateString()) - new Date(t.toDateString())) / 86400000);
  if (diff === 0) return "Aujourd'hui";
  if (diff === 1) return "Demain";
  if (diff === -1) return "Hier";
  return d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
};

export async function addVideosBox(onDone) {
  // boîte « ajoute tes vidéos » réutilisée sur l'accueil et sur cette page
  return `<form class="ap-add" id="apform">
      <textarea class="input" id="apurls" rows="2" placeholder="Colle un ou plusieurs liens YouTube / Twitch (un par ligne)…"></textarea>
      <div class="row wrap" style="gap:8px">
        <button class="btn primary" id="apgo">${icon("bolt", "sm")} Ajouter au pilote automatique</button>
        <label class="btn">${icon("upload", "sm")} Importer une vidéo<input type="file" id="apfile" accept="video/*,.mp4,.mov,.mkv,.webm" hidden></label>
        <span class="small faint" id="approg"></span>
      </div></form>`;
}

export function bindAddVideos(onDone) {
  const send = async (body) => {
    const r = await api("/api/projects/quick", { method: "POST", body });
    toast(`${r.length} vidéo${r.length > 1 ? "s" : ""} ajoutée${r.length > 1 ? "s" : ""} : les clips se créent puis se programment tout seuls 🤖`, "ok");
    onDone && onDone();
  };
  $("#apform").onsubmit = async (e) => {
    e.preventDefault();
    const urls = $("#apurls").value.trim();
    if (!/https?:\/\//.test(urls)) return toast("Colle au moins un lien (https://…)", "err");
    $("#apgo").disabled = true;
    try { await send({ urls }); $("#apurls").value = ""; } catch (err) { toast(err.message, "err"); }
    finally { $("#apgo").disabled = false; }
  };
  $("#apfile").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const res = await uploadWithProgress("/api/upload", f, (p) => { $("#approg").textContent = `Envoi ${Math.round(p * 100)} %`; });
      $("#approg").textContent = "";
      await send({ upload_id: res.upload_id, title: res.title });
    } catch (err) { toast(err.message, "err"); $("#approg").textContent = ""; }
  };
}

export async function renderAutopilot(view) {
  let timer = null;
  onLeave(() => clearTimeout(timer));

  const draw = async () => {
    const d = await api("/api/autopilot");
    const c = d.config;
    const sel = new Set(c.accounts || []);
    const accs = d.accounts;
    const active = accs.filter((a) => !sel.size || sel.has(a.id));
    const groups = {};
    d.posts.forEach((p) => { (groups[dayLabel(p.scheduled_at)] ||= []).push(p); });

    view.innerHTML = `<div class="page-head"><div><h1>Pilote automatique</h1>
        <p class="muted" style="margin:0">Ajoute tes vidéos : NOXPclips crée les clips, choisit les meilleurs, les programme aux meilleures heures et les publie tout seul sur tes réseaux.</p></div>
        <label class="ap-switch ${c.enabled ? "on" : ""}"><span>${c.enabled ? "Activé" : "Désactivé"}</span><label class="toggle"><input type="checkbox" id="enabled" ${c.enabled ? "checked" : ""}><span></span></label></label></div>

      <div class="ap-checks">
        <div class="ap-check ${active.length ? "ok" : "ko"}">${active.length ? "✔" : "✖"} ${active.length ? `${active.length} compte${active.length > 1 ? "s" : ""} : ${active.map((a) => esc(a.name)).join(", ")}` : `Aucun réseau connecté — <a href="#/connectors">Connecteurs</a>`}</div>
        <div class="ap-check ${d.ai ? "ok" : "warn"}">${d.ai ? "✔ IA Gemini / Groq : titres et choix des clips au top" : "⚠ Sans clé Gemini, les titres et le choix des clips sont plus simples (Réglages)"}</div>
        <div class="ap-check warn">⚠ Les posts partent quand ton serveur est allumé (Codespace ouvert). En retard ? Ils partent dès qu'il redémarre.</div>
      </div>

      <div class="card" style="margin-bottom:16px"><h2 style="margin-top:0">${icon("plus")} Ajoute tes vidéos</h2>${await addVideosBox()}</div>

      <div class="ap-layout">
        <div class="card">
          <div class="row between wrap" style="gap:8px"><h2 style="margin:0">${icon("calendar")} Planning</h2>
            <button class="btn sm" id="fill">${icon("refresh", "sm")} Programmer mes clips existants (${d.candidates})</button></div>
          ${Object.keys(groups).length ? Object.entries(groups).map(([day, posts]) => `<div class="ap-day">${esc(day)}</div>
            ${posts.map((p) => {
              const [lab, cls] = STATUS[p.status] || [p.status, ""];
              const t = new Date(p.scheduled_at * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
              return `<div class="ap-post">
                <div class="ap-time">${t}</div>
                <div class="ap-thumb">${p.clip && p.clip.thumb_url ? `<img src="${esc(p.clip.thumb_url)}" alt="" loading="lazy">` : ""}</div>
                <div class="grow" style="min-width:0">
                  <div class="ap-head"><span class="plat-logo ${p.platform}" style="width:22px;height:22px;border-radius:6px">${icon(p.platform, "sm")}</span>
                    <b class="small">${esc(p.account_name || PLATFORMS[p.platform]?.short || p.platform)}</b>
                    <span class="pill ${cls}" style="font-size:11px">${lab}</span></div>
                  <div class="small" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(p.clip ? p.clip.title : "Clip supprimé")}${p.clip ? ` · <span class="faint">score ${p.clip.score}</span>` : ""}</div>
                  ${p.error ? `<div class="small" style="color:${p.status === "failed" ? "var(--danger)" : "var(--warn)"}">${esc(p.error.slice(0, 220)).replace(/\(capture : ([\w.-]+\.png)\)/, '(<a href="/api/browser-shots/$1" target="_blank" style="text-decoration:underline">voir la capture</a>)')}</div>` : ""}
                  ${p.result && p.result.url ? `<a class="small" href="${esc(p.result.url)}" target="_blank" rel="noopener" style="text-decoration:underline">Voir le post</a>` : ""}
                </div>
                ${["scheduled", "failed"].includes(p.status) ? `<div class="ap-actions"><button class="icon-btn" title="Publier maintenant" data-now="${p.id}">${icon("send", "sm")}</button><button class="icon-btn" title="Retirer du planning" data-del="${p.id}">${icon("trash", "sm")}</button></div>` : ""}
              </div>`;
            }).join("")}`).join("")
          : `<div class="empty">${icon("calendar")}<p>Rien de programmé pour l'instant.<br>Ajoute une vidéo ci-dessus : ses meilleurs clips arriveront ici tout seuls.</p></div>`}
        </div>

        <div class="card stack">
          <h2 style="margin:0">${icon("settings")} Réglages</h2>
          <div><div class="small muted" style="margin-bottom:6px">Publier sur</div>
            ${accs.length ? accs.map((a) => `<label class="row small" style="gap:8px;margin-bottom:6px"><input type="checkbox" data-acc="${a.id}" ${!sel.size || sel.has(a.id) ? "checked" : ""}>
              <span class="plat-logo ${a.platform}" style="width:22px;height:22px;border-radius:6px">${icon(a.platform, "sm")}</span>${esc(a.name)}</label>`).join("")
            : `<a class="btn sm" href="#/connectors">${icon("plug", "sm")} Connecter un réseau</a>`}</div>
          <div><div class="small muted" style="margin-bottom:6px">Heures de publication (heures de pointe conseillées)</div>
            <div class="row wrap" style="gap:6px" id="times">${(c.times || []).map((t) => `<span class="ap-timechip"><input type="time" value="${esc(t)}" class="input"><button class="icon-btn" data-rmtime title="Retirer">${icon("x", "sm")}</button></span>`).join("")}
              <button class="btn sm" id="addtime">${icon("plus", "sm")}</button></div></div>
          <div class="grid2">
            <label class="field">Posts par jour et par réseau<select class="input" id="per_day">${[1, 2, 3, 4, 5, 6].map((n) => `<option ${+c.per_day === n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
            <label class="field">Clips publiés par vidéo<select class="input" id="max_per_video">${[1, 2, 3, 4, 5, 6, 8, 10].map((n) => `<option ${+c.max_per_video === n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
            <label class="field">Score viral minimum<select class="input" id="min_score">${[55, 60, 65, 70, 75, 80, 85].map((n) => `<option ${+c.min_score === n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
            <label class="field">Fuseau horaire<select class="input" id="timezone">${[...new Set([c.timezone, Intl.DateTimeFormat().resolvedOptions().timeZone, ...TZS])].filter(Boolean).map((z) => `<option ${c.timezone === z ? "selected" : ""}>${esc(z)}</option>`).join("")}</select></label>
          </div>
          <button class="btn primary" id="save">${icon("check", "sm")} Enregistrer</button>
        </div>
      </div>`;

    bindAddVideos(draw);
    const collect = () => {
      const ids = $$("[data-acc]").filter((x) => x.checked).map((x) => x.dataset.acc);
      return {
        enabled: $("#enabled").checked,
        accounts: ids.length === accs.length ? [] : ids,
        times: $$("#times input[type=time]").map((i) => i.value).filter(Boolean),
        per_day: +$("#per_day").value, max_per_video: +$("#max_per_video").value, min_score: +$("#min_score").value,
        timezone: $("#timezone").value,
      };
    };
    const save = async (msg) => { await api("/api/autopilot", { method: "PUT", body: collect() }); if (msg) toast(msg, "ok"); draw(); };
    $("#enabled").onchange = () => save($("#enabled").checked ? "Pilote automatique activé 🤖" : "Pilote automatique désactivé");
    $("#save").onclick = () => save("Réglages enregistrés ✔");
    $("#addtime").onclick = (e) => {
      e.preventDefault();
      e.currentTarget.insertAdjacentHTML("beforebegin", `<span class="ap-timechip"><input type="time" value="20:00" class="input"><button class="icon-btn" data-rmtime title="Retirer">${icon("x", "sm")}</button></span>`);
    };
    $("#times").addEventListener("click", (e) => { const b = e.target.closest("[data-rmtime]"); if (b) { e.preventDefault(); b.parentElement.remove(); } });
    $("#fill").onclick = async () => {
      if (!$("#enabled").checked) await api("/api/autopilot", { method: "PUT", body: { ...collect(), enabled: true } });
      const r = await api("/api/autopilot/fill", { method: "POST" });
      toast(r.count ? `${r.count} posts programmés ✔` : "Rien de nouveau à programmer (clips déjà programmés ou score trop bas)", r.count ? "ok" : "");
      draw();
    };
    $$("[data-now]").forEach((b) => (b.onclick = async () => {
      await api(`/api/posts/${b.dataset.now}/publish`, { method: "POST" });
      toast("Publication lancée (quelques minutes)…", "ok");
      setTimeout(draw, 1500);
    }));
    $$("[data-del]").forEach((b) => (b.onclick = async () => {
      if (!(await confirmBox("Retirer ce post du planning ?", "Retirer"))) return;
      await api(`/api/posts/${b.dataset.del}`, { method: "DELETE" });
      draw();
    }));
    clearTimeout(timer);
    if (d.posts.some((p) => p.status === "publishing")) timer = setTimeout(draw, 5000);
  };
  draw();
}
