// Connexion YouTube depuis l'iPad : un navigateur tourne sur le serveur, l'utilisateur s'y connecte à distance.
import { $, api, esc, icon, modal, toast } from "./core.js";

export function youtubeLoginModal(onDone) {
  let timer = null;
  const m = modal(`
    <div class="modal-head"><h2>${icon("play")} Se connecter à YouTube</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <p class="muted" style="margin-top:0">YouTube bloque les serveurs gratuits. Pour qu'il te laisse passer, connecte-toi <b>une fois</b> à ton compte
      dans un navigateur qui tourne sur ton serveur NOXPclips. Conseil : utilise un <b>compte Google secondaire</b>.</p>
    <ol class="small" style="line-height:1.7;padding-left:20px;margin:0 0 12px">
      <li>Appuie sur <b>Ouvrir le navigateur</b> : une page s'ouvre avec Chrome à l'intérieur.</li>
      <li>Connecte-toi à Google / YouTube. Pour taper au clavier, touche le champ puis l'icône ⌨️ du menu à gauche (flèche ›).</li>
      <li>Quand tu vois l'accueil YouTube avec ta photo de profil, reviens ici et appuie sur <b>J'ai terminé</b>.</li>
    </ol>
    <div id="ytstate" class="card flat small" style="margin:0">Prêt.</div>
    <div class="modal-foot">
      <button class="btn" data-close>Fermer</button>
      <a class="btn hidden" id="ytopen" target="_blank" rel="noopener">${icon("right", "sm")} Ouvrir le navigateur</a>
      <button class="btn primary" id="ytstart">${icon("bolt", "sm")} Démarrer</button>
      <button class="btn primary hidden" id="ytdone">${icon("check", "sm")} J'ai terminé</button>
    </div>`, { onClose: () => clearTimeout(timer) });
  const st = $("#ytstate", m.el), open = $("#ytopen", m.el), startBtn = $("#ytstart", m.el), done = $("#ytdone", m.el);

  const show = (s) => {
    const busy = ["installing", "starting"].includes(s.state);
    st.innerHTML = s.state === "running" ? `✅ ${esc(s.message)}`
      : s.state === "error" ? `<span style="color:var(--danger)">${esc(s.message)}</span>`
      : busy ? `${icon("refresh", "sm spin")} ${esc(s.message)}`
      : s.has_cookies ? `<span style="color:var(--ok)">✔ Compte YouTube déjà connecté.</span> Tu peux refaire la connexion si les liens YouTube sont de nouveau bloqués.`
      : "Prêt.";
    if (s.state === "running") {
      open.href = s.url.startsWith("http") ? s.url : `${location.protocol}//${location.hostname}:${s.port}${s.url}`;
    }
    open.classList.toggle("hidden", s.state !== "running");
    done.classList.toggle("hidden", s.state !== "running");
    startBtn.classList.toggle("hidden", s.state === "running");
    startBtn.disabled = busy;
    clearTimeout(timer);
    if (busy) timer = setTimeout(poll, 2000);
  };
  const poll = async () => { try { show(await api("/api/youtube-login")); } catch (e) { st.textContent = e.message; } };

  startBtn.onclick = async () => { startBtn.disabled = true; show(await api("/api/youtube-login/start", { method: "POST" })); };
  done.onclick = async () => {
    done.disabled = true;
    st.innerHTML = `${icon("refresh", "sm spin")} Enregistrement de la connexion…`;
    try {
      const r = await api("/api/youtube-login/finish", { method: "POST" });
      toast(`YouTube connecté ✔ (${r.count} cookies). Tu peux coller tes liens YouTube.`, "ok");
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
