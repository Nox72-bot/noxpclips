import { $, $$, api, esc, icon, toast, uploadWithProgress } from "./core.js";
import { stylePreview } from "./create.js";

const FONTS = ["", "Poppins Black", "Poppins ExtraBold", "Poppins Bold", "Anton", "Bebas Neue", "Luckiest Guy", "Bangers", "Archivo Black"];

export async function renderBrand(view) {
  const [settings, styles] = await Promise.all([api("/api/settings"), api("/api/styles")]);
  const b = { ...settings.brand };

  const preview = () => {
    const s = { ...(styles.captions.find((x) => x.id === b.caption_style) || styles.captions[0]) };
    if (b.highlight_color) s.highlight = b.highlight_color;
    if (b.text_color) s.color = b.text_color;
    if (b.font) s.font = b.font;
    const top = { top: "22%", middle: "62%", bottom: "78%" }[b.caption_position || "middle"];
    const lp = b.logo_position || "top-right";
    const logo = b.logo ? `<img src="/media/brand/${esc(b.logo)}" style="position:absolute;${lp.includes("top") ? "top:18px" : "bottom:60px"};${lp.includes("left") ? "left:12px" : "right:12px"};width:${Math.round(218 * b.logo_size)}px;opacity:${b.logo_opacity}">` : "";
    $("#phone").innerHTML = `${logo}<div style="position:absolute;left:8px;right:8px;top:${top};transform:translateY(-50%);text-align:center;zoom:.62">${stylePreview(s, "Le meilleur moment")}</div>`;
  };

  view.innerHTML = `<div class="page-head"><div><h1>Kit de marque</h1><p class="muted" style="margin:0">Ton style appliqué automatiquement à tous tes clips.</p></div>
    <button class="btn primary" id="save">${icon("check", "sm")} Enregistrer</button></div>
    <div style="display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:24px" class="brand-grid">
      <div class="stack" style="gap:18px">
        <div class="card stack">
          <h2>Identité</h2>
          <label class="field">Nom du kit<input class="input" id="name" value="${esc(b.name || "")}"></label>
          <div class="row wrap" style="gap:16px">
            <div style="width:110px;height:110px;border-radius:16px;background:var(--bg-2);border:1px dashed var(--border-2);display:grid;place-items:center;overflow:hidden" id="logobox">
              ${b.logo ? `<img src="/media/brand/${esc(b.logo)}" style="max-width:90%;max-height:90%">` : `<span class="faint small">Aucun logo</span>`}</div>
            <div class="stack" style="gap:8px">
              <label class="btn">${icon("upload", "sm")} Importer un logo (PNG transparent)<input type="file" id="logo" accept="image/png,image/jpeg,image/webp" hidden></label>
              ${b.logo ? `<button class="btn ghost danger" id="dellogo">${icon("trash", "sm")} Retirer le logo</button>` : ""}
            </div>
          </div>
          <div class="grid2">
            <label class="field">Position du logo<select class="input" id="logo_position">${[["top-left", "En haut à gauche"], ["top-right", "En haut à droite"], ["bottom-left", "En bas à gauche"], ["bottom-right", "En bas à droite"]].map(([v, l]) => `<option value="${v}" ${b.logo_position === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
            <label class="field">Taille du logo : <span id="lsv">${Math.round(b.logo_size * 100)}%</span><input type="range" id="logo_size" min="0.08" max="0.4" step="0.01" value="${b.logo_size}"></label>
            <label class="field">Opacité : <span id="lov">${Math.round(b.logo_opacity * 100)}%</span><input type="range" id="logo_opacity" min="0.2" max="1" step="0.05" value="${b.logo_opacity}"></label>
          </div>
        </div>
        <div class="card stack">
          <h2>Sous-titres par défaut</h2>
          <div class="style-scroller" id="styles">${styles.captions.map((s) => `<div class="style-card ${s.id === b.caption_style ? "on" : ""}" data-style="${s.id}"><span class="tag">${esc(s.label)}</span>${stylePreview(s)}</div>`).join("")}</div>
          <div class="grid2">
            <label class="field">Couleur du mot surligné<div class="row"><input type="color" id="highlight_color" value="${b.highlight_color || "#7cff4f"}" style="width:54px;height:44px;border:none;background:none"><button class="btn sm" id="resethl">Couleur du style</button></div></label>
            <label class="field">Couleur du texte<div class="row"><input type="color" id="text_color" value="${b.text_color || "#ffffff"}" style="width:54px;height:44px;border:none;background:none"><button class="btn sm" id="resettc">Par défaut</button></div></label>
            <label class="field">Police<select class="input" id="font">${FONTS.map((f) => `<option value="${f}" ${b.font === f ? "selected" : ""}>${f || "Police du style"}</option>`).join("")}</select></label>
            <label class="field">Position<select class="input" id="caption_position"><option value="top">En haut</option><option value="middle">Au milieu</option><option value="bottom">En bas</option></select></label>
          </div>
        </div>
      </div>
      <div><div class="card" style="position:sticky;top:20px"><h3>Aperçu</h3><div class="phone" id="phone"></div></div></div>
    </div>
    <style>@media (max-width:900px){.brand-grid{grid-template-columns:1fr!important}}</style>`;

  $("#caption_position").value = b.caption_position || "middle";
  let hlSet = !!b.highlight_color, tcSet = !!b.text_color;
  $$("#styles .style-card").forEach((c) => (c.onclick = () => {
    b.caption_style = c.dataset.style;
    $$("#styles .style-card").forEach((x) => x.classList.toggle("on", x === c));
    preview();
  }));
  $("#highlight_color").oninput = (e) => { hlSet = true; b.highlight_color = e.target.value; preview(); };
  $("#text_color").oninput = (e) => { tcSet = true; b.text_color = e.target.value; preview(); };
  $("#resethl").onclick = () => { hlSet = false; b.highlight_color = ""; preview(); };
  $("#resettc").onclick = () => { tcSet = false; b.text_color = ""; preview(); };
  $("#font").onchange = (e) => { b.font = e.target.value; preview(); };
  $("#caption_position").onchange = (e) => { b.caption_position = e.target.value; preview(); };
  $("#logo_position").onchange = (e) => { b.logo_position = e.target.value; preview(); };
  $("#logo_size").oninput = (e) => { b.logo_size = +e.target.value; $("#lsv").textContent = Math.round(b.logo_size * 100) + "%"; preview(); };
  $("#logo_opacity").oninput = (e) => { b.logo_opacity = +e.target.value; $("#lov").textContent = Math.round(b.logo_opacity * 100) + "%"; preview(); };
  $("#logo").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const r = await uploadWithProgress("/api/brand/logo", f);
      b.logo = r.logo;
      toast("Logo importé ✔", "ok");
      renderBrand(view);
    } catch (err) { toast(err.message, "err"); }
  };
  $("#dellogo") && ($("#dellogo").onclick = async () => { await api("/api/brand/logo", { method: "DELETE" }); renderBrand(view); });
  $("#save").onclick = async () => {
    b.name = $("#name").value;
    if (!hlSet) b.highlight_color = "";
    if (!tcSet) b.text_color = "";
    await api("/api/settings", { method: "PUT", body: { brand: b } });
    toast("Kit de marque enregistré ✔", "ok");
  };
  preview();
}
