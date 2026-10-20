// Remember the last few JavaScript errors so a "Report a problem" can include them.
window.__jsErrors = [];
function rememberError(text) {
  window.__jsErrors.push(String(text).slice(0, 300));
  if (window.__jsErrors.length > 5) window.__jsErrors.shift();
}
window.addEventListener("error", e => rememberError(`${e.message} (${(e.filename || "").split("/").pop()}:${e.lineno})`));
window.addEventListener("unhandledrejection", e => rememberError("Promise: " + (e.reason && e.reason.message || e.reason)));

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "Something went wrong. Please try again.");
  return data;
}

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
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2800);
}

/* ---------------------------------------------------------------
   MEDIA: sliders on cards, hover preview, and the expanded viewer
---------------------------------------------------------------- */
const mediaStore = {};            // "announcement-3" -> item, so the viewer can find it
const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

function formatSize(bytes) {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
  return Math.max(1, Math.round(bytes / 1024)) + " KB";
}
function fileIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  return { pdf: "PDF", doc: "DOC", docx: "DOC", xls: "XLS", xlsx: "XLS", ppt: "PPT", pptx: "PPT", txt: "TXT", csv: "CSV" }[ext] || "FILE";
}

// Photos and videos go in the slider; documents become file chips.
function mediaHTML(key, item) {
  const visual = (item.media || []).filter(m => m.kind !== "file");
  const files = (item.media || []).filter(m => m.kind === "file");
  let html = "";
  if (visual.length) {
    const slides = visual.map((m, i) => m.kind === "video"
      ? `<div class="media-slide" data-index="${i}"><video src="${escapeHTML(m.url)}#t=0.1" muted loop playsinline preload="metadata" aria-label="${escapeHTML(m.name)}"></video><span class="play-badge" aria-hidden="true">▶</span></div>`
      : `<div class="media-slide" data-index="${i}"><img src="${escapeHTML(m.url)}" alt="${escapeHTML(m.name)}" loading="lazy"></div>`).join("");
    const many = visual.length > 1;
    html += `<div class="media-slider" data-key="${key}">
      <div class="media-track">${slides}</div>
      ${many ? `<button type="button" class="slider-btn prev" aria-label="Previous photo or video">‹</button>
      <button type="button" class="slider-btn next" aria-label="Next photo or video">›</button>
      <div class="slider-dots">${visual.map((_, i) => `<i class="${i === 0 ? "active" : ""}"></i>`).join("")}</div>
      <span class="media-count">1/${visual.length}</span>` : ""}
      <button type="button" class="expand-btn" data-expand aria-label="Expanded view">⤢ Expand</button>
    </div>`;
  }
  if (files.length) {
    html += `<div class="file-list">${files.map(m => `
      <div class="file-chip"><span class="file-badge">${fileIcon(m.name)}</span>
        <span class="file-name"><strong>${escapeHTML(m.name)}</strong><small>${formatSize(m.size)}</small></span>
        <button type="button" class="file-expand" data-expand-file="${escapeHTML(m.id)}">Expand</button>
        <a class="file-download" href="${escapeHTML(m.url)}" download="${escapeHTML(m.name)}">Download</a>
      </div>`).join("")}</div>`;
  }
  return html;
}

// ---- slider behaviour (works by touch-swipe, arrows, and hover)
function sliderIndex(slider) {
  const track = slider.querySelector(".media-track");
  return Math.round(track.scrollLeft / Math.max(1, track.clientWidth));
}
function updateSlider(slider) {
  const i = sliderIndex(slider);
  slider.querySelectorAll(".slider-dots i").forEach((d, n) => d.classList.toggle("active", n === i));
  const count = slider.querySelector(".media-count");
  if (count) count.textContent = `${i + 1}/${slider.querySelectorAll(".media-slide").length}`;
  slider.querySelectorAll("video").forEach((v, n) => { if (n !== i || !slider.matches(":hover")) v.pause(); });
  if (slider.matches(":hover") && canHover) {
    const cur = slider.querySelectorAll(".media-slide")[i].querySelector("video");
    if (cur) cur.play().catch(() => {});
  }
}
function goSlide(slider, delta, wrap) {
  const track = slider.querySelector(".media-track");
  const total = slider.querySelectorAll(".media-slide").length;
  let next = sliderIndex(slider) + delta;
  if (wrap) next = (next + total) % total; else next = Math.min(total - 1, Math.max(0, next));
  track.scrollTo({ left: next * track.clientWidth, behavior: "smooth" });
}

