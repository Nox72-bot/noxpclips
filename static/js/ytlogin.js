// Connexion rapide : identifiant + mot de passe tapés dans NOXPclips, le robot les saisit sur la vraie page
// du réseau. La page s'affiche en direct dans la fenêtre (touche / glisse pour un captcha, tape un code).
import { $, api, esc, icon, modal, toast } from "./core.js";

const TEXTS = {
  youtube: { title: "Connecter YouTube", icon: "youtube", user: "Adresse Gmail (compte de ta chaîne)", ph: "toi@gmail.com" },
  tiktok: { title: "Connecter TikTok", icon: "tiktok", user: "E-mail ou nom d'utilisateur TikTok", ph: "@toncompte ou e-mail" },
  instagram: { title: "Connecter Instagram", icon: "instagram", user: "Nom d'utilisateur, e-mail ou téléphone", ph: "toncompte" },
};

export function browserLoginModal(target = "youtube", onDone, opts = {}) {
  // Renvoie une promesse : true si le compte est connecté, false si la fenêtre est fermée avant
  let resolveDone;
  const result = new Promise((r) => { resolveDone = r; });
  const T = TEXTS[target] || TEXTS.youtube;
  let timer = null, finished = false, finishing = false, busy = false;
  const m = modal(`
    <div class="modal-head"><h2>${icon(T.icon)} ${T.title}</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <form id="lf" class="stack ${opts.resume ? "hidden" : ""}" autocomplete="off">
      <label class="field">${T.user}<input class="input" id="lu" value="${esc(opts.user || "")}" placeholder="${esc(T.ph)}" autocapitalize="off" autocorrect="off" spellcheck="false" required></label>
      <label class="field">Mot de passe<div class="row" style="gap:6px"><input class="input grow" id="lp" type="password" required>
        <button class="btn" type="button" id="lshow" title="Afficher">${icon("eye", "sm")}</button></div></label>
      <button class="btn primary block" id="lgo">${icon("bolt", "sm")} Se connecter</button>
      <p class="small faint" style="margin:0">Le robot tape tes identifiants sur la vraie page de connexion. NOXPclips n'enregistre pas ton mot de passe.</p>
    </form>
    <div id="lstate" class="small" style="margin:12px 0 8px">${icon("refresh", "sm spin")} Ouverture de la page de connexion…</div>
    <div class="live-wrap" id="lwrap"><img id="limg" alt="Page de connexion en direct" draggable="false"></div>
    <div class="live-tools">
      <input class="input grow" id="ltext" placeholder="Code reçu par SMS / e-mail, ou texte à taper…" autocomplete="one-time-code">
      <button class="btn" id="lsend">${icon("send", "sm")} Taper</button>
      <button class="btn" id="lenter" title="Touche Entrée">⏎</button>
      <button class="btn" id="lback" title="Effacer un caractère">⌫</button>
      <button class="btn" id="lreload" title="Recommencer">${icon("refresh", "sm")}</button>
    </div>
    <p class="small faint" style="margin:8px 0 0">Captcha ou bouton à toucher ? Touche ou fais glisser directement sur l'image.</p>`, {
    wide: true,
    // le navigateur reste ouvert quelques minutes : se reconnecter / connecter un autre réseau est instantané
    onClose: () => { clearTimeout(timer); if (!finished) resolveDone(false); },
  });
  const st = $("#lstate", m.el), img = $("#limg", m.el), wrap = $("#lwrap", m.el);
  const say = (html) => { st.innerHTML = html; };

  const finish = async () => {
    if (finishing) return;
    finishing = true;
    say(`${icon("refresh", "sm spin")} Connexion réussie, enregistrement du compte…`);
    try {
      const r = await api("/api/live/finish", { method: "POST", body: { name: $("#lu", m.el).value.trim() } });
      finished = true;
      toast(`${T.title.replace("Connecter ", "")} connecté ✔ (${r.account})`, "ok");
      m.close();
      resolveDone(true);
      onDone && onDone();
    } catch (e) { finishing = false; say(`<span style="color:var(--danger)">${esc(e.message)}</span>`); }
  };

  const poll = async () => {
    if (!document.body.contains(m.el)) return;
    try {
      const s = await api("/api/live/status");
      if (s.has_shot) img.src = `/api/live/shot?t=${Date.now()}`;
      if (s.logged_in) return finish();
      if (s.state === "error" || s.state === "closed") return say(`<span style="color:var(--danger)">${esc(s.message || "Navigateur fermé.")}</span> <a href="#" id="lretry">Réessayer</a>`);
      const again = $("#lf", m.el).classList.contains("hidden") ? ` <a href="#" id="lagain">Modifier les identifiants</a>` : "";
      if (!busy) say(s.state === "ready" ? `✅ ${esc(s.message)}${again}` : `${icon("refresh", "sm spin")} ${esc(s.message || "Démarrage…")}`);
    } catch { /* on réessaie */ }
    timer = setTimeout(poll, 1100);
  };
  m.el.addEventListener("click", (e) => {
    if (e.target.id === "lretry") { e.preventDefault(); start(); }
    if (e.target.id === "lagain") { e.preventDefault(); $("#lf", m.el).classList.remove("hidden"); }
  });
  const start = async () => {
    try { await api("/api/live/start", { method: "POST", body: { target, resume: !!opts.resume } }); } catch (e) { return say(`<span style="color:var(--danger)">${esc(e.message)}</span>`); }
    clearTimeout(timer);
    poll();
  };

  const act = async (body) => {
    try { await api("/api/live/action", { method: "POST", body }); } catch (e) { toast(e.message, "err"); }
  };
  $("#lshow", m.el).onclick = () => { const i = $("#lp", m.el); i.type = i.type === "password" ? "text" : "password"; };
  $("#lf", m.el).onsubmit = async (e) => {
    e.preventDefault();
    busy = true;
    $("#lgo", m.el).disabled = true;
    say(`${icon("refresh", "sm spin")} Le robot saisit tes identifiants…`);
    try {
      const s = await api("/api/live/login", { method: "POST", body: { username: $("#lu", m.el).value.trim(), password: $("#lp", m.el).value } });
      $("#lp", m.el).value = "";
      $("#lf", m.el).classList.add("hidden");  // place pour la page en direct
      say(esc(s.message || "") + ` <a href="#" id="lagain">Modifier les identifiants</a>`);
    } catch (err) { say(`<span style="color:var(--danger)">${esc(err.message)}</span>`); }
    finally { busy = false; $("#lgo", m.el).disabled = false; }
  };
  $("#lsend", m.el).onclick = () => { const t = $("#ltext", m.el); if (t.value) { act({ type: "type", text: t.value, enter: true }); t.value = ""; } };
  $("#ltext", m.el).addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("#lsend", m.el).click(); } });
  $("#lenter", m.el).onclick = () => act({ type: "key", key: "Enter" });
  $("#lback", m.el).onclick = () => act({ type: "key", key: "Backspace" });
  $("#lreload", m.el).onclick = () => act({ type: "reload" });

  // toucher / glisser sur l'image = clic / glisser dans la vraie page
  let pts = null;
  const rel = (e) => { const r = img.getBoundingClientRect(); return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))]; };
  wrap.addEventListener("pointerdown", (e) => { if (!img.src) return; e.preventDefault(); wrap.setPointerCapture(e.pointerId); pts = [rel(e)]; });
  wrap.addEventListener("pointermove", (e) => { if (pts) { const p = rel(e); const l = pts[pts.length - 1]; if (Math.hypot(p[0] - l[0], p[1] - l[1]) > 0.01) pts.push(p); } });
  wrap.addEventListener("pointerup", () => {
    if (!pts) return;
    const a = pts[0], b = pts[pts.length - 1];
    if (pts.length > 2 && Math.hypot(b[0] - a[0], b[1] - a[1]) > 0.02) act({ type: "drag", points: pts.slice(0, 40) });
    else act({ type: "click", x: a[0], y: a[1] });
    pts = null;
  });
  start();
  return result;
}

export const youtubeLoginModal = (onDone) => browserLoginModal("youtube", onDone);
