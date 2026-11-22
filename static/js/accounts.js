import { $, $$, api, confirmBox, copyText, esc, icon, toast } from "./core.js";

const CONF = {
  youtube: {
    title: "YouTube Shorts", desc: "Publication directe et programmation native (YouTube publie même si NOXPclips est éteint).",
    fields: [["youtube_client_id", "Client ID"], ["youtube_client_secret", "Client secret"]],
    steps: [
      'Ouvre <a href="https://console.cloud.google.com/" target="_blank" rel="noopener">console.cloud.google.com</a> et crée un projet « NOXPclips ».',
      "Menu « API et services » → « Bibliothèque » → active <b>YouTube Data API v3</b>.",
      "« Écran de consentement OAuth » → type <b>Externe</b> → remplis le nom de l'appli et ton e-mail → ajoute ton adresse Gmail dans « Utilisateurs tests ». Puis clique sur <b>Publier l'application</b> (sinon la connexion expire tous les 7 jours).",
      "« Identifiants » → « Créer des identifiants » → <b>ID client OAuth</b> → type « Application Web » → dans « URI de redirection autorisés », colle l'adresse ci-dessous.",
      "Copie le Client ID et le Client secret ici, enregistre, puis clique sur « Connecter ».",
      "⚠️ Tant que ton projet Google n'a pas passé l'audit gratuit YouTube (formulaire « YouTube API Services – Audit »), YouTube met les vidéos envoyées par API en <b>privé</b>. Tu peux les passer en public en 1 clic dans YouTube Studio, ou demander l'audit.",
    ],
  },
  tiktok: {
    title: "TikTok", desc: "Envoi en brouillon (tu valides dans l'appli TikTok en 1 tap) ou publication directe après validation de ton appli.",
    fields: [["tiktok_client_key", "Client key"], ["tiktok_client_secret", "Client secret"]],
    steps: [
      'Va sur <a href="https://developers.tiktok.com/" target="_blank" rel="noopener">developers.tiktok.com</a>, connecte-toi et clique sur « Manage apps » → <b>Connect an app</b>.',
      "Ajoute les produits <b>Login Kit</b> et <b>Content Posting API</b> (active « Direct Post » si tu veux publier sans passer par l'appli).",
      "Coche les scopes <b>user.info.basic</b>, <b>video.upload</b> et <b>video.publish</b>.",
      "Dans Login Kit, ajoute l'URI de redirection ci-dessous (elle doit commencer par https://).",
      "En mode Sandbox, ajoute ton compte TikTok dans « Target users ». Copie le Client key et le Client secret ici.",
      "ℹ️ Sans validation (audit) par TikTok, la publication directe est forcée en « privé ». Le mode <b>Brouillon</b> (par défaut) contourne ça : la vidéo arrive dans tes notifications TikTok, prête à publier.",
    ],
  },
  instagram: {
    title: "Instagram Reels", desc: "Publication directe des Reels sur ton compte Instagram professionnel (créateur ou entreprise, gratuit).",
    fields: [["instagram_app_id", "ID de l'app Instagram"], ["instagram_app_secret", "Clé secrète de l'app Instagram"]],
    steps: [
      "Dans l'appli Instagram : Paramètres → Type de compte → passe en <b>compte professionnel</b> (Créateur), c'est gratuit.",
      'Sur <a href="https://developers.facebook.com/apps" target="_blank" rel="noopener">developers.facebook.com/apps</a> → « Créer une app » → cas d\'usage <b>« Gérer les messages et le contenu sur Instagram »</b>.',
      "Dans « Configuration de l'API avec connexion Instagram » : ajoute ton compte en <b>testeur Instagram</b> (Rôles de l'app), puis accepte l'invitation dans Instagram → Paramètres → Apps et sites web.",
      "Section « Configurer la connexion professionnelle Instagram » → ajoute l'URI de redirection ci-dessous (https obligatoire).",
      "Copie l'<b>ID de l'app Instagram</b> et la <b>clé secrète de l'app Instagram</b> ici (attention : pas l'ID de l'app Facebook).",
    ],
  },
};