document.addEventListener("scroll", event => {
  const track = event.target;
  if (track.classList && track.classList.contains("media-track")) {
    cancelAnimationFrame(track._raf);
    track._raf = requestAnimationFrame(() => updateSlider(track.closest(".media-slider")));
  }
}, true);

document.addEventListener("click", event => {
  const slider = event.target.closest(".media-slider");
  const chip = event.target.closest("[data-expand-file]");
  if (chip) {
    const card = chip.closest("[data-key]");
    const item = mediaStore[card.dataset.key];
    const all = orderedMedia(item);
    openViewer(all, all.findIndex(m => m.id === chip.dataset.expandFile), item.title);
    return;
  }
  if (!slider) return;
  const item = mediaStore[slider.dataset.key];
  if (event.target.closest(".slider-btn")) {
    event.stopPropagation();
    goSlide(slider, event.target.closest(".slider-btn").classList.contains("next") ? 1 : -1, true);
    return;
  }
  // Tapping the media or the Expand button opens the large view.
  openViewer(orderedMedia(item), sliderIndex(slider), item.title);
});

// Hover preview on computers: play videos silently and rotate through photos.
document.addEventListener("mouseover", event => {
  if (!canHover) return;
  const card = event.target.closest(".announcement-card, .event-card");
  if (!card || card._hovering) return;
  const slider = card.querySelector(".media-slider");
  if (!slider) return;
  card._hovering = true;
  updateSlider(slider);
  if (slider.querySelectorAll(".media-slide").length > 1) {
    card._timer = setInterval(() => {
      const cur = slider.querySelectorAll(".media-slide")[sliderIndex(slider)].querySelector("video");
      if (cur && !cur.ended && !cur.paused && cur.currentTime < cur.duration - 0.3) return; // let the video finish
      goSlide(slider, 1, true);
    }, 2400);
  }
});
document.addEventListener("mouseout", event => {
  const card = event.target.closest(".announcement-card, .event-card");
  if (!card || !card._hovering || card.contains(event.relatedTarget)) return;
  card._hovering = false;
  clearInterval(card._timer);
  card.querySelectorAll("video").forEach(v => v.pause());
});

// ---- expanded viewer (photos, videos, PDFs, other files)
function orderedMedia(item) {
  const media = item.media || [];
  return [...media.filter(m => m.kind !== "file"), ...media.filter(m => m.kind === "file")];
}
const viewer = $("#viewer");
const viewerState = { items: [], index: 0, opener: null, touchX: null };

