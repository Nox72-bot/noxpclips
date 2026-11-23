import { $$, api, confirmBox, copyText, esc, icon, toast } from "./core.js";
import { browserLoginModal } from "./ytlogin.js";

const CONF = {
  youtube: {
    title: "YouTube Shorts", short: "YouTube", browser: true,
    desc: "Tes clips publiés automatiquement en Shorts, en public, à l'heure prévue.",
    apiNote: "Sans risque pour le compte, mais tant que ton projet Google n'a pas passé l'audit YouTube, les vidéos envoyées par l'API sont mises en <b>privé</b>.",
    guideTitle: "Configurer l'appli Google (≈15 min)",
    fields: [["youtube_client_id", "Client ID"], ["youtube_client_secret", "Client secret"]],
    steps: [
      'Ouvre <a href="https://console.cloud.google.com/projectcreate" target="_blank" rel="noopener">console.cloud.google.com</a> et crée un projet « NOXPclips ».',
      'Active <a href="https://console.cloud.google.com/apis/library/youtube.googleapis.com" target="_blank" rel="noopener">YouTube Data API v3</a>.',
      'Écran de consentement : type <b>Externe</b>, ton e-mail en « utilisateur test », puis <b>Publier l\'application</b>.',
      'Identifiants → ID client OAuth → « Application Web » → URI de redirection :__URI__',
      "Colle le Client ID et le secret ci-dessous, enregistre, puis « Connecter avec l'API officielle ».",
    ],
  },
  tiktok: {
    title: "TikTok", short: "TikTok", browser: true,
    desc: "Tes clips publiés automatiquement sur TikTok, en public, à l'heure prévue.",
    apiNote: "Sans risque pour le compte, mais tant que TikTok n'a pas validé ton appli, l'API publie en privé ou en brouillon (à valider dans l'appli TikTok).",
    guideTitle: "Configurer l'appli TikTok (≈15 min)",
    fields: [["tiktok_client_key", "Client key"], ["tiktok_client_secret", "Client secret"]],
    steps: [
      '<a href="https://developers.tiktok.com/apps" target="_blank" rel="noopener">developers.tiktok.com/apps</a> → <b>Connect an app</b>.',
      "Ajoute <b>Login Kit</b> et <b>Content Posting API</b>, avec les scopes user.info.basic, video.upload, video.publish.",
      "Login Kit → URI de redirection :__URI__",
      "Sandbox → ajoute ton compte dans « Target users ». Colle le Client key et le secret ci-dessous.",
    ],
  },
  instagram: {
    title: "Instagram Reels", short: "Instagram",
    desc: "Publication automatique des Reels, en public, par l'API officielle d'Instagram (sans risque pour ton compte).",
    guideTitle: "Configurer en 4 étapes (≈10 min, une seule fois)",
    fields: [["instagram_app_id", "ID de l'app Instagram"], ["instagram_app_secret", "Clé secrète de l'app Instagram"]],
    steps: [
      "Dans l'appli Instagram : Paramètres → <b>Type de compte et outils</b> → passe en <b>compte professionnel</b> (Créateur, gratuit).",
      '<a href="https://developers.facebook.com/apps/creation/" target="_blank" rel="noopener">Crée une app Meta</a> → cas d\'usage <b>« Gérer les messages et le contenu sur Instagram »</b> → type <b>Entreprise</b>.',
      "Page « Configuration de l'API avec connexion Instagram » : bouton <b>Ajouter un compte</b> → connecte ton Instagram. Puis, en bas (« Configurer la connexion professionnelle Instagram »), colle cette adresse de redirection :__URI__",
      "En haut de cette même page, copie l'<b>ID de l'app Instagram</b> et la <b>clé secrète de l'app Instagram</b> (pas celles de Facebook) ci-dessous, enregistre, puis « Connecter ».",
    ],
  },
};

