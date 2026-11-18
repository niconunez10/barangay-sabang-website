window.__jsErrors = [];
window.addEventListener("error", event => {
  window.__jsErrors.push(`${event.message} (${(event.filename || "").split("/").pop()}:${event.lineno})`.slice(0, 300));
  window.__jsErrors = window.__jsErrors.slice(-5);
});
window.addEventListener("unhandledrejection", event => {
  window.__jsErrors.push(`Promise: ${(event.reason && event.reason.message) || event.reason}`.slice(0, 300));
  window.__jsErrors = window.__jsErrors.slice(-5);
});

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

function escapeHTML(value = "") {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[char]);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || data.detail || "Please try again.");
  return data;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function skeletonCard(type = "") {
  return `<div class="skeleton-card ${type}" aria-label="Loading"></div>`;
}

function errorState(loadFunction) {
  return `<div class="error-state"><strong>Could not load this information.</strong><p>Please check your connection and try again.</p><button class="btn btn-primary" type="button" data-retry="${loadFunction}">Retry</button></div>`;
}

const mediaStore = {};
const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

function formatSize(bytes) {
  const size = Number(bytes) || 0;
  return size >= 1048576 ? `${(size / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(size / 1024))} KB`;
}

function fileIcon(name) {
  const ext = String(name).split(".").pop().toLowerCase();
  return ({ pdf: "PDF", doc: "DOC", docx: "DOC", xls: "XLS", xlsx: "XLS", ppt: "PPT", pptx: "PPT", txt: "TXT", csv: "CSV" })[ext] || "FILE";
}

function mediaHTML(key, item) {
  const media = item.media || [];
  const visual = media.filter(value => value.kind !== "file");
  const files = media.filter(value => value.kind === "file");
  let html = "";
  if (visual.length) {
    const slides = visual.map((value, index) => value.kind === "video"
      ? `<div class="media-slide" data-index="${index}"><video src="${escapeHTML(value.url)}#t=0.1" muted loop playsinline preload="metadata" aria-label="${escapeHTML(value.name)}"></video></div>`
      : `<div class="media-slide" data-index="${index}"><img src="${escapeHTML(value.url)}" alt="${escapeHTML(value.name)}" loading="lazy"></div>`
    ).join("");
    html += `<div class="media-slider" data-key="${key}">
      <div class="media-track">${slides}</div>
      ${visual.length > 1 ? `<button type="button" class="slider-btn prev" aria-label="Previous">‹</button><button type="button" class="slider-btn next" aria-label="Next">›</button><span class="media-count">1/${visual.length}</span>` : ""}
      <button type="button" class="expand-btn" data-expand aria-label="Expand media">Expand</button>
    </div>`;
  }
  if (files.length) {
    html += `<div class="file-list">${files.map(value => `
      <div class="file-chip">
        <span class="file-badge">${fileIcon(value.name)}</span>
        <span class="file-name"><strong>${escapeHTML(value.name)}</strong><small>${formatSize(value.size)}</small></span>
        <button type="button" class="file-expand" data-expand-file="${escapeHTML(value.id)}">Expand</button>
        <a class="file-download" href="${escapeHTML(value.url)}" download="${escapeHTML(value.name)}">Download</a>
      </div>`).join("")}</div>`;
  }
  return html;
}

function sliderIndex(slider) {
  const track = slider.querySelector(".media-track");
  return Math.round(track.scrollLeft / Math.max(1, track.clientWidth));
}

function goSlide(slider, delta) {
  const track = slider.querySelector(".media-track");
  const total = slider.querySelectorAll(".media-slide").length;
  const next = (sliderIndex(slider) + delta + total) % total;
  track.scrollTo({ left: next * track.clientWidth, behavior: "smooth" });
}

const viewer = $("#viewer");
const viewerState = { items: [], index: 0, opener: null, touchX: null };

function orderedMedia(item) {
  const media = item.media || [];
  return [...media.filter(value => value.kind !== "file"), ...media.filter(value => value.kind === "file")];
}

