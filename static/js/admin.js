const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const FILE_ACCEPT = "image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/quicktime,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv";

function escapeHTML(value = "") {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[char]);
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3200);
}

function formatSize(bytes) {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
  return Math.max(1, Math.round(bytes / 1024)) + " KB";
}

// Every admin request carries the CSRF token. JSON bodies get a JSON header;
// FormData (file uploads) must NOT, so the browser can add its own boundary.
async function api(url, options = {}) {
  const headers = { "X-CSRF-Token": csrfToken, ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) { window.location.href = "/admin/login"; throw new Error("Please log in again."); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || "Something went wrong. Please try again.");
  return data;
}

function setStatus(el, message, kind) {
  el.textContent = message;
  el.className = "form-message" + (kind ? " " + kind : "");
}

/* ---------- Tabs ---------- */
$$(".dash-tab").forEach(tab => tab.addEventListener("click", () => {
  $$(".dash-tab").forEach(t => { t.classList.toggle("active", t === tab); t.setAttribute("aria-selected", String(t === tab)); });
  $$(".dash-panel").forEach(p => p.classList.toggle("hidden", p.id !== "tab-" + tab.dataset.tab));
}));

/* ---------- Summary ---------- */
async function loadSummary() {
  try {
    const s = await api("/api/admin/summary");
    $("#sumAnnouncements").textContent = s.announcements;
    $("#sumEvents").textContent = s.events;
    $("#sumArchived").textContent = s.archived;
    $("#sumNew").textContent = s.new_suggestions;
    $("#sumReports").textContent = s.new_reports;
    for (const [id, n] of [["#tabBadge", s.new_suggestions], ["#reportBadge", s.new_reports]]) {
      $(id).textContent = n;
      $(id).classList.toggle("hidden", n === 0);
    }
  } catch (e) { /* the list areas show their own errors */ }
}

/* ---------- Choosing files in a form (with "Add more") ---------- */
// prefix "a" = announcement form, "e" = event form, "g" = guide form
function makePicker(prefix) {
  const input = $(`#${prefix}Files`), list = $(`#${prefix}Picked`);
  let chosen = [];
  function draw() {
    list.innerHTML = chosen.map((f, i) => `
      <div class="picked"><span>${escapeHTML(f.name)} <small>${formatSize(f.size)}</small></span>
      <button type="button" data-remove-picked="${i}" aria-label="Remove ${escapeHTML(f.name)}">×</button></div>`).join("");
  }
  $(`#${prefix}AddMore`).addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    chosen.push(...input.files);
    input.value = "";               // lets the same file be chosen again
    draw();
  });
  list.addEventListener("click", event => {
    const b = event.target.closest("[data-remove-picked]");
    if (b) { chosen.splice(Number(b.dataset.removePicked), 1); draw(); }
  });
  return { files: () => chosen, clear: () => { chosen = []; draw(); } };
}
const pickers = { a: makePicker("a"), e: makePicker("e"), g: makePicker("g") };

function buildForm(fields, picker) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  picker.files().forEach(f => fd.append("media", f));
  return fd;
}

