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

export async function renderConnectors(view, _p, query = {}) {
  if (query.connected) toast(`Compte connecté : ${query.connected} ✔`, "ok");
  if (query.error) toast(query.error, "err");
  if (query.connected || query.error) history.replaceState(null, "", "#/connectors");
  const [accounts, settings, sys] = await Promise.all([api("/api/accounts"), api("/api/settings"), api("/api/system")]);
  const reload = () => renderConnectors(view, {}, {});

  view.innerHTML = `<div class="page-head"><div><h1>Connecteurs</h1>
    <p class="muted" style="margin:0">Touche un réseau pour le connecter. Ensuite, NOXPclips publie tes clips tout seul aux heures prévues dans le calendrier.</p></div></div>
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

  $$("[data-connect]").forEach((b) => (b.onclick = () => {
    browserLoginModal(b.dataset.connect, reload);
  }));
  $$("[data-disc]").forEach((b) => (b.onclick = async () => {
    if (!(await confirmBox("Déconnecter ce compte ?", "Déconnecter"))) return;
    await api(`/api/accounts/${b.dataset.disc}`, { method: "DELETE" });
    reload();
  }));
}
