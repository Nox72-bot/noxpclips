import { $, $$, PLATFORMS, STATUS_LABELS, api, esc, icon, modal, onLeave, toast } from "./core.js";
import { openPost, openSchedule } from "./schedule.js";

const DOW = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

export async function renderCalendar(view) {
  const now = new Date();
  let year = now.getFullYear(), month = now.getMonth();
  let mode = window.innerWidth < 760 ? "list" : "month";
  let posts = [];
  let timer;
  onLeave(() => clearTimeout(timer));

  const range = () => {
    const first = new Date(year, month, 1);
    const start = new Date(first);
    start.setDate(1 - ((first.getDay() + 6) % 7));
    const end = new Date(start);
    end.setDate(start.getDate() + 42);
    return [start, end];
  };

  const load = async () => {
    const [s, e] = mode === "list" ? [new Date(Date.now() - 2 * 86400000), new Date(Date.now() + 120 * 86400000)] : range();
    posts = await api(`/api/posts?start=${s.getTime() / 1000}&end=${e.getTime() / 1000}`);
    draw();
    clearTimeout(timer);
    if (posts.some((p) => p.status === "publishing")) timer = setTimeout(load, 4000);
  };

  const chip = (p) => `<div class="cal-post ${p.platform} ${p.status}" draggable="true" data-post="${p.id}" title="${esc((p.clip || {}).title || "")}">
    ${p.clip && p.clip.thumb_url ? `<img src="${esc(p.clip.thumb_url)}" alt="">` : ""}<span>${new Date(p.scheduled_at * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })} ${esc((p.clip || {}).title || "")}</span></div>`;

  const draw = () => {
    const due = posts.filter((p) => p.status === "due").length;
    const failed = posts.filter((p) => p.status === "failed").length;
    const title = new Date(year, month, 1).toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
    let body = "";
    if (mode === "month") {
      const [start] = range();
      const cells = [];
      for (let i = 0; i < 42; i++) {
        const d = new Date(start);
        d.setDate(start.getDate() + i);
        const key = d.toDateString();
        const dayPosts = posts.filter((p) => new Date(p.scheduled_at * 1000).toDateString() === key);
        const max = window.innerWidth < 760 ? 3 : 4;
        cells.push(`<div class="cal-day ${d.getMonth() !== month ? "other" : ""} ${key === new Date().toDateString() ? "today" : ""}" data-day="${d.getFullYear()}-${d.getMonth()}-${d.getDate()}">
          <div class="num">${d.getDate()}</div>${dayPosts.slice(0, max).map(chip).join("")}${dayPosts.length > max ? `<div class="cal-more">+${dayPosts.length - max}</div>` : ""}</div>`);
      }
      body = `<div class="cal-grid">${DOW.map((d) => `<div class="cal-dow">${d}</div>`).join("")}${cells.join("")}</div>`;
    } else {
      const groups = {};
      posts.slice().sort((a, b) => a.scheduled_at - b.scheduled_at).forEach((p) => {
        const k = new Date(p.scheduled_at * 1000).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
        (groups[k] = groups[k] || []).push(p);
      });
      body = Object.keys(groups).length ? Object.entries(groups).map(([k, ps]) => `<div class="agenda-date">${k}</div><div class="stack" style="gap:8px">${ps.map((p) => `
        <div class="agenda-item" data-post="${p.id}">${p.clip && p.clip.thumb_url ? `<img src="${esc(p.clip.thumb_url)}" alt="">` : "<div style='width:46px'></div>"}
          <div class="grow"><div style="font-weight:650">${esc((p.clip || {}).title || "Clip")}</div>
          <div class="row small muted" style="margin-top:4px"><span class="plat-dot ${p.platform}"></span>${esc(PLATFORMS[p.platform]?.short || p.platform)} · ${new Date(p.scheduled_at * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</div></div>
          <span class="status ${p.status}">${STATUS_LABELS[p.status] || p.status}</span></div>`).join("")}</div>`).join("")
        : `<div class="empty">${icon("calendar")}<p>Rien de prévu pour l'instant.<br>Ouvre un projet et clique sur « Planifier ».</p></div>`;
    }
    view.innerHTML = `
      <div class="page-head"><div><h1>Calendrier</h1><p class="muted" style="margin:0">Programme tes clips sur TikTok, Instagram et YouTube, sur plusieurs jours.</p></div>
        <div class="row"><button class="btn" id="series">${icon("layers", "sm")} Planifier une série</button><button class="btn primary" id="add">${icon("plus", "sm")} Planifier</button></div></div>
      ${due ? `<div class="card flat small" style="border-color:#ffb02066;margin-bottom:12px;color:var(--warn)">${icon("info", "sm")} ${due} publication(s) manuelle(s) à faire maintenant — touche-la pour partager le clip.</div>` : ""}
      ${failed ? `<div class="card flat small" style="border-color:#ff5a5f66;margin-bottom:12px;color:var(--danger)">${failed} publication(s) en échec — touche-la pour voir l'erreur et réessayer.</div>` : ""}
      <div class="cal-head">
        ${mode === "month" ? `<button class="icon-btn" id="prev">${icon("left")}</button><h2 style="margin:0;text-transform:capitalize;min-width:170px;text-align:center">${title}</h2><button class="icon-btn" id="next">${icon("right")}</button><button class="btn sm" id="today">Aujourd'hui</button>` : `<h2 style="margin:0">À venir</h2>`}
        <span class="grow"></span>
        <div class="row" style="gap:4px"><button class="chip sm ${mode === "month" ? "on" : ""}" data-m="month">${icon("calendar", "sm")} Mois</button><button class="chip sm ${mode === "list" ? "on" : ""}" data-m="list">${icon("list", "sm")} Liste</button></div>
      </div>
      <div class="row small muted wrap" style="margin-top:10px;gap:14px"><span class="row" style="gap:6px"><span class="plat-dot tiktok"></span>TikTok</span><span class="row" style="gap:6px"><span class="plat-dot instagram"></span>Instagram</span><span class="row" style="gap:6px"><span class="plat-dot youtube"></span>YouTube</span><span class="faint">Glisse un post sur un autre jour pour le déplacer.</span></div>
      ${body}`;

    $$("[data-m]").forEach((b) => (b.onclick = () => { mode = b.dataset.m; load(); }));
    $("#prev") && ($("#prev").onclick = () => { month--; if (month < 0) { month = 11; year--; } load(); });
    $("#next") && ($("#next").onclick = () => { month++; if (month > 11) { month = 0; year++; } load(); });
    $("#today") && ($("#today").onclick = () => { year = now.getFullYear(); month = now.getMonth(); load(); });
    $("#add").onclick = () => pickClips(false, load);
    $("#series").onclick = () => pickClips(true, load);
    $$("[data-post]").forEach((el) => el.addEventListener("click", (e) => {
      e.stopPropagation();
      openPost(posts.find((p) => p.id === el.dataset.post), load);
    }));
    // glisser-déposer
    $$(".cal-post").forEach((el) => el.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", el.dataset.post)));
    $$(".cal-day").forEach((day) => {
      day.addEventListener("dragover", (e) => { e.preventDefault(); day.classList.add("drop"); });
      day.addEventListener("dragleave", () => day.classList.remove("drop"));
      day.addEventListener("drop", async (e) => {
        e.preventDefault();
        day.classList.remove("drop");
        const p = posts.find((x) => x.id === e.dataTransfer.getData("text/plain"));
        if (!p) return;
        const [y, mo, d] = day.dataset.day.split("-").map(Number);
        const old = new Date(p.scheduled_at * 1000);
        const nd = new Date(y, mo, d, old.getHours(), old.getMinutes());
        try {
          await api(`/api/posts/${p.id}`, { method: "PATCH", body: { scheduled_at: nd.getTime() / 1000 } });
          toast("Publication déplacée ✔", "ok");
        } catch (err) { toast(err.message, "err"); }
        load();
      });
      day.addEventListener("click", () => mode === "month" && pickClips(false, load));
    });
  };
  view.innerHTML = `<div class="empty">${icon("refresh", "spin")}</div>`;
  await load();
}

async function pickClips(multi, onDone) {
  const projects = (await api("/api/projects")).filter((p) => p.status === "done" && p.clip_count);
  if (!projects.length) return toast("Crée d'abord des clips depuis l'accueil", "err");
  const m = modal(`<div class="modal-head"><h2>${multi ? "Choisis les clips de la série" : "Choisis un clip"}</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <select class="input" id="proj">${projects.map((p) => `<option value="${p.id}">${esc(p.title)} (${p.clip_count} clips)</option>`).join("")}</select>
    <div id="list" class="stack" style="gap:6px;margin-top:12px;max-height:50dvh;overflow:auto"></div>
    <div class="modal-foot"><button class="btn" data-close>Annuler</button>${multi ? `<button class="btn primary" id="next">Continuer</button>` : ""}</div>`, { wide: true });
  let clips = [];
  const show = async () => {
    const p = await api(`/api/projects/${$("#proj", m.el).value}`);
    clips = p.clips.filter((c) => c.status === "done");
    $("#list", m.el).innerHTML = clips.map((c) => `<label class="row" data-c="${c.id}" style="padding:8px;border-radius:12px;background:var(--bg-2);cursor:pointer">
      ${multi ? `<input type="checkbox" checked style="width:20px;height:20px">` : ""}${c.thumb_url ? `<img src="${esc(c.thumb_url)}" style="width:34px;height:60px;object-fit:cover;border-radius:7px">` : ""}
      <span class="grow"><b>${c.score}</b> · ${esc(c.title)}</span><span class="pill cat-${c.category}">${esc(c.category_label)}</span></label>`).join("");
    if (!multi) $$("[data-c]", m.el).forEach((el) => (el.onclick = () => { m.close(); openSchedule([clips.find((c) => c.id === el.dataset.c)], onDone); }));
  };
  $("#proj", m.el).onchange = show;
  await show();
  if (multi) $("#next", m.el).onclick = () => {
    const chosen = $$("[data-c]", m.el).filter((el) => el.querySelector("input").checked).map((el) => clips.find((c) => c.id === el.dataset.c));
    if (chosen.length < 2) return toast("Choisis au moins 2 clips", "err");
    m.close();
    openSchedule(chosen, onDone);
  };
}