function renderViewer() {
  const media = viewerState.items[viewerState.index];
  const stage = $("#viewerStage");
  stage.innerHTML = "";
  let node;
  if (media.kind === "image") {
    node = document.createElement("img");
    node.src = media.url;
    node.alt = media.name;
  } else if (media.kind === "video") {
    node = document.createElement("video");
    node.src = media.url;
    node.controls = true;
    node.autoplay = true;
    node.playsInline = true;
  } else if (media.name.toLowerCase().endsWith(".pdf") && window.innerWidth > 800) {
    node = document.createElement("iframe");
    node.src = media.url;
    node.title = media.name;
  } else {
    node = document.createElement("div");
    node.className = "viewer-file";
    node.innerHTML = `<span class="file-badge big">${fileIcon(media.name)}</span><strong>${escapeHTML(media.name)}</strong><small>${formatSize(media.size)}</small><a class="btn btn-primary" href="${escapeHTML(media.url)}" target="_blank" rel="noopener">Open file</a><a class="btn btn-secondary" href="${escapeHTML(media.url)}" download="${escapeHTML(media.name)}">Download</a>`;
  }
  stage.appendChild(node);
  $("#viewerCount").textContent = viewerState.items.length > 1 ? `${viewerState.index + 1} / ${viewerState.items.length}` : "";
  $("#viewerOpen").href = media.url;
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
  $("#viewerStage").innerHTML = "";
  document.documentElement.classList.remove("no-scroll");
  if (viewerState.opener?.focus) viewerState.opener.focus();
}

function stepViewer(delta) {
  if (viewerState.items.length < 2) return;
  viewerState.index = (viewerState.index + delta + viewerState.items.length) % viewerState.items.length;
  renderViewer();
}

$("#viewerClose").addEventListener("click", closeViewer);
$("#viewerPrev").addEventListener("click", () => stepViewer(-1));
$("#viewerNext").addEventListener("click", () => stepViewer(1));
viewer.addEventListener("click", event => { if (event.target.id === "viewerStage") closeViewer(); });
viewer.addEventListener("touchstart", event => { viewerState.touchX = event.touches[0].clientX; }, { passive: true });
viewer.addEventListener("touchend", event => {
  if (viewerState.touchX === null) return;
  const difference = event.changedTouches[0].clientX - viewerState.touchX;
  viewerState.touchX = null;
  if (Math.abs(difference) > 60) stepViewer(difference < 0 ? 1 : -1);
});

document.addEventListener("click", event => {
  const slider = event.target.closest(".media-slider");
  const fileButton = event.target.closest("[data-expand-file]");
  if (fileButton) {
    const card = fileButton.closest("[data-key]");
    const item = mediaStore[card.dataset.key];
    const media = orderedMedia(item);
    openViewer(media, media.findIndex(value => value.id === fileButton.dataset.expandFile), item.title);
    return;
  }
  if (!slider) return;
  const item = mediaStore[slider.dataset.key];
  if (event.target.closest(".slider-btn")) {
    event.stopPropagation();
    goSlide(slider, event.target.closest(".slider-btn").classList.contains("next") ? 1 : -1);
  } else {
    openViewer(orderedMedia(item), sliderIndex(slider), item.title);
  }
});

async function loadAnnouncements() {
  const grid = $("#announcementGrid");
  try {
    const query = $("#announcementSearch").value.trim();
    const category = $("#categoryFilter").value;
    const items = await api(`/api/announcements?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`);
    $("#announcementEmpty").classList.toggle("hidden", items.length !== 0);
    grid.classList.toggle("hidden", items.length === 0);
    if (!items.length) return;
    items.forEach(item => { mediaStore[`announcement-${item.id}`] = item; });
    grid.innerHTML = items.map(item => `
      <article class="announcement-card reveal ${item.media?.length ? "has-media" : ""}" data-key="announcement-${item.id}">
        ${mediaHTML(`announcement-${item.id}`, item)}
        <div class="card-topline"><span class="category-pill">${escapeHTML(item.category)}</span><span class="card-date">${escapeHTML(item.date)}</span></div>
        <h3>${escapeHTML(item.title)}</h3>
        <p>${escapeHTML(item.description)}</p>
        <div class="card-footer"><span>Community update</span><span aria-hidden="true">→</span></div>
      </article>`).join("");
    setupReveal();
  } catch (error) {
    grid.classList.remove("hidden");
    $("#announcementEmpty").classList.add("hidden");
    grid.innerHTML = errorState("announcements");
  }
}

async function loadEvents() {
  const grid = $("#eventsGrid");
  try {
    const items = await api("/api/events");
    items.forEach(item => { mediaStore[`event-${item.id}`] = item; });
    grid.innerHTML = items.length ? items.map(item => `
      <article class="event-card reveal ${item.media?.length ? "has-media" : ""}" data-key="event-${item.id}">
        <div class="event-date"><strong>${escapeHTML(item.day)}</strong><small>${escapeHTML(item.month)}</small></div>
        <div class="event-info">
          <h3>${escapeHTML(item.title)}</h3>
          <div class="event-meta"><span>${escapeHTML(item.date)} · ${escapeHTML(item.time)}</span><span>${escapeHTML(item.location)}</span></div>
          ${mediaHTML(`event-${item.id}`, item)}
        </div>
      </article>`).join("") : `<div class="empty-state"><strong>No upcoming events.</strong><p>Check back for new activities.</p></div>`;
    setupReveal();
  } catch (error) {
    grid.innerHTML = errorState("events");
  }
}

