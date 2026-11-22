import { $, api, esc, h, icon, route, router, toast } from "./core.js";
import { renderHome, renderProjects } from "./home.js";
import { renderNew } from "./create.js";
import { renderProject } from "./project.js";
import { renderCalendar } from "./calendar.js";
import { renderAccounts } from "./accounts.js";
import { renderBrand } from "./brand.js";
import { renderSettings, renderAnalytics } from "./settings.js";

const NAV = [
  { label: "Créer" },
  { path: "/", icon: "home", text: "Accueil" },
  { path: "/projects", icon: "folder", text: "Mes projets" },
  { path: "/brand", icon: "palette", text: "Kit de marque" },
  { label: "Publier" },
  { path: "/calendar", icon: "calendar", text: "Calendrier" },
  { path: "/analytics", icon: "chart", text: "Analytics" },
  { path: "/accounts", icon: "link", text: "Comptes sociaux" },
  { spacer: true },
  { path: "/settings", icon: "settings", text: "Réglages" },
];
const TABS = [
  { path: "/", icon: "home", text: "Accueil" },
  { path: "/projects", icon: "folder", text: "Projets" },
  { path: "/calendar", icon: "calendar", text: "Calendrier" },
  { path: "/accounts", icon: "link", text: "Comptes" },
  { path: "/settings", icon: "settings", text: "Réglages" },
];

const brandHtml = `<a class="brand" href="#/"><div class="brand-mark">N</div><div class="brand-name">NOXP<span>clips</span></div></a>`;

function shell() {
  $("#sidebar").innerHTML = brandHtml + NAV.map((n) => {
    if (n.label) return `<div class="nav-label">${n.label}</div>`;
    if (n.spacer) return `<div class="spacer"></div>`;
    return `<a class="nav-item" data-path="${n.path}" href="#${n.path}">${icon(n.icon)}<span>${n.text}</span></a>`;
  }).join("") + `<div class="free-badge"><b>∞ Illimité & gratuit</b>Aucun crédit, aucun token : tout tourne sur ton propre serveur.</div>`;
  $("#topbar").innerHTML = brandHtml + `<a class="icon-btn" href="#/analytics" aria-label="Analytics">${icon("chart")}</a>`;
  $("#tabbar").innerHTML = TABS.map((t) => `<a data-path="${t.path}" href="#${t.path}">${icon(t.icon)}<span>${t.text}</span></a>`).join("");
}

function highlight(path) {
  const base = "/" + (path.split("/")[1] || "");
  const map = { "/new": "/", "/project": "/projects" };
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
