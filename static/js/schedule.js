import { $, $$, PLATFORMS, STATUS_LABELS, api, copyText, esc, fmtDate, fromLocalInput, icon, modal, toLocalInput, toast, confirmBox } from "./core.js";

export const BEST_TIMES = { tiktok: ["12:00", "18:00", "21:00"], instagram: ["11:00", "19:00"], youtube: ["17:00", "20:00"] };

export function captionFor(clip) {
  if (clip.captionOverride) return clip.captionOverride;
  return [clip.title, clip.description, (clip.hashtags || []).join(" ")].filter(Boolean).join("\n\n");
}

async function targetsHtml() {
  const accounts = await api("/api/accounts");
  const connected = new Set(accounts.map((a) => a.platform));
  const items = accounts.map((a) => ({ platform: a.platform, account_id: a.id, name: a.name, sub: PLATFORMS[a.platform].name + (a.platform === "tiktok" && a.mode !== "direct" ? " · brouillon" : " · auto") }));
  for (const p of ["tiktok", "instagram", "youtube"]) {
    if (!connected.has(p)) items.push({ platform: p, account_id: "", name: PLATFORMS[p].short, sub: "Manuel : rappel + partage" });
  }
  return { accounts, html: items.map((t, i) => `<div class="target" data-i="${i}" data-p="${t.platform}" data-a="${t.account_id}">
      <span style="color:var(--${t.platform === "youtube" ? "yt" : t.platform === "tiktok" ? "tt" : "ig"})">${icon(t.platform)}</span>
      <div class="grow"><div style="font-weight:600">${esc(t.name)}</div><div class="sub">${esc(t.sub)}</div></div>
      <span class="check" style="display:none">${icon("check", "sm")}</span></div>`).join("") };
}

function bindTargets(root) {
  $$(".target", root).forEach((t) => (t.onclick = () => {
    t.classList.toggle("on");
    t.querySelector(".check").style.display = t.classList.contains("on") ? "" : "none";
  }));
  return () => $$(".target.on", root).map((t) => ({ platform: t.dataset.p, account_id: t.dataset.a || null }));
}

function at(dayOffset, hhmm) {
  const d = new Date();
  d.setDate(d.getDate() + dayOffset);
  const [hh, mm] = hhmm.split(":").map(Number);
  d.setHours(hh, mm, 0, 0);
  return Math.round(d.getTime() / 1000);
}

export async function openSchedule(clips, onDone) {
  if (clips.length > 1) return openSeries(clips, onDone);
  const clip = clips[0];
  const { html } = await targetsHtml();
  const tonight = at(new Date().getHours() >= 18 ? 1 : 0, "18:00");
  const m = modal(`
    <div class="modal-head"><h2>Planifier la publication</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <div class="row" style="margin-bottom:14px">${clip.thumb_url ? `<img src="${esc(clip.thumb_url)}" style="width:54px;height:96px;object-fit:cover;border-radius:10px">` : ""}
      <div class="grow"><b>${esc(clip.title)}</b><div class="small muted">Score ${clip.score} · ${esc(clip.category_label || "")}</div></div></div>
    <h3>Où publier ?</h3><div class="targets" id="tg">${html}</div>
    <p class="small faint">Réseau non connecté = tu reçois un rappel dans le calendrier et tu partages le clip en 1 tap.</p>
    <h3 style="margin-top:16px">Quand ?</h3>
    <div class="time-chips" style="margin-bottom:10px">
      <button class="chip sm" data-t="now">Maintenant</button>
      <button class="chip sm" data-t="${tonight}">Ce soir 18h</button>
      <button class="chip sm" data-t="${at(1, "12:00")}">Demain 12h</button>
      <button class="chip sm" data-t="${at(1, "19:00")}">Demain 19h</button>
      <button class="chip sm" data-t="${at(2, "18:00")}">Après-demain 18h</button>
    </div>
    <input type="datetime-local" class="input" id="when" value="${toLocalInput(tonight)}">
    <div class="grid2" style="margin-top:14px">
      <label class="field">Confidentialité<select class="input" id="privacy"><option value="public">Public</option><option value="unlisted">Non répertorié / amis</option><option value="private">Privé</option></select></label>
    </div>
    <label class="field" style="margin-top:12px">Légende<textarea class="input" id="caption" rows="5">${esc(captionFor(clip))}</textarea></label>
    <div class="modal-foot"><button class="btn" data-close>Annuler</button><button class="btn primary" id="ok">${icon("calendar", "sm")} Planifier</button></div>`);
  const getTargets = bindTargets(m.el);
  let now = false;
  $$("[data-t]", m.el).forEach((b) => (b.onclick = () => {
    $$("[data-t]", m.el).forEach((x) => x.classList.toggle("on", x === b));
    now = b.dataset.t === "now";
    if (!now) $("#when", m.el).value = toLocalInput(+b.dataset.t);
  }));
  $("#when", m.el).oninput = () => { now = false; $$("[data-t]", m.el).forEach((x) => x.classList.remove("on")); };
  $("#ok", m.el).onclick = async () => {
    const targets = getTargets();
    if (!targets.length) return toast("Choisis au moins un réseau", "err");
    const btn = $("#ok", m.el);
    btn.disabled = true;
    btn.textContent = now ? "Publication…" : "Planification…";
    try {
      const res = await api("/api/posts", { method: "POST", body: {
        clip_id: clip.id, targets, scheduled_at: now ? null : fromLocalInput($("#when", m.el).value),
        caption: $("#caption", m.el).value, privacy: $("#privacy", m.el).value } });
      const failed = res.filter((p) => p.status === "failed");
      if (failed.length) toast(`Échec : ${failed[0].error}`, "err");
      else toast(now ? "C'est parti ! 🚀" : `${res.length} publication(s) planifiée(s) ✔`, "ok");
      m.close();
      const manualNow = res.find((p) => p.status === "due");
      if (manualNow) openPost(manualNow, onDone);
      onDone && onDone();
    } catch (e) {
      toast(e.message, "err");
      btn.disabled = false;
      btn.textContent = "Planifier";
    }
  };
}