async function loadServices() {
  const grid = $("#servicesGrid");
  try {
    const items = await api("/api/services");
    grid.innerHTML = items.length ? items.map(item => `
      <article class="service-card reveal">
        <div class="service-icon">${escapeHTML(item.icon)}</div>
        <span class="service-tag">${escapeHTML(item.tag)}</span>
        <h3>${escapeHTML(item.name)}</h3>
        <p>${escapeHTML(item.description)}</p>
        <div class="service-details">
          <p><strong>Office hours:</strong> Confirm with the barangay office.</p>
          <p><strong>Requirements:</strong> ${escapeHTML(item.details || "Confirm with the barangay office.")}</p>
        </div>
      </article>`).join("") : `<div class="empty-state"><strong>No resident services yet.</strong><p>Check back for available services.</p></div>`;
    setupReveal();
  } catch (error) {
    grid.innerHTML = errorState("services");
  }
}

let revealObserver;
function setupReveal() {
  if (!("IntersectionObserver" in window)) {
    $$(".reveal").forEach(card => card.classList.add("visible"));
    return;
  }
  if (!revealObserver) {
    revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
  }
  $$(".reveal").forEach((card, index) => {
    card.style.transitionDelay = `${Math.min(index % 3, 2) * 80}ms`;
    revealObserver.observe(card);
  });
}

document.addEventListener("click", event => {
  const retry = event.target.closest("[data-retry]");
  if (!retry) return;
  const loader = { announcements: loadAnnouncements, events: loadEvents, services: loadServices }[retry.dataset.retry];
  if (loader) {
    retry.closest(".error-state").innerHTML = skeletonCard();
    loader();
  }
});

const header = $("#siteHeader");
window.addEventListener("scroll", () => header.classList.toggle("scrolled", window.scrollY > 24), { passive: true });
header.classList.add("seal-load");

const heroPhotos = $$(".hero-photo");
if (heroPhotos.length > 1 && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  let activeHeroPhoto = 0;
  window.setInterval(() => {
    heroPhotos[activeHeroPhoto].classList.remove("is-active");
    heroPhotos[activeHeroPhoto].setAttribute("aria-hidden", "true");
    activeHeroPhoto = (activeHeroPhoto + 1) % heroPhotos.length;
    heroPhotos[activeHeroPhoto].classList.add("is-active");
    heroPhotos[activeHeroPhoto].removeAttribute("aria-hidden");
  }, 5000);
}

const mobileMenu = $("#mobileMenuBtn");
mobileMenu.addEventListener("click", () => {
  const open = $("#navLinks").classList.toggle("open");
  mobileMenu.setAttribute("aria-expanded", String(open));
});
$$(".nav-link").forEach(link => link.addEventListener("click", () => {
  $("#navLinks").classList.remove("open");
  mobileMenu.setAttribute("aria-expanded", "false");
  $$(".nav-link").forEach(other => other.classList.remove("active"));
  link.classList.add("active");
}));

$("#announcementSearch").addEventListener("input", loadAnnouncements);
$("#categoryFilter").addEventListener("change", loadAnnouncements);

const feedbackType = $("#feedbackType");
const reportDetailsGroup = $("#reportDetailsGroup");
feedbackType.addEventListener("change", () => {
  const isProblem = feedbackType.value === "Problem";
  reportDetailsGroup.classList.toggle("hidden", !isProblem);
  $("#reportDetails").required = isProblem;
});

$("#suggestionMessage").addEventListener("input", event => {
  $("#charCount").textContent = event.target.value.length;
});

function loadQueue() {
  try { return JSON.parse(localStorage.getItem("pendingReports") || "[]"); } catch (error) { return []; }
}

function saveQueue(queue) {
  try { localStorage.setItem("pendingReports", JSON.stringify(queue.slice(-5))); } catch (error) {}
}

async function sendReport(payload) {
  const response = await fetch("/api/problem-reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.message || "The report could not be sent.");
    error.permanent = response.status >= 400 && response.status < 500;
    throw error;
  }
  return data;
}

let flushing = false;
async function flushQueue() {
  if (flushing) return;
  const queue = loadQueue();
  if (!queue.length) return;
  flushing = true;
  saveQueue([]);
  const remaining = [];
  for (const payload of queue) {
    try { await sendReport(payload); } catch (error) { if (!error.permanent) remaining.push(payload); }
  }
  saveQueue([...remaining, ...loadQueue()]);
  flushing = false;
}
window.addEventListener("online", flushQueue);

