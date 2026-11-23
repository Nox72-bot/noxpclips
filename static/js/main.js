import { $, api, esc, h, icon, route, router, toast } from "./core.js";
import { renderHome, renderProjects } from "./home.js";
import { renderNew } from "./create.js";
import { renderProject } from "./project.js";
import { renderCalendar } from "./calendar.js";
import { renderAccounts } from "./accounts.js";
import { renderBrand } from "./brand.js";
import { renderSettings, renderAnalytics } from "./settings.js";
import { renderInspiration } from "./inspiration.js";
import { renderConnectors } from "./connectors.js";
import { renderBot } from "./bot.js";
import { renderAutopilot } from "./autopilot.js";

const NAV = [
  { label: "Créer" },
  { path: "/", icon: "home", text: "Accueil" },
  { path: "/projects", icon: "folder", text: "Mes projets" },
  { path: "/brand", icon: "palette", text: "Kit de marque" },
  { path: "/inspiration", icon: "sparkles", text: "Inspiration TikTok" },
  { path: "/bot", icon: "bot", text: "Bot" },
  { label: "Publier" },
  { path: "/autopilot", icon: "bolt", text: "Pilote auto" },
  { path: "/calendar", icon: "calendar", text: "Calendrier" },
  { path: "/analytics", icon: "chart", text: "Analytics" },
  { path: "/connectors", icon: "plug", text: "Connecteurs" },
  { spacer: true },
  { path: "/settings", icon: "settings", text: "Réglages" },
];
const TABS = [
  { path: "/", icon: "home", text: "Accueil" },
  { path: "/autopilot", icon: "bolt", text: "Pilote" },
  { path: "/calendar", icon: "calendar", text: "Calendrier" },
  { path: "/connectors", icon: "plug", text: "Connecteurs" },
  { path: "/bot", icon: "bot", text: "Bot" },
];

const brandHtml = `<a class="brand" href="#/"><div class="brand-mark">N</div><div class="brand-name">NOXP<span>clips</span></div></a>`;

function shell() {
  $("#sidebar").innerHTML = `<div class="side-head">${brandHtml}<button class="side-toggle" id="sidetoggle" aria-label="Replier le menu" title="Replier / déplier le menu">${icon("dleft")}</button></div>` + NAV.map((n) => {
    if (n.label) return `<div class="nav-label">${n.label}</div>`;
    if (n.spacer) return `<div class="spacer"></div>`;
    return `<a class="nav-item" data-path="${n.path}" href="#${n.path}" title="${n.text}">${icon(n.icon)}<span>${n.text}</span></a>`;
  }).join("") + `<div class="free-badge"><b>∞ Illimité & gratuit</b>Aucun crédit, aucun token : tout tourne sur ton propre serveur.</div>`;
  $("#topbar").innerHTML = brandHtml + `<div class="row" style="gap:4px"><a class="icon-btn" href="#/inspiration" aria-label="Inspiration TikTok">${icon("sparkles")}</a><a class="icon-btn" href="#/analytics" aria-label="Analytics">${icon("chart")}</a><a class="icon-btn" href="#/settings" aria-label="Réglages">${icon("settings")}</a></div>`;
  const setCollapsed = (on) => {
    document.documentElement.classList.toggle("nav-collapsed", on);
    $("#sidetoggle").setAttribute("aria-label", on ? "Déplier le menu" : "Replier le menu");
    $("#sidetoggle").innerHTML = icon(on ? "dright" : "dleft");
    try { localStorage.setItem("noxp-nav-collapsed", on ? "1" : ""); } catch { /* stockage indisponible */ }
  };
  let saved = false;
  try { saved = localStorage.getItem("noxp-nav-collapsed") === "1"; } catch { /* stockage indisponible */ }
  setCollapsed(saved);
  $("#sidetoggle").onclick = () => setCollapsed(!document.documentElement.classList.contains("nav-collapsed"));
  $("#tabbar").innerHTML = TABS.map((t) => `<a data-path="${t.path}" href="#${t.path}">${icon(t.icon)}<span>${t.text}</span></a>`).join("");
}

function highlight(path) {
  const base = "/" + (path.split("/")[1] || "");
  const map = { "/new": "/", "/project": "/projects", "/accounts": "/connectors" };
  const cur = map[base] || base;
  document.querySelectorAll("[data-path]").forEach((a) => a.classList.toggle("active", a.dataset.path === cur));
}

async function showLogin() {
  $("#view").innerHTML = "";
  const el = h(`<div class="login card"><div class="brand" style="justify-content:center">${$("#sidebar .brand")?.innerHTML || ""}</div>
    <h2>Accès protégé</h2><p class="muted small">Entre le mot de passe défini sur ton serveur (NOXP_PASSWORD).</p>
    <form class="stack"><input class="input" type="password" id="pw" placeholder="Mot de passe" autocomplete="current-password">
    <button class="btn primary block">${icon("lock")} Entrer</button></form></div>`);
  $("#view").append(el);
  el.querySelector("form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/api/login", { method: "POST", body: { password: $("#pw").value } });
      router();
    } catch (err) { toast(err.message, "err"); }
  };
}

route("/", renderHome);
route("/projects", renderProjects);
route("/new", renderNew);
route("/project/:id", renderProject);
route("/calendar", renderCalendar);
route("/accounts", renderAccounts);
route("/brand", renderBrand);
route("/settings", renderSettings);
route("/analytics", renderAnalytics);
route("/inspiration", renderInspiration);
route("/connectors", renderConnectors);
route("/bot", renderBot);
route("/autopilot", renderAutopilot);

shell();
window.addEventListener("noxp-route", (e) => highlight(e.detail));
window.addEventListener("noxp-auth", showLogin);
window.addEventListener("hashchange", router);

(async () => {
  try {
    const a = await api("/api/auth");
    if (a.required && !a.ok) return showLogin();
  } catch {}
  router();
})();

if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