export async function renderAccounts(view, _p, query) {
  if (query.connected) toast(`Compte connecté : ${query.connected} ✔`, "ok");
  if (query.error) toast(query.error, "err");
  if (query.connected || query.error) history.replaceState(null, "", "#/accounts");
  const [accounts, settings, sys] = await Promise.all([api("/api/accounts"), api("/api/settings"), api("/api/system")]);
  const https = sys.base_url.startsWith("https://");

  view.innerHTML = `<div class="page-head"><div><h1>Comptes sociaux</h1>
    <p class="muted" style="margin:0">Connecte tes réseaux pour publier et programmer automatiquement. 100 % gratuit via les API officielles.</p></div></div>
    ${!https ? `<div class="card flat small" style="border-color:#ffb02066;margin-bottom:16px;color:var(--warn)">${icon("info", "sm")} TikTok et Instagram exigent une adresse <b>https://</b> pour la connexion. Ton serveur est sur <code>${esc(sys.base_url)}</code> : utilise GitHub Codespaces ou Tailscale (voir le guide d'installation). YouTube accepte <code>http://localhost</code>.</div>` : ""}
    <div class="accounts-grid">${Object.entries(CONF).map(([p, c]) => {
      const mine = accounts.filter((a) => a.platform === p);
      const configured = c.fields.every(([k]) => settings[k]);
      return `<div class="card" data-p="${p}">
        <div class="plat-head"><div class="plat-logo ${p}">${icon(p, "lg")}</div><div class="grow"><h3 style="margin:0">${c.title}</h3>
          <div class="small muted">${mine.length ? `${mine.length} compte(s) connecté(s)` : "Non connecté"}</div></div></div>
        <p class="small muted" style="margin-top:0">${c.desc}</p>
        ${mine.map((a) => `<div class="acc-row">${a.avatar ? `<img src="${esc(a.avatar)}" alt="" referrerpolicy="no-referrer">` : `<div class="plat-logo ${p}" style="width:34px;height:34px;border-radius:50%">${icon(p, "sm")}</div>`}
          <div class="grow"><b>${esc(a.name)}</b>${p === "tiktok" ? `<div><select class="select-inline small" data-mode="${a.id}"><option value="inbox" ${a.mode !== "direct" ? "selected" : ""}>Mode brouillon (recommandé)</option><option value="direct" ${a.mode === "direct" ? "selected" : ""}>Publication directe</option></select></div>` : ""}</div>
          <button class="icon-btn" data-disc="${a.id}" title="Déconnecter">${icon("x", "sm")}</button></div>`).join("")}
        <a class="btn ${configured ? "primary" : ""} block" href="/api/oauth/${p}/start" ${configured ? "" : 'data-needconf="1"'}>${icon("link", "sm")} ${mine.length ? "Ajouter un autre compte" : "Connecter"}</a>
        <details class="guide" ${configured ? "" : "open"}><summary>${icon("settings", "sm")} Configurer l'application développeur (gratuit) ${configured ? '<span class="pill free">OK</span>' : ""}</summary>
          <ol>${c.steps.map((s) => `<li>${s}</li>`).join("")}</ol>
          <div class="small muted" style="margin-bottom:6px">URI de redirection à copier :</div>
          <div class="copy-box"><span class="code">${esc(sys.redirect_uris[p])}</span><button class="icon-btn" data-copy="${esc(sys.redirect_uris[p])}">${icon("copy", "sm")}</button></div>
          <div class="stack" style="margin-top:12px">${c.fields.map(([k, l]) => `<label class="field">${l}<input class="input" data-k="${k}" value="${esc(settings[k] || "")}" autocomplete="off" ${k.includes("secret") ? 'type="password"' : ""}></label>`).join("")}
            <button class="btn" data-save="${p}">${icon("check", "sm")} Enregistrer</button></div>
        </details></div>`;
    }).join("")}
      <div class="card">
        <div class="plat-head"><div class="plat-logo" style="background:var(--surface-3)">${icon("share", "lg")}</div><div><h3 style="margin:0">Facebook, X, Snapchat…</h3><div class="small muted">Partage manuel</div></div></div>
        <p class="small muted">Pour les autres réseaux, planifie un « rappel » dans le calendrier : à l'heure prévue, tu ouvres le post et le bouton <b>Partager</b> envoie le clip directement dans l'appli de ton choix (iPhone / iPad).</p>
      </div>
    </div>`;

  $$("[data-copy]").forEach((b) => (b.onclick = () => copyText(b.dataset.copy)));
  $$("[data-needconf]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); toast("Renseigne d'abord les identifiants de l'appli (juste en dessous)", "err"); }));
  $$("[data-save]").forEach((b) => (b.onclick = async () => {
    const card = b.closest("[data-p]");
    const body = {};
    $$("[data-k]", card).forEach((i) => (body[i.dataset.k] = i.value.trim()));
    await api("/api/settings", { method: "PUT", body });
    toast("Identifiants enregistrés ✔", "ok");
    renderAccounts(view, {}, {});
  }));
  $$("[data-disc]").forEach((b) => (b.onclick = async () => {
    if (!(await confirmBox("Déconnecter ce compte ?", "Déconnecter"))) return;
    await api(`/api/accounts/${b.dataset.disc}`, { method: "DELETE" });
    renderAccounts(view, {}, {});
  }));
  $$("[data-mode]").forEach((s) => (s.onchange = async () => {
    await api(`/api/accounts/${s.dataset.mode}`, { method: "PATCH", body: { mode: s.value } });
    toast(s.value === "direct" ? "Publication directe activée" : "Mode brouillon activé", "ok");
  }));
}
