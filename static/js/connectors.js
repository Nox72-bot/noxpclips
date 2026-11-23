// Connecteurs : connexion en quelques taps à TikTok, YouTube Shorts et Instagram.
import { $, $$, api, confirmBox, copyText, esc, icon, modal, toast } from "./core.js";
import { browserLoginModal } from "./ytlogin.js";

const NETS = [
  { p: "tiktok", name: "TikTok", how: "Identifiant + mot de passe · publication en public" },
  { p: "youtube", name: "YouTube Shorts", how: "Compte Google + mot de passe · publication en public" },
  { p: "instagram", name: "Instagram Reels", how: "Identifiant + mot de passe · publication en public" },
];

// Instagram : assistant étape par étape (Meta impose une appli, on guide écran par écran)
function instagramWizard(settings, sys, onDone) {
  const uri = sys.redirect_uris.instagram;
  const steps = [
    { t: "Passe ton Instagram en compte pro", b: `Dans l'appli Instagram : <b>Paramètres</b> → <b>Type de compte et outils</b> → <b>Passer à un compte professionnel</b> → <b>Créateur</b>. C'est gratuit et ça ne change rien pour tes abonnés.` },
    { t: "Crée l'appli Meta (une seule fois)", b: `Ouvre <a href="https://developers.facebook.com/apps/creation/" target="_blank" rel="noopener" style="text-decoration:underline">developers.facebook.com/apps/creation</a> → connecte-toi avec Facebook → <b>Créer une app</b> → nom « NOXPclips » → cas d'usage <b>« Gérer les messages et le contenu sur Instagram »</b> → type <b>Entreprise</b> → Créer.` },
    { t: "Relie ton Instagram et colle l'adresse", b: `Sur la page <b>« Configuration de l'API avec connexion Instagram »</b> :<br>1. bouton <b>Ajouter un compte</b> → connecte ton Instagram ;<br>2. en bas, <b>« Configurer la connexion professionnelle Instagram »</b> → colle cette adresse comme URL de redirection :
      <div class="copy-box" style="margin-top:8px"><span class="code">${esc(uri)}</span><button class="icon-btn" data-copy="${esc(uri)}">${icon("copy", "sm")}</button></div>` },
    { t: "Copie les deux codes ici", b: `En haut de cette même page Meta, copie l'<b>ID de l'app Instagram</b> et la <b>clé secrète de l'app Instagram</b> (pas ceux de Facebook) :
      <div class="stack" style="margin-top:10px"><label class="field">ID de l'app Instagram<input class="input" id="ig_id" value="${esc(settings.instagram_app_id || "")}" autocomplete="off" inputmode="numeric"></label>
      <label class="field">Clé secrète de l'app Instagram<input class="input" id="ig_secret" type="password" value="${esc(settings.instagram_app_secret || "")}" autocomplete="off"></label></div>` },
  ];
  let k = 0;
  const m = modal(`<div class="modal-head"><h2>${icon("instagram")} Connecter Instagram</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <div class="wiz-dots" id="dots"></div><div id="wbody"></div>
    <div class="modal-foot"><button class="btn" id="prev">Retour</button><button class="btn primary" id="next">Suivant</button></div>`);
  const draw = () => {
    $("#dots", m.el).innerHTML = steps.map((_, i) => `<span class="${i <= k ? "on" : ""}"></span>`).join("");
    $("#wbody", m.el).innerHTML = `<div class="small faint">Étape ${k + 1} sur ${steps.length} · ≈ 10 min au total, une seule fois</div><h3 style="margin:6px 0 10px">${steps[k].t}</h3><div class="small" style="line-height:1.65">${steps[k].b}</div>`;
    $$("[data-copy]", m.el).forEach((b) => (b.onclick = () => copyText(b.dataset.copy)));
    $("#prev", m.el).disabled = k === 0;
    $("#next", m.el).innerHTML = k === steps.length - 1 ? `${icon("link", "sm")} Connecter Instagram` : "Suivant";
  };
  $("#prev", m.el).onclick = () => { if (k > 0) { k--; draw(); } };
  $("#next", m.el).onclick = async () => {
    if (k < steps.length - 1) { k++; draw(); return; }
    const id = $("#ig_id", m.el).value.trim(), secret = $("#ig_secret", m.el).value.trim();
    if (!id || !secret) return toast("Colle l'ID et la clé secrète de l'app Instagram", "err");
    await api("/api/settings", { method: "PUT", body: { instagram_app_id: id, instagram_app_secret: secret } });
    location.href = "/api/oauth/instagram/start";  // page de connexion Instagram, puis retour ici
  };
  draw();
}