function renderViewer() {
  const m = viewerState.items[viewerState.index];
  const stage = $("#viewerStage");
  stage.innerHTML = "";
  let node;
  if (m.kind === "image") {
    node = document.createElement("img"); node.src = m.url; node.alt = m.name;
  } else if (m.kind === "video") {
    node = document.createElement("video"); node.src = m.url; node.controls = true; node.autoplay = true; node.playsInline = true;
    node.setAttribute("playsinline", "");
  } else if (m.name.toLowerCase().endsWith(".pdf") && window.innerWidth > 800) {
    node = document.createElement("iframe"); node.src = m.url; node.title = m.name;
  } else {
    node = document.createElement("div"); node.className = "viewer-file";
    node.innerHTML = `<span class="file-badge big">${fileIcon(m.name)}</span><strong>${escapeHTML(m.name)}</strong><small>${formatSize(m.size)}</small>
      <a class="btn btn-primary" href="${escapeHTML(m.url)}" target="_blank" rel="noopener">Open file</a>
      <a class="btn btn-secondary" href="${escapeHTML(m.url)}" download="${escapeHTML(m.name)}">Download</a>`;
  }
  stage.appendChild(node);
  $("#viewerCount").textContent = viewerState.items.length > 1 ? `${viewerState.index + 1} / ${viewerState.items.length}` : "";
  $("#viewerOpen").href = m.url;
  const multi = viewerState.items.length > 1;
  $("#viewerPrev").classList.toggle("hidden", !multi);
  $("#viewerNext").classList.toggle("hidden", !multi);
}
function openViewer(items, index = 0, title = "") {
  if (!items.length) return;
  viewerState.items = items;
  viewerState.index = Math.max(0, index);
  viewerState.opener = document.activeElement;
  $("#viewerTitle").textContent = title;
  renderViewer();
  viewer.classList.remove("hidden");
  document.documentElement.classList.add("no-scroll");
  $("#viewerClose").focus();
}
function closeViewer() {
  if (viewer.classList.contains("hidden")) return;
  viewer.classList.add("hidden");
  $("#viewerStage").innerHTML = "";          // also stops any playing video
  document.documentElement.classList.remove("no-scroll");
  if (viewerState.opener && viewerState.opener.focus) viewerState.opener.focus();
}
function stepViewer(delta) {
  const n = viewerState.items.length;
  if (n < 2) return;
  viewerState.index = (viewerState.index + delta + n) % n;
  renderViewer();
}
$("#viewerClose").addEventListener("click", closeViewer);
$("#viewerPrev").addEventListener("click", () => stepViewer(-1));
$("#viewerNext").addEventListener("click", () => stepViewer(1));
viewer.addEventListener("click", event => { if (event.target.id === "viewerStage") closeViewer(); });
viewer.addEventListener("touchstart", e => { viewerState.touchX = e.touches[0].clientX; }, { passive: true });
viewer.addEventListener("touchend", e => {
  if (viewerState.touchX === null) return;
  const dx = e.changedTouches[0].clientX - viewerState.touchX;
  viewerState.touchX = null;
  if (Math.abs(dx) > 60) stepViewer(dx < 0 ? 1 : -1);
});

async function loadAnnouncements() {
  const query = $("#announcementSearch").value.trim();
  const category = $("#categoryFilter").value;
  const grid = $("#announcementGrid");
  try {
    const items = await api(`/api/announcements?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`);
    $("#statAnnouncements").textContent = String(items.length).padStart(2, "0");
    $("#announcementEmpty").classList.toggle("hidden", items.length !== 0);
    grid.classList.toggle("hidden", items.length === 0);
    items.forEach(item => { mediaStore["announcement-" + item.id] = item; });
    grid.innerHTML = items.map(item => `
      <article class="announcement-card ${item.media.length ? "has-media" : ""}" data-key="announcement-${item.id}">
        ${mediaHTML("announcement-" + item.id, item)}
        <div class="card-topline"><span class="category-pill">${escapeHTML(item.category)}</span><span class="card-date">${escapeHTML(item.date)}</span></div>
        <h3>${escapeHTML(item.title)}</h3>
        <p>${escapeHTML(item.description)}</p>
        <div class="card-footer"><span>Community update</span><span>↗</span></div>
      </article>`).join("");
  } catch (error) {
    grid.innerHTML = `<div class="loading-card">Could not load announcements: ${escapeHTML(error.message)}</div>`;
  }
}

async function loadEvents() {
  const grid = $("#eventsGrid");
  try {
    const items = await api("/api/events");
    $("#statEvents").textContent = String(items.length).padStart(2, "0");
    items.forEach(item => { mediaStore["event-" + item.id] = item; });
    grid.innerHTML = items.map(item => `
      <article class="event-card ${item.media.length ? "has-media" : ""}" data-key="event-${item.id}">
        <div class="event-date"><strong>${escapeHTML(item.day)}</strong><small>${escapeHTML(item.month)}</small></div>
        <div class="event-info"><h3>${escapeHTML(item.title)}</h3>
          <div class="event-meta"><span>◷ ${escapeHTML(item.date)} · ${escapeHTML(item.time)}</span><span>⌖ ${escapeHTML(item.location)}</span></div>
          <p>${escapeHTML(item.description)}</p>
          ${mediaHTML("event-" + item.id, item)}
        </div><span class="event-tag">SAMPLE</span>
      </article>`).join("") || `<div class="loading-card">No events have been added.</div>`;
  } catch (error) { grid.innerHTML = `<div class="loading-card">${escapeHTML(error.message)}</div>`; }
}