export async function openSeries(clips, onDone) {
  const { html } = await targetsHtml();
  const sorted = [...clips].sort((a, b) => b.score - a.score);
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const m = modal(`
    <div class="modal-head"><h2>Planifier une série</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <p class="muted" style="margin-top:0">Répartis tes meilleurs clips sur plusieurs jours, aux heures où ton audience est la plus active.</p>
    <h3>Clips (du meilleur score au moins bon)</h3>
    <div class="stack" style="gap:6px;max-height:230px;overflow:auto" id="cl">${sorted.map((c) => `<label class="row" style="padding:6px;border-radius:10px;background:var(--bg-2)">
      <input type="checkbox" checked data-c="${c.id}" style="width:20px;height:20px">${c.thumb_url ? `<img src="${esc(c.thumb_url)}" style="width:30px;height:52px;object-fit:cover;border-radius:6px">` : ""}
      <span class="grow small"><b>${c.score}</b> · ${esc(c.title)}</span><span class="pill cat-${c.category}">${esc(c.category_label || "")}</span></label>`).join("")}</div>
    <h3 style="margin-top:16px">Où publier ?</h3><div class="targets" id="tg">${html}</div>
    <div class="grid2" style="margin-top:16px">
      <label class="field">Premier jour<input type="date" class="input" id="d0" value="${tomorrow}"></label>
      <label class="field">Clips par jour<select class="input" id="perday">${[1, 2, 3, 4, 5].map((n) => `<option ${n === 2 ? "selected" : ""}>${n}</option>`).join("")}</select></label>
    </div>
    <label class="field" style="margin-top:12px">Horaires de publication<div class="row wrap" id="times"></div></label>
    <div class="row small faint" style="margin-top:6px">${icon("info", "sm")} Meilleurs créneaux : TikTok 12h/18h/21h · Instagram 11h/19h · YouTube 17h/20h</div>
    <label class="field" style="margin-top:12px">Confidentialité<select class="input" id="privacy"><option value="public">Public</option><option value="unlisted">Non répertorié / amis</option><option value="private">Privé</option></select></label>
    <h3 style="margin-top:16px">Aperçu</h3><div id="preview" class="stack small" style="gap:4px"></div>
    <div class="modal-foot"><button class="btn" data-close>Annuler</button><button class="btn primary" id="ok">${icon("calendar", "sm")} Tout planifier</button></div>`, { wide: true });
  const getTargets = bindTargets(m.el);
  const times = ["12:00", "18:00", "21:00", "15:00", "09:00"];
  const renderTimes = () => {
    const n = +$("#perday", m.el).value;
    const cur = $$("#times input", m.el).map((i) => i.value);
    $("#times", m.el).innerHTML = [...Array(n)].map((_, i) => `<input type="time" class="input" style="width:120px" value="${cur[i] || times[i]}">`).join("");
    $$("#times input", m.el).forEach((i) => (i.onchange = preview));
    preview();
  };
  const slots = () => {
    const chosen = sorted.filter((c) => $(`[data-c="${c.id}"]`, m.el).checked);
    const ts = $$("#times input", m.el).map((i) => i.value).sort();
    const base = new Date($("#d0", m.el).value + "T00:00");
    return chosen.map((c, i) => {
      const d = new Date(base);
      d.setDate(d.getDate() + Math.floor(i / ts.length));
      const [hh, mm] = ts[i % ts.length].split(":").map(Number);
      d.setHours(hh, mm, 0, 0);
      return { clip: c, ts: Math.round(d.getTime() / 1000) };
    });
  };
  const preview = () => {
    $("#preview", m.el).innerHTML = slots().map((s) => `<div class="row"><span class="faint" style="width:150px;text-transform:capitalize">${fmtDate(s.ts, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span><span class="grow">${esc(s.clip.title)}</span></div>`).join("") || '<span class="faint">Aucun clip sélectionné</span>';
  };
  $("#perday", m.el).onchange = renderTimes;
  $("#d0", m.el).onchange = preview;
  $$("[data-c]", m.el).forEach((c) => (c.onchange = preview));
  renderTimes();
  $("#ok", m.el).onclick = async () => {
    const targets = getTargets();
    if (!targets.length) return toast("Choisis au moins un réseau", "err");
    const items = slots().map((s) => ({ clip_id: s.clip.id, scheduled_at: s.ts, caption: captionFor(s.clip) }));
    if (!items.length) return toast("Sélectionne au moins un clip", "err");
    try {
      const r = await api("/api/posts/bulk", { method: "POST", body: { items, targets, privacy: $("#privacy", m.el).value } });
      toast(`${r.count} publications planifiées ✔`, "ok");
      m.close();
      onDone && onDone();
    } catch (e) { toast(e.message, "err"); }
  };
}