export async function renderAccounts(view, _p, query) {
  if (query.connected) toast(`Compte connecté : ${query.connected} ✔`, "ok");
  if (query.error) toast(query.error, "err");
  if (query.connected || query.error) history.replaceState(null, "", "#/accounts");
  const [accounts, settings, sys] = await Promise.all([api("/api/accounts"), api("/api/settings"), api("/api/system")]);
  const https = sys.base_url.startsWith("https://");
  const reload = () => renderAccounts(view, {}, {});

  const accRow = (a, p) => `<div class="acc-row">${a.avatar ? `<img src="${esc(a.avatar)}" alt="" referrerpolicy="no-referrer">` : `<div class="plat-logo ${p}" style="width:34px;height:34px;border-radius:50%">${icon(p, "sm")}</div>`}
    <div class="grow"><b>${esc(a.name)}</b> <span class="pill ${a.method === "browser" ? "free" : ""}" style="font-size:11px">${a.method === "browser" ? "navigateur · public" : "API officielle"}</span>
      ${p === "tiktok" && a.method !== "browser" ? `<div><select class="select-inline small" data-mode="${a.id}"><option value="inbox" ${a.mode !== "direct" ? "selected" : ""}>Mode brouillon (recommandé)</option><option value="direct" ${a.mode === "direct" ? "selected" : ""}>Publication directe</option></select></div>` : ""}</div>
    <button class="icon-btn" data-disc="${a.id}" title="Déconnecter">${icon("x", "sm")}</button></div>`;

  const apiGuide = (p, c, open) => {
    const configured = c.fields.every(([k]) => settings[k]);
    return `<a class="btn ${configured ? "primary" : ""} block" href="/api/oauth/${p}/start" ${configured ? "" : 'data-needconf="1"'}>${icon("link", "sm")} Connecter avec l'API officielle</a>
      <details class="guide" ${open && !configured ? "open" : ""}><summary>${icon("settings", "sm")} ${c.guideTitle} ${configured ? '<span class="pill free">OK</span>' : ""}</summary>
        <ol>${c.steps.map((s) => `<li>${s.replace("__URI__", `<span class="copy-box" style="display:flex;margin-top:6px"><span class="code">${esc(sys.redirect_uris[p])}</span><button class="icon-btn" data-copy="${esc(sys.redirect_uris[p])}">${icon("copy", "sm")}</button></span>`)}</li>`).join("")}</ol>
        <div class="stack" style="margin-top:12px">${c.fields.map(([k, l]) => `<label class="field">${l}<input class="input" data-k="${k}" value="${esc(settings[k] || "")}" autocomplete="off" ${k.includes("secret") ? 'type="password"' : ""}></label>`).join("")}
          <button class="btn" data-save="${p}">${icon("check", "sm")} Enregistrer</button></div>
      </details>`;
  };

  view.innerHTML = `<div class="page-head"><div><h1>Comptes sociaux</h1>
    <p class="muted" style="margin:0">Connecte tes réseaux une fois : NOXPclips publie ensuite tout seul aux heures prévues dans le calendrier.</p></div></div>
    <div class="card flat small" style="margin-bottom:16px">${icon("info", "sm")} La publication automatique se fait quand ton serveur NOXPclips est allumé (Codespace ouvert). S'il était éteint à l'heure prévue, les posts en retard partent dès qu'il redémarre.</div>
    <div class="accounts-grid">${Object.entries(CONF).map(([p, c]) => {
      const mine = accounts.filter((a) => a.platform === p);
      return `<div class="card" data-p="${p}">
        <div class="plat-head"><div class="plat-logo ${p}">${icon(p, "lg")}</div><div class="grow"><h3 style="margin:0">${c.title}</h3>
          <div class="small muted">${mine.length ? `${mine.length} compte(s) connecté(s)` : "Non connecté"}</div></div></div>
        <p class="small muted" style="margin-top:0">${c.desc}</p>
        ${mine.map((a) => accRow(a, p)).join("")}
        ${c.browser ? `<button class="btn primary block" data-browser="${p}">${icon("bolt", "sm")} ${mine.some((a) => a.method === "browser") ? "Reconnecter" : "Connecter"} en 2 minutes</button>
          <p class="small faint" style="margin:8px 0 0">Tu te connectes à ${c.short} dans un navigateur sur ton serveur, puis NOXPclips publie <b>en public</b> à ta place. Aucune appli développeur à créer. Comme c'est un robot qui publie, ${c.short} pourrait le repérer : utilise-le avec modération (quelques posts par jour).</p>
          <details class="guide"><summary>${icon("settings", "sm")} Méthode avancée : API officielle</summary>
            <p class="small muted">${c.apiNote}</p>${apiGuide(p, c, false)}</details>`
        : `${!https ? `<p class="small" style="color:var(--warn)">${c.short} exige une adresse https:// (ton Codespace en a une).</p>` : ""}${apiGuide(p, c, true)}`}
      </div>`;
    }).join("")}
      <div class="card">
        <div class="plat-head"><div class="plat-logo" style="background:var(--surface-3)">${icon("share", "lg")}</div><div><h3 style="margin:0">Facebook, X, Snapchat…</h3><div class="small muted">Partage manuel</div></div></div>
        <p class="small muted">Pour les autres réseaux, planifie un « rappel » dans le calendrier : à l'heure prévue, tu ouvres le post et le bouton <b>Partager</b> envoie le clip directement dans l'appli de ton choix (iPhone / iPad).</p>
      </div>
    </div>`;

  $$("[data-browser]").forEach((b) => (b.onclick = () => browserLoginModal(b.dataset.browser, reload)));
  $$("[data-copy]").forEach((b) => (b.onclick = () => copyText(b.dataset.copy)));
  $$("[data-needconf]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); toast("Renseigne d'abord les identifiants de l'appli (juste en dessous)", "err"); }));
  $$("[data-save]").forEach((b) => (b.onclick = async () => {
    const card = b.closest("[data-p]");
    const body = {};
    $$("[data-k]", card).forEach((i) => (body[i.dataset.k] = i.value.trim()));
    await api("/api/settings", { method: "PUT", body });
    toast("Identifiants enregistrés ✔", "ok");
    reload();
  }));
  $$("[data-disc]").forEach((b) => (b.onclick = async () => {
    if (!(await confirmBox("Déconnecter ce compte ?", "Déconnecter"))) return;
    await api(`/api/accounts/${b.dataset.disc}`, { method: "DELETE" });
    reload();
  }));
  $$("[data-mode]").forEach((s) => (s.onchange = async () => {
    await api(`/api/accounts/${s.dataset.mode}`, { method: "PATCH", body: { mode: s.value } });
    toast(s.value === "direct" ? "Publication directe activée" : "Mode brouillon activé", "ok");
  }));
}