$("#suggestionForm").addEventListener("submit", async event => {
  event.preventDefault();
  const status = $("#suggestionStatus");
  const button = $("#suggestionSubmit");
  button.disabled = true;
  button.className = "btn btn-primary submit-button loading";
  status.textContent = "Sending...";
  status.className = "form-message";

  if (feedbackType.value === "Problem") {
    const payload = {
      type: "Something is not working",
      details: $("#reportDetails").value,
      contact: $("#reportContact").value,
      page_url: location.href,
      user_agent: $("#reportTech").checked ? navigator.userAgent : "",
      viewport: $("#reportTech").checked ? `${window.innerWidth}x${window.innerHeight}` : "",
      js_errors: $("#reportTech").checked ? window.__jsErrors : []
    };
    try {
      const result = await sendReport(payload);
      status.textContent = result.message;
      status.className = "form-message success";
      button.className = "btn btn-primary submit-button success";
      event.target.reset();
      $("#charCount").textContent = "0";
      reportDetailsGroup.classList.add("hidden");
      setTimeout(() => { button.className = "btn btn-primary submit-button"; }, 1800);
    } catch (error) {
      if (error.permanent) {
        status.textContent = error.message;
        status.className = "form-message error";
        button.className = "btn btn-primary submit-button";
      } else {
        saveQueue([...loadQueue(), payload]);
        status.textContent = "Your report was saved on this device. It will be sent when the connection returns.";
        status.className = "form-message success";
        button.className = "btn btn-primary submit-button success";
        event.target.reset();
        reportDetailsGroup.classList.add("hidden");
      }
    } finally {
      button.disabled = false;
    }
    return;
  }

  const payload = {
    name: $("#suggestionName").value,
    subject: $("#suggestionSubject").value,
    message: $("#suggestionMessage").value
  };
  try {
    const result = await api("/api/suggestions", { method: "POST", body: JSON.stringify(payload) });
    status.textContent = result.message;
    status.className = "form-message success";
    button.className = "btn btn-primary submit-button success";
    event.target.reset();
    $("#charCount").textContent = "0";
    setTimeout(() => { button.className = "btn btn-primary submit-button"; }, 1800);
  } catch (error) {
    status.textContent = error.message;
    status.className = "form-message error";
    button.className = "btn btn-primary submit-button";
  } finally {
    button.disabled = false;
  }
});

const chatModal = $("#chatModal");
const chatInput = $("#chatInput");
const chatForm = $("#chatForm");
let chatBusy = false;

function openChat() {
  chatModal.classList.remove("hidden");
  $("#openChatFab").classList.add("opened");
  setTimeout(() => chatInput.focus(), 100);
}

function closeChat() {
  chatModal.classList.add("hidden");
  $("#openChatFab").focus();
}

function addChatBubble(text, type = "bot") {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${type === "user" ? "user-bubble" : "bot-bubble"}`;
  bubble.textContent = text;
  $("#chatMessages").appendChild(bubble);
  bubble.scrollIntoView({ block: "nearest" });
}

async function sendChat(question) {
  if (chatBusy || !question.trim()) return;
  chatBusy = true;
  addChatBubble(question, "user");
  chatInput.value = "";
  const loading = document.createElement("div");
  loading.className = "chat-bubble bot-bubble";
  loading.textContent = "Please wait...";
  $("#chatMessages").appendChild(loading);
  try {
    const result = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message: question })
    });
    loading.remove();
    addChatBubble(result.reply || "Please contact the barangay office for more information.");
  } catch (error) {
    loading.remove();
    addChatBubble("The assistant could not respond. Please try again.");
  } finally {
    chatBusy = false;
  }
}

$("#openChatFab").addEventListener("click", openChat);
$("#closeChat").addEventListener("click", closeChat);
chatModal.addEventListener("click", event => { if (event.target === chatModal) closeChat(); });
chatForm.addEventListener("submit", event => {
  event.preventDefault();
  sendChat(chatInput.value);
});
$$("[data-question]").forEach(button => button.addEventListener("click", () => sendChat(button.dataset.question)));

document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    if (!viewer.classList.contains("hidden")) closeViewer();
    if (!chatModal.classList.contains("hidden")) closeChat();
  }
  if (!viewer.classList.contains("hidden")) {
    if (event.key === "ArrowRight") stepViewer(1);
    if (event.key === "ArrowLeft") stepViewer(-1);
  }
});

loadAnnouncements();
loadEvents();
loadServices();
flushQueue();