// ---------- Partage natif (iPhone / iPad : ouvre directement TikTok, Instagram…) ----------
export async function shareClip(clip) {
  const m = modal(`<div class="modal-head"><h2>Partager le clip</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <p class="muted" id="st">Préparation de la vidéo…</p>
    <div class="bar"><div id="pb" style="width:5%"></div></div>
    <div class="modal-foot">
      <button class="btn" id="cap">${icon("copy", "sm")} Copier la légende</button>
      <a class="btn" href="/api/clips/${clip.id}/download" download>${icon("download", "sm")} Télécharger</a>
      <button class="btn primary" id="go" disabled>${icon("share", "sm")} Partager</button></div>`);
  $("#cap", m.el).onclick = () => copyText(captionFor(clip));
  let file;
  try {
    const r = await fetch(clip.video_url.split("?")[0] + "?v=s");
    const total = +r.headers.get("content-length") || 0;
    const reader = r.body.getReader();
    const chunks = [];
    let got = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      got += value.length;
      if (total) $("#pb", m.el).style.width = (got / total) * 100 + "%";
    }
    file = new File(chunks, `${(clip.title || "clip").replace(/[^\w\- ]/g, "").slice(0, 40) || "clip"}.mp4`, { type: "video/mp4" });
  } catch {
    $("#st", m.el).textContent = "Impossible de préparer la vidéo. Utilise « Télécharger ».";
    return;
  }
  $("#pb", m.el).style.width = "100%";
  const can = navigator.canShare && navigator.canShare({ files: [file] });
  $("#st", m.el).innerHTML = can
    ? "Prêt ! Appuie sur « Partager » puis choisis TikTok, Instagram, YouTube… <br><span class='faint small'>Astuce : copie d'abord la légende pour la coller dans l'appli.</span>"
    : "Le partage direct n'est pas disponible ici (il faut Safari en HTTPS). Télécharge le clip puis publie-le depuis l'appli.";
  const go = $("#go", m.el);
  go.disabled = !can;
  go.onclick = async () => {
    try {
      await navigator.clipboard?.writeText(captionFor(clip)).catch(() => {});
      await navigator.share({ files: [file], title: clip.title, text: captionFor(clip) });
      m.close();
    } catch (e) { if (e.name !== "AbortError") toast(e.message, "err"); }
  };
}

