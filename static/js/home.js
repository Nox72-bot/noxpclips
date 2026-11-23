import { youtubeLoginModal } from "./ytlogin.js";
import { $, $$, api, confirmBox, esc, fmtDur, go, h, icon, onLeave, store, toast, uploadWithProgress } from "./core.js";

export const RECIPES = {
  viral: { icon: "sparkles", label: "Vidéo longue → clips viraux", short: "Clips viraux",
    options: { split: true, captions: true, hook: true, auto_zoom: true, ai_emojis: true, transitions: false, color_correct: true, progress_bar: true } },
  captions: { icon: "cc", label: "Sous-titres auto", short: "Sous-titres",
    options: { split: false, captions: true, hook: false, auto_zoom: false, ai_emojis: false } },
  reframe: { icon: "phone", label: "Recadrage 9:16", short: "Recadrage",
    options: { split: false, captions: false, hook: false, auto_zoom: false } },
  clean: { icon: "refresh", label: "Nettoyer l'enregistrement", short: "Nettoyer",
    options: { split: false, voice_cleanup: "both", enhance_audio: true, captions: true, hook: false } },
  social: { icon: "wand", label: "Montage réseaux sociaux", short: "Montage réseaux",
    options: { split: true, captions: true, hook: true, auto_zoom: true, ai_emojis: true, transitions: true, color_correct: true, enhance_audio: true } },
  translate: { icon: "translate", label: "Traduire les sous-titres", short: "Traduire",
    options: { split: true, captions: true, translate_to: "anglais" } },
};

export function newDraft(source, recipe = "viral") {
  store.draft = { source, recipe, options: { ...(RECIPES[recipe] || RECIPES.viral).options } };
  go("/new");
}

function statusText(p) {
  if (p.status === "done") return `${p.clip_count} clips`;
  if (p.status === "error") return "Erreur";
  if (p.status === "queued") return "En file d'attente";
  return p.message || "Traitement…";
}

export function projectCard(p) {
  const prog = p.status !== "done" && p.status !== "error" ? `<div class="progress" style="width:${Math.round((p.progress || 0) * 100)}%"></div>` : "";
  const ov = p.status !== "done" ? `<div class="overlay ${p.status === "error" ? "" : ""}" style="color:${p.status === "error" ? "var(--danger)" : "var(--text)"}">${esc(statusText(p))}${p.status !== "error" ? ` · ${Math.round((p.progress || 0) * 100)}%` : ""}</div>` : "";
  const date = new Date(p.created_at * 1000).toLocaleDateString("fr-FR");
  return `<div class="project-card" data-id="${p.id}">
    <div class="project-thumb">${p.thumb_url ? `<img src="${esc(p.thumb_url)}" alt="" loading="lazy">` : ""}${ov}${prog}</div>
    <div class="project-meta row between"><div class="grow"><div class="t">${esc(p.title)}</div>
      <div class="faint small">${p.status === "done" ? `${p.clip_count} clips` : esc(statusText(p))} · ${date}</div></div>
      <button class="icon-btn" data-del="${p.id}" aria-label="Supprimer">${icon("trash", "sm")}</button></div></div>`;
}

export function bindProjectCards(root, reload) {
  $$(".project-card", root).forEach((c) => {
    c.addEventListener("click", async (e) => {
      const del = e.target.closest("[data-del]");
      if (del) {
        e.stopPropagation();
        if (await confirmBox("Supprimer ce projet et tous ses clips ?", "Supprimer")) {
          await api(`/api/projects/${del.dataset.del}`, { method: "DELETE" });
          toast("Projet supprimé");
          reload();
        }
        return;
      }
      go(`/project/${c.dataset.id}`);
    });
  });
}

