// Connexion par navigateur : un Chrome tourne sur le serveur, l'utilisateur s'y connecte depuis l'iPad.
// Sert aux téléchargements YouTube (cookies) et à la publication automatique YouTube Shorts / TikTok.
import { $, api, esc, icon, modal, toast } from "./core.js";

const TEXTS = {
  youtube: {
    title: "Connecter YouTube", icon: "youtube",
    intro: "Connecte-toi <b>une fois</b> à ton compte Google dans un navigateur qui tourne sur ton serveur NOXPclips. Ça débloque les liens YouTube <b>et</b> la publication automatique de tes Shorts.",
    done: "Quand tu vois l'accueil YouTube avec ta photo de profil",
    name: "Nom de ta chaîne (pour t'y retrouver)",
  },
  instagram: {
    title: "Connecter Instagram", icon: "instagram",
    intro: "Connecte-toi <b>une fois</b> à Instagram avec ton identifiant et ton mot de passe, dans un navigateur qui tourne sur ton serveur NOXPclips. Ensuite NOXPclips publie tes Reels tout seul, en public, à l'heure prévue.",
    done: "Quand tu vois ton fil Instagram (tu es connecté)",
    name: "Ton pseudo Instagram (pour t'y retrouver)",
  },
  tiktok: {
    title: "Connecter TikTok", icon: "tiktok",
    intro: "Connecte-toi <b>une fois</b> à TikTok dans un navigateur qui tourne sur ton serveur NOXPclips. Ensuite NOXPclips publie tes clips tout seul, en public, à l'heure prévue.",
    done: "Quand tu vois ton fil TikTok (tu es connecté)",
    name: "Ton pseudo TikTok (pour t'y retrouver)",
  },
};

export function browserLoginModal(target = "youtube", onDone) {
  const T = TEXTS[target] || TEXTS.youtube;
  let timer = null;
  const m = modal(`
    <div class="modal-head"><h2>${icon(T.icon)} ${T.title}</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <p class="muted" style="margin-top:0">${T.intro}</p>
    <ol class="small" style="line-height:1.7;padding-left:20px;margin:0 0 12px">
      <li>Appuie sur <b>Démarrer</b> puis <b>Ouvrir le navigateur</b> : une page s'ouvre avec Chrome à l'intérieur.</li>
      <li>Connecte-toi. Pour taper au clavier : touche le champ, puis la petite flèche <b>›</b> à gauche et l'icône ⌨️.</li>
      <li>${T.done}, reviens ici et appuie sur <b>J'ai terminé</b>.</li>
    </ol>
    <label class="field" style="margin-bottom:12px">${T.name}<input class="input" id="bname" placeholder="ex. @noxp" autocomplete="off"></label>
    <div id="ytstate" class="card flat small" style="margin:0">Prêt.</div>
    <div class="modal-foot">
      <button class="btn" data-close>Fermer</button>
      <a class="btn hidden" id="ytopen" target="_blank" rel="noopener">${icon("right", "sm")} Ouvrir le navigateur</a>
      <button class="btn primary" id="ytstart">${icon("bolt", "sm")} Démarrer</button>
      <button class="btn primary hidden" id="ytdone">${icon("check", "sm")} J'ai terminé</button>
    </div>`, { onClose: () => clearTimeout(timer) });
  const st = $("#ytstate", m.el), open = $("#ytopen", m.el), startBtn = $("#ytstart", m.el), done = $("#ytdone", m.el);

  const show = (s) => {
    const mine = s.target === target;
    const busy = ["installing", "starting"].includes(s.state);
    const running = s.state === "running" && mine;
    st.innerHTML = running ? `✅ ${esc(s.message)}`
      : s.state === "error" ? `<span style="color:var(--danger)">${esc(s.message)}</span>`
      : busy ? `${icon("refresh", "sm spin")} ${esc(s.message)}`
      : s.publishing ? "⏳ Une publication automatique est en cours, attends une minute."
      : target === "youtube" && s.has_cookies ? `<span style="color:var(--ok)">✔ YouTube déjà connecté.</span> Refais la connexion si les liens YouTube sont de nouveau bloqués.`
      : "Prêt.";
    if (running) open.href = s.url.startsWith("http") ? s.url : `${location.protocol}//${location.hostname}:${s.port}${s.url}`;
    open.classList.toggle("hidden", !running);
    done.classList.toggle("hidden", !running);
    startBtn.classList.toggle("hidden", running);
    startBtn.disabled = busy;
    clearTimeout(timer);
    if (busy) timer = setTimeout(poll, 2000);
  };
  const poll = async () => { try { show(await api("/api/youtube-login")); } catch (e) { st.textContent = e.message; } };

  startBtn.onclick = async () => {
    startBtn.disabled = true;
    try { show(await api("/api/youtube-login/start", { method: "POST", body: { target } })); }
    catch (e) { startBtn.disabled = false; st.innerHTML = `<span style="color:var(--danger)">${esc(e.message)}</span>`; }
  };
  done.onclick = async () => {
    done.disabled = true;
    st.innerHTML = `${icon("refresh", "sm spin")} Vérification de la connexion…`;
    try {
      const r = await api("/api/youtube-login/finish", { method: "POST", body: { target, name: $("#bname", m.el).value } });
      toast(`${T.title.replace("Connecter ", "")} connecté ✔ (${r.account})`, "ok");
      m.close();
      onDone && onDone();
    } catch (e) {
      done.disabled = false;
      st.innerHTML = `<span style="color:var(--danger)">${esc(e.message)}</span>`;
      poll();
    }
  };
  poll();
}

export const youtubeLoginModal = (onDone) => browserLoginModal("youtube", onDone);