/* ---------- Preview (admin) ---------- */
function openPreview(url, kind, name) {
  const stage = $("#viewerStage");
  stage.innerHTML = "";
  let node;
  if (kind === "image") { node = document.createElement("img"); node.src = url; node.alt = name; }
  else if (kind === "video") { node = document.createElement("video"); node.src = url; node.controls = true; node.autoplay = true; node.setAttribute("playsinline", ""); }
  else { node = document.createElement("iframe"); node.src = url; node.title = name; }
  stage.appendChild(node);
  $("#viewerTitle").textContent = name;
  $("#viewerOpen").href = url;
  $("#viewer").classList.remove("hidden");
}
function closePreview() { $("#viewer").classList.add("hidden"); $("#viewerStage").innerHTML = ""; }
$("#viewerClose").addEventListener("click", closePreview);
$("#viewer").addEventListener("click", e => { if (e.target.id === "viewerStage") closePreview(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closePreview(); });

/* ---------- Lists of announcements / events / guides ---------- */
const LISTS = {
  announcements: {
    live: "#aList", archive: "#aArchive", empty: "No announcements yet. Post one using the form.",
    sub: i => `${i.category} · ${i.date}`, title: i => i.title
  },
  events: {
    live: "#eList", archive: "#eArchive", empty: "No events yet. Add one using the form.",
    sub: i => `${i.date} · ${i.time} · ${i.location}`, title: i => i.title
  },
  guides: {
    live: "#gList", archive: "#gArchive", empty: "No guides yet. Teach the AI using the form.",
    sub: i => `Keywords: ${(i.keywords || []).join(", ") || "none"}`, title: i => i.topic
  }
};

function thumbsHTML(kind, item) {
  return (item.media || []).map(m => {
    const body = m.kind === "image" ? `<img src="${escapeHTML(m.url)}" alt="" loading="lazy">`
      : m.kind === "video" ? `<video src="${escapeHTML(m.url)}#t=0.1" muted playsinline preload="metadata"></video><b>▶</b>`
      : `<span class="thumb-file">${escapeHTML(m.name.split(".").pop().toUpperCase())}</span>`;
    return `<div class="thumb" title="${escapeHTML(m.name)}">
      <button type="button" class="thumb-open" data-act="preview" data-url="${escapeHTML(m.url)}" data-mkind="${m.kind}" data-name="${escapeHTML(m.name)}">${body}</button>
      <button type="button" class="thumb-x" data-act="rm-media" data-kind="${kind}" data-id="${item.id}" data-mid="${m.id}" aria-label="Remove ${escapeHTML(m.name)}">×</button>
    </div>`;
  }).join("");
}

function rowHTML(kind, item, archived) {
  const cfg = LISTS[kind];
  const note = archived && item.archived_on ? ` · archived ${escapeHTML(item.archived_on)}` : "";
  const answer = kind === "guides" ? `<p class="guide-answer">${escapeHTML(item.answer)}</p>` : "";
  const data = `data-kind="${kind}" data-id="${item.id}"`;
  return `<div class="admin-list-item stack">
    <div class="row-main"><div><strong>${escapeHTML(cfg.title(item))}</strong><small>${escapeHTML(cfg.sub(item))}${note}</small></div></div>
    ${answer}
    ${item.media.length ? `<div class="thumbs">${thumbsHTML(kind, item)}</div>` : ""}
    <div class="row-actions">
      <button class="act-btn" type="button" data-act="add-media" ${data}>+ Add more photos</button>
      ${archived
        ? `<button class="act-btn" type="button" data-act="restore" ${data}>Restore</button>
           <button class="delete-btn" type="button" data-act="delete" ${data}>Delete permanently</button>`
        : `<button class="act-btn" type="button" data-act="archive" ${data}>Add to archive</button>`}
    </div>
  </div>`;
}

async function loadKind(kind) {
  const cfg = LISTS[kind];
  try {
    const items = await api(`/api/admin/${kind}`);
    const live = items.filter(i => i.status === "Published");
    const old = items.filter(i => i.status === "Archived");
    $(cfg.live).innerHTML = live.map(i => rowHTML(kind, i, false)).join("") || `<p class="empty-note">${cfg.empty}</p>`;
    $(cfg.archive).innerHTML = old.map(i => rowHTML(kind, i, true)).join("") || `<p class="empty-note">Nothing in the archive.</p>`;
  } catch (e) { $(cfg.live).textContent = e.message; }
}
const reloadAll = () => { loadKind("announcements"); loadKind("events"); loadKind("guides"); loadSummary(); };

// One click handler for every button inside the lists.
document.addEventListener("click", async event => {
  const btn = event.target.closest("[data-act]");
  if (!btn) return;
  const { act, kind, id, mid } = btn.dataset;
  try {
    if (act === "preview") { openPreview(btn.dataset.url, btn.dataset.mkind, btn.dataset.name); return; }
    if (act === "add-media") {
      const input = document.createElement("input");
      input.type = "file"; input.multiple = true; input.accept = FILE_ACCEPT;
      input.addEventListener("change", async () => {
        if (!input.files.length) return;
        const fd = new FormData();
        [...input.files].forEach(f => fd.append("media", f));
        showToast("Uploading...");
        try { await api(`/api/admin/${kind}/${id}/media`, { method: "POST", body: fd }); showToast("Added."); reloadAll(); }
        catch (e) { showToast(e.message); }
      });
      input.click();                  // must run straight from the tap so phones allow it
      return;
    }
    if (act === "rm-media") {
      if (!confirm("Remove this file from the post?")) return;
      await api(`/api/admin/${kind}/${id}/media/${mid}`, { method: "DELETE" });
      showToast("File removed.");
    } else if (act === "archive") {
      if (!confirm("Add to archive? Residents will no longer see it. It never expires and you can restore it at any time.")) return;
      showToast((await api(`/api/admin/${kind}/${id}/archive`, { method: "POST" })).message);
    } else if (act === "restore") {
      showToast((await api(`/api/admin/${kind}/${id}/restore`, { method: "POST" })).message);
    } else if (act === "delete") {
      if (!confirm("Delete permanently? This cannot be undone, and its photos and files will be erased.")) return;
      showToast((await api(`/api/admin/${kind}/${id}`, { method: "DELETE" })).message);
    }
    reloadAll();
  } catch (e) { showToast(e.message); }
});

/* ---------- Forms ---------- */
async function submitForm({ formEl, statusEl, buttonEl, url, fields, picker, okText, busyText }) {
  setStatus(statusEl, busyText);
  buttonEl.disabled = true;
  try {
    await api(url, { method: "POST", body: buildForm(fields(), picker) });
    setStatus(statusEl, okText, "success");
    formEl.reset(); picker.clear();
    showToast(okText);
    reloadAll();
  } catch (e) { setStatus(statusEl, e.message, "error"); }
  finally { buttonEl.disabled = false; }
}

$("#announcementForm").addEventListener("submit", event => {
  event.preventDefault();
  submitForm({ formEl: event.target, statusEl: $("#aStatus"), buttonEl: $("#aSubmit"), url: "/api/admin/announcements",
    picker: pickers.a, okText: "Announcement published.", busyText: "Publishing (large videos may take a moment)...",
    fields: () => ({ title: $("#aTitle").value, category: $("#aCategory").value, description: $("#aDescription").value }) });
});
$("#eventForm").addEventListener("submit", event => {
  event.preventDefault();
  submitForm({ formEl: event.target, statusEl: $("#eStatus"), buttonEl: $("#eSubmit"), url: "/api/admin/events",
    picker: pickers.e, okText: "Event added.", busyText: "Adding...",
    fields: () => ({ title: $("#eTitle").value, date: $("#eDate").value, time: $("#eTime").value,
      location: $("#eLocation").value, description: $("#eDescription").value }) });
});
$("#guideForm").addEventListener("submit", event => {
  event.preventDefault();
  submitForm({ formEl: event.target, statusEl: $("#gStatus"), buttonEl: $("#gSubmit"), url: "/api/admin/guides",
    picker: pickers.g, okText: "Guide saved. The AI will now use it.", busyText: "Saving...",
    fields: () => ({ topic: $("#gTopic").value, keywords: $("#gKeywords").value, answer: $("#gAnswer").value }) });
});

/* ---------- Try the assistant ---------- */
async function askTest() {
  const q = $("#testQuestion").value.trim();
  if (!q) return;
  const box = $("#testAnswer");
  box.textContent = "Thinking...";
  try {
    const r = await api("/api/chat", { method: "POST", body: JSON.stringify({ message: q }) });
    box.textContent = r.reply;
    const media = r.media || [];
    const video = media.find(m => m.kind === "video");
    const pics = media.filter(m => m.kind === "image");
    if (video) { const b = document.createElement("button"); b.type = "button"; b.className = "chat-demo-btn"; b.textContent = "▶ Click for video demo"; b.onclick = () => openPreview(video.url, "video", video.name); box.append(document.createElement("br"), b); }
    if (pics.length) { const b = document.createElement("button"); b.type = "button"; b.className = "chat-demo-btn alt"; b.textContent = "🖼 View guide pictures"; b.onclick = () => openPreview(pics[0].url, "image", pics[0].name); box.append(document.createElement("br"), b); }
  } catch (e) { box.textContent = e.message; }
}
$("#testAsk").addEventListener("click", askTest);
$("#testQuestion").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); askTest(); } });