const EXPRESS = [
  { p: "tiktok", name: "TikTok", user: "E-mail ou @pseudo TikTok" },
  { p: "instagram", name: "Instagram", user: "Pseudo, e-mail ou téléphone" },
  { p: "youtube", name: "YouTube", user: "Adresse Gmail de ta chaîne" },
];

function expressBox(accounts) {
  const todo = EXPRESS.filter(({ p }) => !accounts.some((a) => a.platform === p && a.method === "browser"));
  if (!todo.length) return "";
  return `<form class="card express" id="xform" autocomplete="off">
    <h2 style="margin:0 0 4px">${icon("bolt")} Connexion express</h2>
    <p class="small muted" style="margin:0 0 12px">Remplis ce que tu veux connecter puis touche <b>Tout connecter</b> : NOXPclips se connecte tout seul et ne te dérange que si un réseau demande un code.</p>
    ${todo.map(({ p, name, user }) => `<div class="x-row" data-x="${p}">
      <span class="plat-logo ${p}" style="width:40px;height:40px;border-radius:12px">${icon(p)}</span>
      <input class="input" data-u placeholder="${esc(user)}" autocapitalize="off" autocorrect="off" spellcheck="false" aria-label="${esc(name)} : identifiant">
      <input class="input" data-pw type="password" placeholder="Mot de passe ${esc(name)}" aria-label="${esc(name)} : mot de passe">
      <span class="x-state small faint" data-st></span></div>`).join("")}
    <button class="btn primary block" id="xgo" style="margin-top:6px">${icon("bolt", "sm")} Tout connecter</button>
    <p class="small faint" style="margin:8px 0 0">Tes mots de passe sont tapés par le robot sur les vraies pages de connexion, puis oubliés : NOXPclips ne les enregistre pas.</p>
  </form>`;
}

async function waitStatus(ok, ms) {
  const end = Date.now() + ms;
  let s = {};
  while (Date.now() < end) {
    s = await api("/api/live/status").catch(() => ({}));
    if (ok(s) || s.state === "error" || s.state === "closed") return s;
    await new Promise((r) => setTimeout(r, 700));
  }
  return s;
}

async function runExpress(reload) {
  const rows = $$(".x-row").map((r) => ({ el: r, p: r.dataset.x, u: $("[data-u]", r).value.trim(), pw: $("[data-pw]", r).value }))
    .filter((r) => r.u && r.pw);
  if (!rows.length) return toast("Remplis au moins un identifiant et son mot de passe", "err");
  $("#xgo").disabled = true;
  const mark = (r, html) => { $("[data-st]", r.el).innerHTML = html; };
  let ok = 0;
  for (const r of rows) {
    mark(r, `${icon("refresh", "sm spin")} Connexion…`);
    try {
      await api("/api/live/start", { method: "POST", body: { target: r.p } });
      let s = await waitStatus((x) => x.state === "ready" && x.target === r.p, 180000);
      if (s.state !== "ready") throw new Error(s.message || "Navigateur indisponible");
      if (!s.logged_in) {
        await api("/api/live/login", { method: "POST", body: { username: r.u, password: r.pw } });
        s = await waitStatus((x) => x.logged_in, 2000);
      }
      $("[data-pw]", r.el).value = "";
      if (s.logged_in) {
        await api("/api/live/finish", { method: "POST", body: { name: r.u } });
        mark(r, `<span style="color:var(--ok)">✔ Connecté</span>`); ok++;
        continue;
      }
      mark(r, `<span style="color:var(--warn)">Vérification demandée…</span>`);
      const done = await browserLoginModal(r.p, null, { resume: true, user: r.u });
      mark(r, done ? `<span style="color:var(--ok)">✔ Connecté</span>` : `<span style="color:var(--danger)">Non connecté</span>`);
      if (done) ok++;
    } catch (e) {
      mark(r, `<span style="color:var(--danger)">${esc(e.message)}</span>`);
    }
  }
  if (ok) toast(`${ok} réseau${ok > 1 ? "x" : ""} connecté${ok > 1 ? "s" : ""} ✔`, "ok");
  setTimeout(reload, 1200);
}