// ---------- Détail d'une publication ----------
export function openPost(post, onChange) {
  const c = post.clip || {};
  const editable = ["scheduled", "reminder", "due", "failed"].includes(post.status);
  const url = post.result && post.result.url;
  const m = modal(`
    <div class="modal-head"><h2 class="row">${icon(post.platform)} ${esc(PLATFORMS[post.platform]?.name || post.platform)}</h2><button class="icon-btn" data-close>${icon("x")}</button></div>
    <div class="edit-layout" style="grid-template-columns:200px 1fr">
      ${c.video_url ? `<video src="${esc(c.video_url)}" poster="${esc(c.thumb_url || "")}" controls playsinline preload="none"></video>` : "<div></div>"}
      <div class="stack">
        <div><b>${esc(c.title || "Clip")}</b><div class="row small muted" style="margin-top:4px"><span class="status ${post.status}">${STATUS_LABELS[post.status] || post.status}</span>
          ${post.account_name ? esc(post.account_name) : "Publication manuelle"}</div></div>
        ${post.error ? `<div class="small" style="color:var(--danger)">${esc(post.error).replace(/\(capture : ([\w.-]+\.png)\)/, '(<a href="/api/browser-shots/$1" target="_blank" style="text-decoration:underline">voir la capture</a>)')}</div>` : ""}
        ${post.result && post.result.note ? `<div class="small muted">${esc(post.result.note)}</div>` : ""}
        ${url ? `<a class="btn sm" href="${esc(url)}" target="_blank" rel="noopener">${icon("link", "sm")} Voir la publication</a>` : ""}
        <label class="field">Date et heure<input type="datetime-local" class="input" id="when" value="${toLocalInput(post.scheduled_at)}" ${editable ? "" : "disabled"}></label>
        <label class="field">Légende<textarea class="input" id="caption" rows="4" ${editable ? "" : "disabled"}>${esc(post.caption || captionFor(c))}</textarea></label>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn danger" id="del">${icon("trash", "sm")} Supprimer</button>
      <span class="grow"></span>
      ${!post.account_id && post.status !== "published" ? `<button class="btn" id="share">${icon("share", "sm")} Partager</button><button class="btn" id="done">${icon("check", "sm")} Marquer publié</button>` : ""}
      ${post.account_id && editable ? `<button class="btn" id="now">${icon("send", "sm")} Publier maintenant</button>` : ""}
      ${editable ? `<button class="btn primary" id="save">Enregistrer</button>` : ""}
    </div>`, { wide: true });
  const refresh = () => onChange && onChange();
  $("#del", m.el).onclick = async () => {
    if (!(await confirmBox("Supprimer cette publication ?", "Supprimer"))) return;
    await api(`/api/posts/${post.id}`, { method: "DELETE" });
    m.close(); refresh();
  };
  $("#save", m.el) && ($("#save", m.el).onclick = async () => {
    await api(`/api/posts/${post.id}`, { method: "PATCH", body: { scheduled_at: fromLocalInput($("#when", m.el).value), caption: $("#caption", m.el).value } });
    toast("Enregistré ✔", "ok"); m.close(); refresh();
  });
  $("#now", m.el) && ($("#now", m.el).onclick = async (e) => {
    e.target.disabled = true; e.target.textContent = "Envoi…";
    await api(`/api/posts/${post.id}`, { method: "PATCH", body: { caption: $("#caption", m.el).value } });
    const r = await api(`/api/posts/${post.id}/publish`, { method: "POST" });
    toast(r.status === "failed" ? `Échec : ${r.error}` : "Publié 🚀", r.status === "failed" ? "err" : "ok");
    m.close(); refresh();
  });
  $("#share", m.el) && ($("#share", m.el).onclick = () => shareClip({ ...c, captionOverride: $("#caption", m.el).value }));
  $("#done", m.el) && ($("#done", m.el).onclick = async () => {
    await api(`/api/posts/${post.id}`, { method: "PATCH", body: { status: "published" } });
    toast("Marqué comme publié ✔", "ok"); m.close(); refresh();
  });
}