/* ---------- Suggestions ---------- */
async function loadSuggestions() {
  const list = $("#sList");
  try {
    const items = await api("/api/admin/suggestions");
    list.innerHTML = items.map(item => `
      <article class="suggestion-item ${item.status === "New" ? "is-new" : ""}">
        <div class="suggestion-item-top">
          <strong>${escapeHTML(item.subject)}</strong>
          <span class="status-pill ${item.status === "New" ? "new" : ""}">${escapeHTML(item.status)}</span>
        </div>
        <p>${escapeHTML(item.message)}</p>
        <div class="suggestion-item-bottom">
          <small>From ${escapeHTML(item.name)} · ${escapeHTML(item.date)}</small>
          <span>
            ${item.status === "New" ? `<button class="text-link" data-read="${item.id}" type="button">Mark as read</button>` : ""}
            <button class="delete-btn" data-del-s="${item.id}" type="button">Delete</button>
          </span>
        </div>
      </article>`).join("") || `<p class="empty-note">No suggestions yet. Ones sent from the public form appear here.</p>`;
    $$("#sList [data-read]").forEach(btn => btn.addEventListener("click", async () => {
      try { await api(`/api/admin/suggestions/${btn.dataset.read}/read`, { method: "POST" }); loadSuggestions(); loadSummary(); }
      catch (e) { showToast(e.message); }
    }));
    $$("#sList [data-del-s]").forEach(btn => btn.addEventListener("click", async () => {
      if (!confirm("Delete this suggestion permanently?")) return;
      try { await api(`/api/admin/suggestions/${btn.dataset.delS}`, { method: "DELETE" }); showToast("Suggestion deleted."); loadSuggestions(); loadSummary(); }
      catch (e) { showToast(e.message); }
    }));
  } catch (e) { list.textContent = e.message; }
}
$("#refreshSuggestions").addEventListener("click", () => { loadSuggestions(); loadSummary(); });