export async function renderConnectors(view, _p, query = {}) {
  if (query.connected) toast(`Compte connecté : ${query.connected} ✔`, "ok");
  if (query.error) toast(query.error, "err");
  if (query.connected || query.error) history.replaceState(null, "", "#/connectors");
  const [accounts, settings, sys] = await Promise.all([api("/api/accounts"), api("/api/settings"), api("/api/system")]);
  const reload = () => renderConnectors(view, {}, {});

  view.innerHTML = `<div class="page-head"><div><h1>Connecteurs</h1>
    <p class="muted" style="margin:0">Connecte tes réseaux une fois : NOXPclips publie ensuite tes clips tout seul aux heures prévues.</p></div></div>
    ${expressBox(accounts)}
    <div class="conn-grid">${NETS.map(({ p, name, how }) => {
      const mine = accounts.filter((a) => a.platform === p);
      return `<div class="card conn ${mine.length ? "ok" : ""}">
        <div class="plat-logo ${p}" style="width:64px;height:64px;border-radius:18px">${icon(p, "lg")}</div>
        <h3 style="margin:12px 0 2px">${name}</h3>
        <div class="small ${mine.length ? "" : "muted"}" style="${mine.length ? "color:var(--ok)" : ""}">${mine.length ? `✔ Connecté : ${mine.map((a) => esc(a.name)).join(", ")}` : "Non connecté"}</div>
        <div class="small faint" style="margin:6px 0 14px">${how}</div>
        <button class="btn ${mine.length ? "" : "primary"} block" data-connect="${p}">${icon(mine.length ? "refresh" : "link", "sm")} ${mine.length ? "Reconnecter" : "Connecter"}</button>
        ${mine.map((a) => `<button class="btn ghost sm block" style="margin-top:6px" data-disc="${a.id}">${icon("x", "sm")} Déconnecter ${esc(a.name)}</button>`).join("")}
      </div>`;
    }).join("")}</div>
    <div class="card flat small" style="margin-top:16px">${icon("info", "sm")} Tu tapes ton identifiant et ton mot de passe une seule fois, sur la vraie page de connexion du réseau (ouverte dans un navigateur sur ton serveur : NOXPclips ne voit ni ne garde ton mot de passe). Ensuite NOXPclips publie à ta place ; reste à quelques posts par jour. Les posts partent quand ton Codespace est allumé.
      <div style="margin-top:8px"><a href="#/accounts" style="text-decoration:underline">Options avancées (connexions officielles par API)</a> · <a href="#" id="igwiz" style="text-decoration:underline">Instagram par l'API officielle</a></div></div>`;
  $("#igwiz").onclick = (e) => { e.preventDefault(); instagramWizard(settings, sys, reload); };

  api("/api/live/warm", { method: "POST" }).catch(() => {});  // le navigateur démarre pendant que tu tapes
  $("#xform") && ($("#xform").onsubmit = (e) => { e.preventDefault(); runExpress(reload); });
  $$("[data-connect]").forEach((b) => (b.onclick = () => {
    browserLoginModal(b.dataset.connect, reload);
  }));
  $$("[data-disc]").forEach((b) => (b.onclick = async () => {
    if (!(await confirmBox("Déconnecter ce compte ?", "Déconnecter"))) return;
    await api(`/api/accounts/${b.dataset.disc}`, { method: "DELETE" });
    reload();
  }));
}