export async function renderHome(view) {
  let recipe = "viral";
  view.innerHTML = `
  <div class="hero">
    <div class="hero-tabs" id="tabs">
      ${["viral", "social", "captions"].map((k) => `<button data-r="${k}" class="${k === recipe ? "on" : ""}">${icon(RECIPES[k].icon, "sm")} ${RECIPES[k].label}</button>`).join("")}
    </div>
    <div class="hero-box">
      <form class="url-bar" id="urlform">
        ${icon("link")}
        <input id="url" type="text" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Colle un lien YouTube, un live YouTube ou Twitch…">
        <button class="btn primary" id="go">${icon("bolt", "sm")} <span>Obtenir des clips en 1 clic</span></button>
      </form>
      <div class="hero-actions">
        <label class="btn ghost">${icon("upload", "sm")} Importer un fichier<input type="file" id="file" accept="video/*,.mp4,.mov,.mkv,.webm" hidden></label>
        <span class="btn ghost" style="pointer-events:none">${icon("phone", "sm")} Format TikTok 9:16</span>
        <span class="btn ghost" style="pointer-events:none;color:var(--accent)">${icon("bolt", "sm")} 0 crédit · illimité</span>
      </div>
      <div id="apbanner" class="hidden"></div>
      <div id="upprog" class="hidden" style="margin-top:12px"><div class="row between small muted"><span id="upname"></span><span id="uppct">0%</span></div><div class="bar" style="margin-top:6px"><div id="upbar" style="width:0"></div></div></div>
    </div>
  </div>
  <div class="recipes" id="recipes">
    ${Object.entries(RECIPES).map(([k, r]) => `<button class="recipe ${k === recipe ? "on" : ""}" data-r="${k}">${icon(r.icon, "sm")} ${r.short}</button>`).join("")}
  </div>
  <div class="row between" style="margin:42px 0 14px"><h2 style="margin:0">Projets récents</h2><a href="#/projects" class="btn ghost sm">Tout afficher ${icon("right", "sm")}</a></div>
  <div class="projects-grid" id="recent"></div>`;

  const setRecipe = (r) => {
    recipe = r;
    $$("[data-r]", view).forEach((b) => b.classList.toggle("on", b.dataset.r === r));
  };
  $$("[data-r]", view).forEach((b) => (b.onclick = () => setRecipe(b.dataset.r)));

  let auto = false;
  api("/api/autopilot").then((d) => {
    auto = !!d.config.enabled;
    const n = d.accounts.filter((a) => !(d.config.accounts || []).length || d.config.accounts.includes(a.id)).length;
    const b = $("#apbanner");
    if (!b) return;
    b.className = "ap-banner";
    b.innerHTML = auto
      ? `🤖 <b>Pilote automatique activé</b> : colle un ou plusieurs liens (ou importe une vidéo), les meilleurs clips se programment et se publient tout seuls sur ${n} réseau${n > 1 ? "x" : ""}. <a href="#/autopilot">Voir le planning</a>`
      : `💡 Active le <a href="#/autopilot"><b>pilote automatique</b></a> pour que tes vidéos deviennent des posts programmés et publiés tout seuls.`;
    if (auto) $("#go span").textContent = "Créer et publier automatiquement";
  }).catch(() => {});
  const quick = async (body) => {
    const r = await api("/api/projects/quick", { method: "POST", body });
    toast(`${r.length} vidéo${r.length > 1 ? "s" : ""} ajoutée${r.length > 1 ? "s" : ""} au pilote automatique 🤖`, "ok");
    $("#url").value = "";
    load();
  };

  $("#urlform").onsubmit = async (e) => {
    e.preventDefault();
    const url = $("#url").value.trim();
    if (!/^https?:\/\//.test(url)) return toast("Colle un lien valide (https://…)", "err");
    if (auto) {
      try { await quick({ urls: url }); } catch (err) { toast(err.message, "err"); }
      return;
    }
    const btn = $("#go");
    btn.disabled = true;
    btn.innerHTML = `${icon("refresh", "sm spin")} <span>Analyse du lien…</span>`;
    try {
      const info = await api(`/api/info?url=${encodeURIComponent(url)}`);
      newDraft({ url, ...info }, recipe);
    } catch (err) {
      toast(err.message, "err");
      if (/anti-robot|not a bot/i.test(err.message)) {
        if (await confirmBox("YouTube bloque le serveur. Te connecter à YouTube (une seule fois) pour débloquer ?", "Se connecter", false)) {
          youtubeLoginModal();
        }
        return;
      }
      if (await confirmBox("Impossible de lire les infos du lien. Continuer quand même ?", "Continuer", false)) {
        newDraft({ url, title: "Vidéo", duration: 0 }, recipe);
      }
    } finally {
      btn.disabled = false;
      btn.innerHTML = `${icon("bolt", "sm")} <span>Obtenir des clips en 1 clic</span>`;
    }
  };

  $("#file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    $("#upprog").classList.remove("hidden");
    $("#upname").textContent = f.name;
    try {
      const res = await uploadWithProgress("/api/upload", f, (p) => {
        $("#uppct").textContent = Math.round(p * 100) + "%";
        $("#upbar").style.width = p * 100 + "%";
      });
      if (auto) { $("#upprog").classList.add("hidden"); await quick({ upload_id: res.upload_id, title: res.title }); return; }
      newDraft({ upload_id: res.upload_id, title: res.title, duration: res.duration, thumbnail: res.thumbnail, kind: "upload" }, recipe);
    } catch (err) {
      toast(err.message, "err");
      $("#upprog").classList.add("hidden");
    }
  };

  const load = async () => {
    const list = await api("/api/projects");
    const el = $("#recent");
    if (!el) return;
    el.innerHTML = list.length ? list.slice(0, 8).map(projectCard).join("")
      : `<div class="empty" style="grid-column:1/-1">${icon("sparkles")}<p>Aucun projet pour l'instant.<br>Colle un lien de vidéo ou de live pour créer tes premiers clips.</p></div>`;
    bindProjectCards(el, load);
    return list.some((p) => !["done", "error"].includes(p.status));
  };
  let timer;
  const loop = async () => { if (await load()) timer = setTimeout(loop, 3000); };
  loop();
  onLeave(() => clearTimeout(timer));
}

export async function renderProjects(view) {
  view.innerHTML = `<div class="page-head"><div><h1>Mes projets</h1><p class="muted" style="margin:0">Toutes tes vidéos analysées et leurs clips.</p></div>
    <a class="btn primary" href="#/">${icon("plus", "sm")} Nouveau projet</a></div><div class="projects-grid" id="all"></div>`;
  let timer;
  const load = async () => {
    const list = await api("/api/projects");
    const el = $("#all");
    if (!el) return;
    el.innerHTML = list.length ? list.map(projectCard).join("") : `<div class="empty" style="grid-column:1/-1">${icon("folder")}<p>Aucun projet.</p></div>`;
    bindProjectCards(el, load);
    if (list.some((p) => !["done", "error"].includes(p.status))) timer = setTimeout(load, 3000);
  };
  load();
  onLeave(() => clearTimeout(timer));
}