/* ---------- Problem reports ---------- */
async function loadReports() {
  const list = $("#rList");
  try {
    const items = await api("/api/admin/reports");
    list.innerHTML = items.map(r => `
      <article class="suggestion-item ${r.status === "New" ? "is-new" : ""}">
        <div class="suggestion-item-top">
          <strong>#${r.id} · ${escapeHTML(r.type)}</strong>
          <span class="status-pill ${r.status === "New" ? "new" : ""}">${escapeHTML(r.status)}</span>
        </div>
        <p>${escapeHTML(r.details)}</p>
        <details class="tech"><summary>Technical details</summary>
          <dl>
            <dt>Page</dt><dd>${escapeHTML(r.page_url || "not included")}</dd>
            <dt>Device</dt><dd>${escapeHTML(r.user_agent || "not included")}</dd>
            <dt>Screen</dt><dd>${escapeHTML(r.viewport || "not included")}</dd>
            <dt>Errors</dt><dd>${(r.js_errors || []).map(escapeHTML).join("<br>") || "none recorded"}</dd>
            <dt>Contact</dt><dd>${escapeHTML(r.contact || "not provided")}</dd>
          </dl>
        </details>
        <div class="suggestion-item-bottom">
          <small>${escapeHTML(r.date)} · ${escapeHTML(r.time)}</small>
          <span>
            ${r.status === "New" ? `<button class="text-link" data-resolve="${r.id}" type="button">Mark as resolved</button>` : ""}
            <button class="delete-btn" data-del-r="${r.id}" type="button">Delete</button>
          </span>
        </div>
      </article>`).join("") || `<p class="empty-note">No problem reports. Good news!</p>`;
    $$("#rList [data-resolve]").forEach(btn => btn.addEventListener("click", async () => {
      try { await api(`/api/admin/reports/${btn.dataset.resolve}/resolve`, { method: "POST" }); loadReports(); loadSummary(); }
      catch (e) { showToast(e.message); }
    }));
    $$("#rList [data-del-r]").forEach(btn => btn.addEventListener("click", async () => {
      if (!confirm("Delete this report permanently?")) return;
      try { await api(`/api/admin/reports/${btn.dataset.delR}`, { method: "DELETE" }); loadReports(); loadSummary(); }
      catch (e) { showToast(e.message); }
    }));
  } catch (e) { list.textContent = e.message; }
}
$("#refreshReports").addEventListener("click", () => { loadReports(); loadSummary(); });

reloadAll(); loadSuggestions(); loadReports();