async function loadServices() {
  const grid = $("#servicesGrid");
  try {
    const items = await api("/api/services");
    $("#statServices").textContent = String(items.length).padStart(2, "0");
    grid.innerHTML = items.map((item, index) => `
      <article class="service-card">
        <div class="service-icon">${escapeHTML(item.icon)}</div>
        <span class="service-tag">${escapeHTML(item.tag)}</span>
        <h3>${escapeHTML(item.name)}</h3>
        <p>${escapeHTML(item.description)}</p>
        <button type="button" data-service="${index}">View service details <span>→</span></button>
      </article>`).join("");
    $$("#servicesGrid [data-service]").forEach(button => button.addEventListener("click", () => {
      const item = items[Number(button.dataset.service)];
      showToast(item.name + ": " + item.details);
    }));
  } catch (error) { grid.innerHTML = `<div class="loading-card">${escapeHTML(error.message)}</div>`; }
}

$("#announcementSearch").addEventListener("input", loadAnnouncements);
$("#categoryFilter").addEventListener("change", loadAnnouncements);

$("#suggestionMessage").addEventListener("input", event => {
  $("#charCount").textContent = event.target.value.length;
});

$("#suggestionForm").addEventListener("submit", async event => {
  event.preventDefault();
  const status = $("#suggestionStatus");
  status.textContent = "Sending...";
  status.className = "form-message";
  const payload = {
    name: $("#suggestionName").value,
    subject: $("#suggestionSubject").value,
    message: $("#suggestionMessage").value
  };
  try {
    const result = await api("/api/suggestions", { method: "POST", body: JSON.stringify(payload) });
    status.textContent = result.message;
    status.className = "form-message success";
    event.target.reset();
    $("#charCount").textContent = "0";
  } catch (error) {
    status.textContent = error.message;
    status.className = "form-message error";
  }
});

const chatModal = $("#chatModal");
function openChat() { chatModal.classList.remove("hidden"); setTimeout(() => $("#chatInput").focus(), 100); }
function closeChat() { chatModal.classList.add("hidden"); }
$("#openChatTop").addEventListener("click", openChat);
$("#openChatBanner").addEventListener("click", openChat);
$("#openChatFab").addEventListener("click", openChat);
$("#closeChat").addEventListener("click", closeChat);
chatModal.addEventListener("click", event => { if (event.target === chatModal) closeChat(); });

