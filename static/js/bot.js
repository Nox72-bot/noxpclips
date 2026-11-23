// Bot : discussion avec NOX (idées de clips, résultats du scroll TikTok, commandes).
import { $, $$, api, confirmBox, esc, icon, onLeave, toast } from "./core.js";

const SUGGESTIONS = [
  "Lance un scan TikTok #gtarp #gta6",
  "Donne-moi 3 idées de clips à poster aujourd'hui",
  "Qu'est-ce qui marche le plus en ce moment dans ma niche ?",
  "Quels hashtags je devrais utiliser cette semaine ?",
  "Active le passage automatique tous les jours",
];
const n = (v) => (v >= 1e6 ? (v / 1e6).toFixed(1).replace(".0", "") + " M" : v >= 1e3 ? Math.round(v / 1e3) + " k" : String(v || 0));

function cardHtml(c) {
  return `<a class="bot-card" href="${esc(c.url)}" target="_blank" rel="noopener">
    <div class="bot-cover">${c.cover ? `<img src="${esc(c.cover)}" alt="" loading="lazy">` : icon("tiktok")}</div>
    <div style="min-width:0"><div class="small" style="font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.desc || "(sans description)")}</div>
      <div class="small faint">@${esc(c.author)} · ▶ ${n(c.plays)} · ↗ ${n(c.shares)} · score ${c.score}</div>
      ${c.idea ? `<div class="small" style="margin-top:3px">💡 ${esc(c.idea)}</div>` : ""}</div></a>`;
}

function msgHtml(m) {
  const text = esc(m.text).replace(/\n/g, "<br>");
  return m.role === "user"
    ? `<div class="msg me"><div class="bubble">${text}</div></div>`
    : `<div class="msg bot"><div class="avatar">${icon("bot", "sm")}</div><div class="bubble">${text}${(m.cards || []).length ? `<div class="bot-cards">${m.cards.map(cardHtml).join("")}</div>` : ""}</div></div>`;
}

export async function renderBot(view) {
  let timer = null;
  onLeave(() => clearTimeout(timer));
  view.innerHTML = `<div class="page-head"><div><h1>Bot NOX</h1>
      <p class="muted bot-desc" style="margin:0">Discute avec ton bot : il connaît les vidéos TikTok qui cartonnent, les tendances et tes clips, et peut lancer un scroll TikTok pour toi.</p></div>
      <button class="btn ghost sm" id="clear">${icon("trash", "sm")} Effacer</button></div>
    <div class="chat card">
      <div id="scan" class="small"></div>
      <div class="chat-log" id="log"></div>
      <div class="chips chat-sugg" id="sugg">${SUGGESTIONS.map((s) => `<button class="chip sm" data-s="${esc(s)}">${esc(s)}</button>`).join("")}</div>
      <form class="chat-input" id="form"><textarea class="input" id="msg" rows="1" placeholder="Écris à NOX… (ex. « trouve-moi des idées GTA RP drôles »)"></textarea>
        <button class="btn primary" id="send" aria-label="Envoyer">${icon("send", "sm")}</button></form>
    </div>`;
  const log = $("#log"), input = $("#msg");

  const scroll = () => { log.scrollTop = log.scrollHeight; };
  const showScan = (st) => {
    const el = $("#scan");
    if (!el) return;
    el.innerHTML = st && st.state === "running"
      ? `<div class="scan-bar">${icon("refresh", "sm spin")} ${esc(st.message || "Le bot scrolle TikTok…")} <div class="bar" style="margin-top:6px"><div style="width:${Math.round((st.progress || 0) * 100)}%"></div></div></div>` : "";
    clearTimeout(timer);
    if (st && st.state === "running") timer = setTimeout(async () => showScan((await api("/api/bot")).status), 4000);
  };
  const load = async () => {
    const d = await api("/api/bot");
    log.innerHTML = d.messages.length ? d.messages.map(msgHtml).join("")
      : msgHtml({ role: "bot", text: "Salut ! Moi c'est NOX 🤖\nJe scrolle TikTok pour toi, je repère ce qui cartonne et je te propose des idées de clips à faire avec tes vidéos.\nDemande-moi ce que tu veux, ou touche une suggestion ci-dessous." });
    showScan(d.status);
    scroll();
  };

  const send = async (text) => {
    text = (text || "").trim();
    if (!text) return;
    input.value = "";
    input.style.height = "";
    log.insertAdjacentHTML("beforeend", msgHtml({ role: "user", text }) + `<div class="msg bot" id="typing"><div class="avatar">${icon("bot", "sm")}</div><div class="bubble typing"><span></span><span></span><span></span></div></div>`);
    scroll();
    $("#send").disabled = true;
    try {
      const m = await api("/api/bot/chat", { method: "POST", body: { message: text } });
      $("#typing")?.remove();
      log.insertAdjacentHTML("beforeend", msgHtml(m));
      scroll();
      showScan((await api("/api/bot")).status);
    } catch (e) {
      $("#typing")?.remove();
      toast(e.message, "err");
    } finally { $("#send").disabled = false; input.focus(); }
  };

  $("#form").onsubmit = (e) => { e.preventDefault(); send(input.value); };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); } });
  input.addEventListener("input", () => { input.style.height = ""; input.style.height = Math.min(input.scrollHeight, 140) + "px"; });
  $$("[data-s]").forEach((b) => (b.onclick = () => send(b.dataset.s)));
  $("#clear").onclick = async () => {
    if (!(await confirmBox("Effacer la conversation ?", "Effacer"))) return;
    await api("/api/bot", { method: "DELETE" });
    load();
  };
  load();
}