function appendChat(text, type, media = []) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${type === "user" ? "user-bubble" : "bot-bubble"}`;
  bubble.textContent = text;
  const box = $("#chatMessages");
  box.appendChild(bubble);
  // Admin-provided demo video and/or guide pictures become buttons under the answer.
  const videos = media.filter(m => m.kind === "video");
  const pictures = media.filter(m => m.kind === "image");
  if (videos.length || pictures.length) {
    const row = document.createElement("div");
    row.className = "chat-media-row";
    if (videos.length) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chat-demo-btn"; b.textContent = "▶ Click for video demo";
      b.addEventListener("click", () => openViewer(videos.map(v => ({ ...v, size: 0 })), 0, "Video demo"));
      row.appendChild(b);
    }
    if (pictures.length) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chat-demo-btn alt"; b.textContent = "🖼 View guide pictures";
      b.addEventListener("click", () => openViewer(pictures.map(v => ({ ...v, size: 0 })), 0, "Guide pictures"));
      row.appendChild(b);
    }
    box.appendChild(row);
  }
  box.scrollTop = box.scrollHeight;
}

async function sendChat(message) {
  if (!message.trim()) return;
  appendChat(message, "user");
  $("#chatInput").value = "";
  $$(".suggested-questions").forEach(el => el.remove());
  try {
    const result = await api("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
    appendChat(result.reply, "bot", result.media || []);
  } catch (error) { appendChat(error.message, "bot"); }
}
$("#chatForm").addEventListener("submit", event => {
  event.preventDefault();
  sendChat($("#chatInput").value);
});
$$(".suggested-questions button").forEach(button => button.addEventListener("click", () => sendChat(button.dataset.question)));

$("#mobileMenuBtn").addEventListener("click", () => $("#navLinks").classList.toggle("open"));
$$(".nav-links a").forEach(link => link.addEventListener("click", () => $("#navLinks").classList.remove("open")));
$$(".nav-link").forEach(link => link.addEventListener("click", () => {
  $$(".nav-link").forEach(other => other.classList.remove("active"));
  link.classList.add("active");
}));

document.addEventListener("keydown", event => {
  if (!viewer.classList.contains("hidden")) {
    if (event.key === "Escape") closeViewer();
    if (event.key === "ArrowRight") stepViewer(1);
    if (event.key === "ArrowLeft") stepViewer(-1);
    return;
  }
  if (event.key === "Escape") { closeChat(); closeReport(); }
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    $("#announcementSearch").focus();
  }
});

/* ---------------------------------------------------------------
   REPORT A PROBLEM
   If sending fails (no signal, server down), the report is kept on
   the device and sent automatically the next time the site opens.
---------------------------------------------------------------- */
const reportModal = $("#reportModal");
function openReport() { reportModal.classList.remove("hidden"); $("#reportStatus").textContent = ""; setTimeout(() => $("#reportDetails").focus(), 100); }
function closeReport() { reportModal.classList.add("hidden"); }
$$("[data-open-report]").forEach(b => b.addEventListener("click", openReport));
$("#closeReport").addEventListener("click", closeReport);
reportModal.addEventListener("click", event => { if (event.target === reportModal) closeReport(); });

function loadQueue() { try { return JSON.parse(localStorage.getItem("pendingReports") || "[]"); } catch (e) { return []; } }
function saveQueue(queue) { try { localStorage.setItem("pendingReports", JSON.stringify(queue.slice(-5))); } catch (e) { /* storage blocked: ignore */ } }

async function sendReport(payload) {
  const response = await fetch("/api/problem-reports", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) { const err = new Error(data.message || "The report could not be sent."); err.permanent = response.status >= 400 && response.status < 500; throw err; }
  return data;
}

let flushing = false;           // stops two flushes from sending the same report twice
async function flushQueue() {
  if (flushing) return;
  const queue = loadQueue();
  if (!queue.length) return;
  flushing = true;
  saveQueue([]);                // take them out first; put back only the ones that fail
  const left = [];
  for (const payload of queue) {
    try { await sendReport(payload); } catch (e) { if (!e.permanent) left.push(payload); }
  }
  saveQueue([...left, ...loadQueue()]);
  flushing = false;
}

$("#reportForm").addEventListener("submit", async event => {
  event.preventDefault();
  const status = $("#reportStatus");
  const button = $("#reportSubmit");
  const tech = $("#reportTech").checked;
  const payload = {
    type: $("#reportType").value,
    details: $("#reportDetails").value,
    contact: $("#reportContact").value,
    page_url: location.href,
    user_agent: tech ? navigator.userAgent : "",
    viewport: tech ? `${window.innerWidth}x${window.innerHeight}` : "",
    js_errors: tech ? window.__jsErrors : []
  };
  button.disabled = true;
  status.className = "form-message"; status.textContent = "Sending...";
  try {
    const result = await sendReport(payload);
    status.textContent = result.message; status.className = "form-message success";
    event.target.reset();
    setTimeout(closeReport, 2500);
  } catch (error) {
    if (error.permanent) {                    // e.g. empty text or too many reports: tell the person
      status.textContent = error.message; status.className = "form-message error";
    } else {                                  // network or server problem: keep it and retry later
      saveQueue([...loadQueue(), payload]);
      status.textContent = "We could not reach the server, but your report has been saved on this device and will be sent automatically once the connection returns.";
      status.className = "form-message success";
      event.target.reset();
      setTimeout(closeReport, 4500);
    }
  } finally { button.disabled = false; }
});
window.addEventListener("online", flushQueue);

loadAnnouncements();
loadEvents();
loadServices();
flushQueue();
