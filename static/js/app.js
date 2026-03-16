/* ─────────────────────────────────────────────────────────────
   Gymark · Subir Videos  –  Frontend Logic
───────────────────────────────────────────────────────────── */

const API = ""; // same origin
let selectedHashtags = new Set();
let scheduleMode = "auto";
let currentFilter = "all";
let videos = [];
let currentBrand = "gymark";
let brandsData = []; // [{key, label, color, platforms, categories}]
let uploadBrand = "gymark"; // marca activa en el tab de subir

const PERFECT_WINDOWS = {
  gaming: {
    tiktok:
      "TikTok · COT · Mar 20:00 · Mié 21:00 · Jue 19:30 / 23:00 · Vie 20:00 · Sáb 20:00 / 22:00",
  },
  acc_gimnasio: {
    tiktok: "TikTok · COT · Mar / Jue 20:00",
    instagram: "Instagram · COT · Mar / Jue 12:00 y 19:00",
    facebook: "Facebook · COT · Mar / Jue 12:00 y 19:00",
  },
  pilates_yoga: {
    tiktok: "TikTok · COT · Mié / Sáb 19:30",
    instagram: "Instagram · COT · Mié / Sáb 11:00 y 19:00",
    facebook: "Facebook · COT · Mié / Sáb 09:00 y 19:00",
  },
  sup_naturales: {
    tiktok: "TikTok · COT · Mar / Mié 20:00",
    instagram: "Instagram · COT · Mar / Mié 11:00 y 19:00",
    facebook: "Facebook · COT · Mar / Mié 09:00 y 19:00",
  },
  ropa_deportiva: {
    tiktok: "TikTok · COT · Mar / Jue 20:00",
    instagram: "Instagram · COT · Mar / Jue 12:00 y 19:00",
    facebook: "Facebook · COT · Mar / Jue 12:00 y 19:00",
  },
  sup_deportivos: {
    tiktok: "TikTok · COT · Mar / Mié 20:00",
    instagram: "Instagram · COT · Mar / Mié 11:00 y 19:00",
    facebook: "Facebook · COT · Mar / Mié 09:00 y 19:00",
  },
  home_gym: {
    tiktok: "TikTok · COT · Jue / Vie 19:30",
    instagram: "Instagram · COT · Jue / Vie 12:00 y 19:30",
    facebook: "Facebook · COT · Jue / Vie 12:00 y 19:00",
  },
  milita_beauty: {
    tiktok:
      "TikTok · CST México · Mar 09:00 / 13:00 · Mié 10:00 · Jue 19:30 · Vie 10:00 / 19:30 · Dom 10:00",
  },
};

/* ══════════════════════════════════════════════════════════════
   INIT
════════════════════════════════════════════════════════════ */
document.addEventListener("DOMContentLoaded", () => {
  safeInit(initClock, "initClock");
  safeInit(initTabs, "initTabs");
  safeInit(initCalendar, "initCalendar");
  safeInit(initUpload, "initUpload");
  safeInit(initScheduleForm, "initScheduleForm");
  safeInit(initPostsFilter, "initPostsFilter");
  safeInit(loadDashboard, "loadDashboard");
  setInterval(loadDashboard, 30_000); // refresca cada 30s
});

function safeInit(fn, name) {
  try {
    fn();
  } catch (error) {
    console.error(`[Init Error] ${name}:`, error);
  }
}

function initScheduleForm() {
  // Compatibilidad: la lógica principal del tab Programar se inicializa en loadScheduleTab()
}

/* ══════════════════════════════════════════════════════════════
   CLOCK
════════════════════════════════════════════════════════════ */
function initClock() {
  const el = document.getElementById("currentTime");
  const tick = () => {
    const now = new Date().toLocaleString("es-CO", {
      timeZone: "America/Bogota",
      weekday: "short",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    el.textContent = now;
  };
  tick();
  setInterval(tick, 1000);
}

/* ══════════════════════════════════════════════════════════════
   TABS
════════════════════════════════════════════════════════════ */
function initTabs() {
  const titles = {
    dashboard: "Dashboard",
    upload: "Subir Video",
    calendar: "Calendario",
    schedule: "Programar",
    posts: "Mis Posts",
    config: "Config APIs",
  };
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      document
        .querySelectorAll(".nav-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document
        .querySelectorAll(".tab-content")
        .forEach((t) => t.classList.remove("active"));
      document.getElementById(`tab-${tab}`).classList.add("active");
      document.getElementById("pageTitle").textContent = titles[tab] || tab;
      if (tab === "upload") {
        initUploadBrandSelector();
        loadVideoGallery();
      }
      if (tab === "calendar") loadCalendarTab();
      if (tab === "schedule") loadScheduleTab();
      if (tab === "posts") loadPostsTable();
      if (tab === "config") loadApiStatus();
      if (tab === "dashboard") loadDashboard();
    });
  });

  const activeBtn = document.querySelector(".nav-btn.active");
  if (activeBtn?.dataset?.tab) {
    document.getElementById("pageTitle").textContent =
      titles[activeBtn.dataset.tab] || activeBtn.dataset.tab;
  }
}

function goToTab(tab) {
  document.querySelector(`.nav-btn[data-tab="${tab}"]`)?.click();
}

/* ══════════════════════════════════════════════════════════════
   DASHBOARD
════════════════════════════════════════════════════════════ */
async function loadDashboard() {
  try {
    const data = await get("/api/dashboard");
    document.getElementById("kpi-videos").textContent = data.total_videos;
    document.getElementById("kpi-published").textContent = data.published;
    document.getElementById("kpi-scheduled").textContent = data.scheduled;
    document.getElementById("kpi-failed").textContent = data.failed;
    renderPlatformBars(data.by_platform, data.total_posts);
    renderMiniList("upcomingPosts", data.upcoming, "scheduled");
    renderMiniList("recentPosts", data.recent, "published");
  } catch (e) {
    console.error("Dashboard error:", e);
  }
}

function renderPlatformBars(byPlatform, total) {
  const el = document.getElementById("platformBars");
  const platforms = [
    { key: "tiktok", label: "TikTok", color: "tiktok" },
    { key: "instagram", label: "Instagram", color: "instagram" },
    { key: "facebook", label: "Facebook", color: "facebook" },
  ];
  if (total === 0) {
    el.innerHTML = `<div class="empty-msg">Sin datos aún</div>`;
    return;
  }
  el.innerHTML = platforms
    .map((p) => {
      const count = byPlatform[p.key] || 0;
      const pct = total ? Math.round((count / total) * 100) : 0;
      return `
      <div class="pb-row">
        <div class="pb-label">${p.label}</div>
        <div class="pb-bar-bg"><div class="pb-bar-fill ${p.color}" style="width:${pct}%"></div></div>
        <div class="pb-count">${count}</div>
      </div>`;
    })
    .join("");
}

/* ══════════════════════════════════════════════════════════════
   GLOBAL REFRESH  –  call after any mutating action
   Refreshes dashboard + the currently visible tab + background caches
════════════════════════════════════════════════════════════ */
async function refreshAllData() {
  // 1. Always refresh dashboard KPIs
  try {
    await loadDashboard();
  } catch (e) {
    console.warn("refreshAllData: dashboard", e);
  }

  // 2. Refresh cross-tab caches silently
  try {
    videos = await get("/api/videos");
  } catch (e) {
    /* ok */
  }
  try {
    const posts = await get("/api/posts");
    calendarPosts = posts;
    allVideosCache = videos;
    window._postsTableCache = {};
    posts.forEach((p) => {
      window._postsTableCache[p.id] = p;
    });
  } catch (e) {
    /* ok */
  }

  // 3. Refresh active tab
  const activeTab = document.querySelector(".nav-btn.active")?.dataset?.tab;
  try {
    if (activeTab === "upload") {
      await loadVideoGallery();
      await populateVideoSelect();
    }
    if (activeTab === "calendar") {
      renderCalendarGrid();
    }
    if (activeTab === "schedule") {
      await populateVideoSelect();
      loadSchedulePreview();
    }
    if (activeTab === "posts") {
      await loadPostsTable();
    }
    if (activeTab === "config") {
      loadApiStatus();
    }
  } catch (e) {
    console.warn("refreshAllData: tab", e);
  }
}

function renderMiniList(elId, posts, type) {
  const el = document.getElementById(elId);
  if (!posts.length) {
    el.innerHTML = `<div class="empty-msg">${type === "scheduled" ? "No hay posts programados" : "Aún no has publicado nada"}</div>`;
    return;
  }
  el.innerHTML = posts
    .map(
      (p) => `
    <div class="posts-mini-item">
      <div class="plat-dot ${p.platform}" style="width:10px;height:10px;border-radius:50%;flex-shrink:0;"></div>
      <div class="pmi-title">${truncate(p.title, 32)}</div>
      <div class="pmi-time">${type === "scheduled" ? p.scheduled_at : p.posted_at || ""}</div>
      <span class="badge badge-${p.status}">${statusLabel(p.status)}</span>
    </div>`,
    )
    .join("");
}

/* ══════════════════════════════════════════════════════════════
   UPLOAD TAB  –  multi-file queue
════════════════════════════════════════════════════════════ */

const ALLOWED_EXTS = ["mp4", "mov", "avi", "mkv", "webm"];
const MAX_SIZE_MB = 500;
let uploadQueue = []; // [{id, file, status:'wait'|'uploading'|'done'|'error', pct:0}]
let isUploading = false;

/* ── Upload Brand Selector ─────────────────────────────── */

async function updateUploadCategories(bKey) {
  const select = document.getElementById("uploadCategorySelect");
  if (!select) return;

  if (!window.contentTypesData) {
    try {
      window.contentTypesData = await get("/api/hashtags/content-types");
    } catch (e) {
      window.contentTypesData = [];
    }
  }

  const brand = brandsData.find((b) => b.key === bKey);
  if (brand && brand.categories && brand.categories.length) {
    const options = brand.categories
      .map((c) => {
        const found = window.contentTypesData.find((ct) => ct.key === c);
        const label = found ? found.label : c;
        return `<option value="${c}">${label}</option>`;
      })
      .join("");

    if (bKey === "gymark") {
      select.innerHTML = `<option value="">Auto (detectar con IA)</option>${options}`;
      select.value = "";
    } else {
      select.innerHTML = options;
    }
  } else {
    select.innerHTML = "<option value=''>General</option>";
  }
}

async function initUploadBrandSelector() {
  const container = document.getElementById("uploadBrandBtns");
  if (!container) return;
  // Load brands if not yet loaded
  if (!brandsData.length) {
    try {
      brandsData = await get("/api/brands");
    } catch (e) {
      return;
    }
  }

  if (!brandsData.find((b) => b.key === uploadBrand) && brandsData.length) {
    uploadBrand = brandsData[0].key;
  }

  // Render once (check if already rendered)
  updateUploadCategories(uploadBrand);
  if (container.childElementCount !== brandsData.length) {
    container.innerHTML = brandsData
      .map(
        (b) => `
      <button class="brand-btn${b.key === uploadBrand ? " active" : ""}" data-key="${b.key}"
              style="${b.key === uploadBrand ? "background:" + b.color : ""}">
        <span class="brand-dot" style="background:${b.color}"></span>
        ${b.label}
      </button>`,
      )
      .join("");
    container.querySelectorAll(".brand-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        uploadBrand = btn.dataset.key;
        container.querySelectorAll(".brand-btn").forEach((b) => {
          b.classList.remove("active");
          b.style.background = "";
        });
        const meta = brandsData.find((b) => b.key === uploadBrand);
        btn.classList.add("active");
        btn.style.background = meta.color;
        updateUploadCategories(uploadBrand);
      });
    });
  }
}

function getBrandMeta(key) {
  return brandsData.find((b) => b.key === key) || { color: "#555", label: key };
}

function initUpload() {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("videoFileInput");

  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) =>
    addFilesToQueue([...e.target.files]),
  );

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", () =>
    dropZone.classList.remove("drag-over"),
  );
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    addFilesToQueue([...e.dataTransfer.files]);
  });

  document
    .getElementById("btnUploadAll")
    .addEventListener("click", uploadAllFiles);
  document.getElementById("btnAddMore").addEventListener("click", () => {
    document.getElementById("videoFileInput").value = "";
    document.getElementById("videoFileInput").click();
  });
}

function addFilesToQueue(files) {
  let added = 0;
  for (const file of files) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      toast(
        `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M18 6L6 18M6 6l12 12"/></svg> ${file.name}: formato no permitido`,
        "error",
      );
      continue;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      toast(
        `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M18 6L6 18M6 6l12 12"/></svg> ${file.name}: supera los ${MAX_SIZE_MB} MB`,
        "error",
      );
      continue;
    }
    // evitar duplicados por nombre+tamaño
    if (
      uploadQueue.find(
        (q) => q.file.name === file.name && q.file.size === file.size,
      )
    )
      continue;
    uploadQueue.push({
      id: Date.now() + Math.floor(Math.random() * 1000000),
      file,
      brand: uploadBrand,
      status: "wait",
      pct: 0,
    });
    added++;
  }
  if (added > 0) renderQueue();
}

function renderQueue() {
  const queueEl = document.getElementById("uploadQueue");
  const listEl = document.getElementById("queueList");
  const dropEl = document.getElementById("dropZone");
  const titleEl = document.getElementById("queueTitle");

  if (uploadQueue.length === 0) {
    queueEl.classList.add("hidden");
    dropEl.classList.remove("hidden");
    return;
  }

  dropEl.classList.add("hidden");
  queueEl.classList.remove("hidden");

  const waiting = uploadQueue.filter((q) => q.status === "wait").length;
  titleEl.textContent = `${uploadQueue.length} video${uploadQueue.length > 1 ? "s" : ""} · ${waiting} pendiente${waiting !== 1 ? "s" : ""}`;

  listEl.innerHTML = uploadQueue
    .map((item) => {
      const statusMap = {
        wait: { cls: "wait", label: "En espera" },
        uploading: { cls: "uploading", label: "Subiendo..." },
        done: {
          cls: "done",
          label: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M20 6L9 17l-5-5"/></svg> Listo`,
        },
        error: { cls: "error", label: "⚠️ Error" },
      };
      const st = statusMap[item.status] || statusMap.wait;
      return `
      <div class="queue-item ${item.status === "done" ? "done" : item.status === "error" ? "error" : item.status === "uploading" ? "active" : ""}" id="qi-${item.id}">
        <div class="qi-thumb"><svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect width="20" height="15" x="2" y="7" rx="2" ry="2"/><polyline points="17 2 12 7 7 2"/></svg></div>
        <div class="qi-info">
          <div class="qi-name">${item.file.name}</div>
          <div class="qi-meta">${formatBytes(item.file.size)} &nbsp;<span class="vbrand-badge" style="background:${getBrandMeta(item.brand).color}">${getBrandMeta(item.brand).label}</span></div>
          <div class="qi-progress">
            <div class="qi-progress-fill" style="width:${item.pct}%"></div>
          </div>
        </div>
        <div class="qi-status ${st.cls}">${st.label}</div>
        ${item.status === "wait" ? `<button class="qi-remove" data-id="${item.id}" title="Quitar">✕</button>` : "<span style='width:24px'></span>"}
      </div>`;
    })
    .join("");

  // Quitar de la cola
  listEl.querySelectorAll(".qi-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      uploadQueue = uploadQueue.filter((q) => q.id != btn.dataset.id);
      renderQueue();
    });
  });

  // Botón Subir Todos
  const btnAll = document.getElementById("btnUploadAll");
  const anyWaiting = uploadQueue.some((q) => q.status === "wait");
  btnAll.disabled = isUploading || !anyWaiting;
  btnAll.textContent = isUploading
    ? "Subiendo..."
    : `⬆ Subir ${waiting > 0 ? waiting : ""} Video${waiting !== 1 ? "s" : ""}`;
}

async function uploadAllFiles() {
  if (isUploading) return;
  const pending = uploadQueue.filter((q) => q.status === "wait");
  if (!pending.length) return;

  isUploading = true;
  renderQueue();

  const progressFill = document.getElementById("progressFill");
  const progressLabel = document.getElementById("progressLabel");
  let done = 0;

  for (const item of pending) {
    item.status = "uploading";
    item.pct = 0;
    renderQueue();

    try {
      const catId = document.getElementById("uploadCategorySelect").value;
      const result = await uploadOneFile(
        item.file,
        item.brand,
        catId,
        (pct) => {
          if (pct === 100) {
            const stEl = document.querySelector(`#qi-${item.id} .qi-status`);
            if (stEl) stEl.textContent = "Generando IA...";
          }
          item.pct = pct;
          // Update individual bar
          const fill = document.querySelector(
            `#qi-${item.id} .qi-progress-fill`,
          );
          if (fill) fill.style.width = pct + "%";
          const stEl = document.querySelector(`#qi-${item.id} .qi-status`);
          if (stEl) stEl.textContent = `${pct}%`;
          // Global bar
          const globalPct = Math.round(
            ((done + pct / 100) / pending.length) * 100,
          );
          progressFill.style.width = globalPct + "%";
          progressLabel.textContent = `Subiendo "${item.file.name}" · ${pct}%`;
        },
      );
      let aiResult = null;

      try {
        const aiStEl = document.querySelector(`#qi-${item.id} .qi-status`);
        if (aiStEl) aiStEl.textContent = "Procesando con Gemini 2.5 Pro...";
        progressLabel.textContent = `Procesando "${item.file.name}" con Gemini 2.5 Pro...`;
        aiResult = await generateAIWithRetry(
          {
            video_id: result.id,
            brand: item.brand,
            category_id: catId,
          },
          ({ attempt, waitSeconds, model, phase, queued }) => {
            if (aiStEl) {
              if (queued && waitSeconds > 0) {
                aiStEl.textContent = `IA en cola (${attempt}) · esperando ${waitSeconds}s`;
              } else if (model) {
                aiStEl.textContent = `Procesando con ${model}...`;
              } else if (phase === "queued") {
                aiStEl.textContent = "Preparando IA...";
              }
            }
            if (queued && waitSeconds > 0) {
              progressLabel.textContent = `Esperando IA para "${item.file.name}" · ${waitSeconds}s`;
            } else if (model) {
              progressLabel.textContent = `Procesando "${item.file.name}" con ${model}...`;
            } else {
              progressLabel.textContent = `Preparando IA para "${item.file.name}"...`;
            }
          },
        );
        if (aiStEl)
          aiStEl.textContent = aiResult?.model_used
            ? `Listo · ${aiResult.model_used}`
            : "Listo";
      } catch (e) {
        console.error("Error de IA:", e);
        try {
          await del(`/api/videos/${result.id}`);
        } catch (cleanupErr) {
          console.error("No se pudo limpiar video sin IA:", cleanupErr);
        }
        throw {
          error:
            (e && e.error
              ? `IA no disponible: ${e.error}`
              : "IA no disponible") +
            ". El video fue removido para no dejar contenido sin IA.",
        };
      }

      item.status = "done";
      item.pct = 100;
      done++;
      const displayName =
        String(aiResult?.titulo || "").trim() || getVideoDisplayName(result);
      toast(
        `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M20 6L9 17l-5-5"/></svg> "${displayName}" subido y procesado por IA (${result.file_size_mb} MB)`,
        "success",
      );
    } catch (err) {
      item.status = "error";
      toast(
        `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M18 6L6 18M6 6l12 12"/></svg> Error subiendo "${item.file.name}": ${err.error || "error desconocido"}`,
        "error",
      );
    }
    renderQueue();
  }

  progressFill.style.width = "100%";
  progressLabel.innerHTML = `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M20 6L9 17l-5-5"/></svg> ${done} de ${pending.length} video${pending.length > 1 ? "s" : ""} subidos`;
  isUploading = false;
  renderQueue();
  await refreshAllData();

  // Limpiar los exitosos después de 3s
  setTimeout(() => {
    uploadQueue = uploadQueue.filter((q) => q.status !== "done");
    if (uploadQueue.length === 0) {
      document.getElementById("uploadQueue").classList.add("hidden");
      document.getElementById("dropZone").classList.remove("hidden");
      progressFill.style.width = "0%";
      progressLabel.textContent = "";
    } else {
      renderQueue();
    }
  }, 3000);
}

function uploadOneFile(file, brand, category_id, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("video", file);
    formData.append("brand", brand);
    formData.append("category_id", category_id);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/videos/upload");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      const data = JSON.parse(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(data);
    };
    xhr.onerror = () => reject({ error: "Sin conexión" });
    xhr.send(formData);
  });
}

function parseRetryAfterSeconds(aiError) {
  if (aiError && Number.isFinite(Number(aiError.retry_after))) {
    return Math.max(3, Math.ceil(Number(aiError.retry_after)));
  }

  const raw = String((aiError && aiError.error) || "");
  let match = raw.match(/retry_delay\s*\{\s*seconds:\s*(\d+)/i);
  if (!match) match = raw.match(/retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s/i);
  if (!match)
    match = raw.match(/please\s+retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s/i);

  if (match) {
    return Math.max(3, Math.ceil(Number(match[1])));
  }
  return 12;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildAIRequestId() {
  return `ai-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

async function generateAIWithRetry(payload, onWait) {
  let attempt = 1;

  while (true) {
    const requestId = buildAIRequestId();
    let pollTimer = null;
    try {
      if (typeof onWait === "function") {
        onWait({
          attempt,
          waitSeconds: 0,
          model: null,
          phase: "queued",
          queued: true,
        });
      }

      pollTimer = setInterval(async () => {
        try {
          const status = await get(`/api/ai/status/${requestId}`);
          if (typeof onWait === "function") {
            onWait({
              attempt,
              waitSeconds: 0,
              model: status?.model || null,
              phase: status?.phase || null,
              queued: false,
            });
          }
        } catch (e) {
          /* ignore polling errors */
        }
      }, 1200);

      const result = await post("/api/ai/generate", {
        ...payload,
        request_id: requestId,
      });
      if (pollTimer) clearInterval(pollTimer);
      return result;
    } catch (err) {
      if (pollTimer) clearInterval(pollTimer);
      const is429 =
        (err && err._status === 429) ||
        /\b429\b/.test(String(err?.error || ""));
      if (!is429) throw err;

      const waitSeconds = parseRetryAfterSeconds(err);
      if (typeof onWait === "function") {
        onWait({
          attempt,
          waitSeconds,
          error: err,
          model: null,
          phase: "quota",
          queued: true,
        });
      }
      await sleep(waitSeconds * 1000);
      attempt += 1;
    }
  }
}

async function loadVideoGallery() {
  const gallery = document.getElementById("videoGallery");
  try {
    if (!brandsData.length) {
      brandsData = await get("/api/brands");
    }

    videos = await get("/api/videos");
    if (!videos.length) {
      gallery.innerHTML = `<div class="empty-msg">No has subido videos aún</div>`;
      return;
    }

    gallery.innerHTML = videos
      .map((v) => {
        const bm = getBrandMeta(v.brand);
        const canSwitchAccount = brandsData.length > 1;
        const brandOptions = brandsData
          .map(
            (b) =>
              `<option value="${b.key}" ${b.key === v.brand ? "selected" : ""}>${b.label}</option>`,
          )
          .join("");
        return `
      <div class="video-card" data-id="${v.id}">
        <div class="video-card__thumb">
          ${
            v.thumbnail
              ? `<img src="${v.thumbnail}" alt="" onerror="this.parentElement.textContent='\uD83C\uDFAC'">`
              : `\uD83C\uDFAC`
          }
        </div>
        <div class="video-card__info">
          <div class="video-card__name">${getVideoDisplayName(v)}</div>
          <div class="video-card__meta">${v.file_size_mb} MB \u00b7 ${v.duration ? v.duration + "s" : "\u2013"}</div>
          <div style="display:flex;align-items:center;gap:6px;margin-top:4px;">
            <span class="vbrand-badge" style="background:${bm.color}">${bm.label}</span>
            <span class="video-card__meta">${v.uploaded_at}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;margin-top:8px;">
            <select class="form-input video-card__brand-select" data-id="${v.id}" style="max-width:190px;height:34px;padding:6px 10px;" ${canSwitchAccount ? "" : "disabled"}>
              ${brandOptions}
            </select>
            ${canSwitchAccount ? `<button class="btn btn-sm btn-ghost video-card__account-apply" data-id="${v.id}">Cambiar cuenta + IA</button>` : ""}
          </div>
        </div>
        <button class="video-card__del btn btn-sm btn-red" data-id="${v.id}">✕</button>
      </div>`;
      })
      .join("");

    gallery.querySelectorAll(".video-card__del").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteVideo(btn.dataset.id);
      });
    });

    gallery.querySelectorAll(".video-card__account-apply").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        changeVideoAccountAndRegenerateAI(btn.dataset.id);
      });
    });
  } catch (e) {
    gallery.innerHTML = `<div class="empty-msg">Error cargando videos</div>`;
  }
}

async function deleteVideo(id) {
  if (
    !confirm(
      "¿Eliminar este video? También se cancelarán sus posts programados.",
    )
  )
    return;
  try {
    await del(`/api/videos/${id}`);
    toast("Video eliminado", "info");
    await refreshAllData();
  } catch (e) {
    toast("Error al eliminar", "error");
  }
}

async function changeVideoAccountAndRegenerateAI(videoId) {
  const selector = document.querySelector(
    `.video-card__brand-select[data-id="${videoId}"]`,
  );
  const newBrand = selector?.value;
  const video = videos.find((v) => String(v.id) === String(videoId));

  if (!newBrand || !video) {
    toast("No se pudo identificar la cuenta para actualizar", "error");
    return;
  }

  if (newBrand === video.brand) {
    toast("Ese video ya está en esa cuenta", "info");
    return;
  }

  if (
    !confirm("¿Cambiar la cuenta de este video y regenerar metadata con IA?")
  ) {
    return;
  }

  const btn = document.querySelector(
    `.video-card__account-apply[data-id="${videoId}"]`,
  );
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Regenerando...";
  }

  try {
    const categoryForAI = newBrand === "gymark" ? "" : "gaming";
    await generateAIWithRetry({
      video_id: Number(videoId),
      brand: newBrand,
      category_id: categoryForAI,
    });

    toast("Cuenta actualizada y metadata IA regenerada", "success");
    await refreshAllData();
  } catch (e) {
    toast(
      `No se pudo actualizar la cuenta: ${e?.error || "error desconocido"}`,
      "error",
    );
    if (selector) selector.value = video.brand;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Cambiar cuenta + IA";
    }
  }
}

/* ══════════════════════════════════════════════════════════════
   SCHEDULE TAB
════════════════════════════════════════════════════════════ */
async function loadScheduleTab() {
  await loadBrands();
  await populateVideoSelect();
  await loadContentTypes();

  loadSchedulePreview();
  renderBestTimesReference();

  // Listeners (only once)
  const videoList = document.getElementById("schedVideoList");
  const selectAllBtn = document.getElementById("btnSelectAllVideos");
  if (!videoList._initDone) {
    videoList.addEventListener("change", () => {
      onVideoSelectChange();
      updateSelectAllButtonState();
    });

    if (selectAllBtn) {
      selectAllBtn.addEventListener("click", () => {
        toggleSelectAllVideos();
      });
    }

    const ctSelect = document.getElementById("contentTypeSelect");
    if (ctSelect) {
      ctSelect.addEventListener("change", () => {
        // Reset AI indicator when user manually changes category
        ctSelect.style.borderColor = "";
        ctSelect.title = "";
        loadSchedulePreview();
        renderBestTimesReference();
      });
    }
    // hashtags listeners removed

    const btnAIGen = document.getElementById("btnAIGenerate");
    if (btnAIGen) {
      btnAIGen.addEventListener("click", handleAIGenerate);
    }

    const btnSched = document.getElementById("btnSchedule");
    if (btnSched) {
      btnSched.addEventListener("click", submitSchedule);
    }
    document.querySelectorAll(".plat-check input").forEach((cb) => {
      cb.addEventListener("change", () => {
        loadSchedulePreview();
        renderBestTimesReference();
      });
    });
    document.querySelectorAll(".toggle-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document
          .querySelectorAll(".toggle-btn")
          .forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        scheduleMode = btn.dataset.mode;
        document
          .getElementById("manualDateWrap")
          .classList.toggle("hidden", scheduleMode !== "manual");
      });
    });
    videoList._initDone = true;
  }

  updateSelectAllButtonState();
}

/* ── Brand Selector ──────────────────────────────────────── */
async function loadBrands() {
  const container = document.getElementById("brandSelector");
  if (!container) return;
  try {
    brandsData = await get("/api/brands");
    if (!brandsData.length) {
      container.innerHTML = `<div class="empty-msg">No hay cuentas disponibles</div>`;
      return;
    }

    if (!brandsData.find((b) => b.key === currentBrand)) {
      currentBrand = brandsData[0].key;
    }

    container.innerHTML = brandsData
      .map(
        (b) => `
      <button class="brand-btn${b.key === currentBrand ? " active" : ""}" data-key="${b.key}"
              style="${b.key === currentBrand ? "background:" + b.color : ""}">
        <span class="brand-dot" style="background:${b.color}"></span>
        ${b.label}
      </button>`,
      )
      .join("");
    container.querySelectorAll(".brand-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        currentBrand = btn.dataset.key;
        container.querySelectorAll(".brand-btn").forEach((b) => {
          b.classList.remove("active");
          b.style.background = "";
        });
        const brand = brandsData.find((b) => b.key === currentBrand);
        btn.classList.add("active");
        btn.style.background = brand.color;
        filterPlatformsForBrand(brand);
        filterContentTypesForBrand(brand);
        populateVideoSelect();

        loadSchedulePreview();
        renderBestTimesReference();
      });
    });
    // Apply initial filter
    const activeBrand = brandsData.find((b) => b.key === currentBrand);
    if (activeBrand) {
      filterPlatformsForBrand(activeBrand);
      filterContentTypesForBrand(activeBrand);
    }
    renderBestTimesReference();
  } catch (e) {
    console.error("loadBrands error:", e);
  }
}

function renderBestTimesReference() {
  const wrap = document.getElementById("bestTimesReference");
  if (!wrap) return;

  const contentType =
    document.getElementById("contentTypeSelect")?.value || "acc_gimnasio";
  const categoryMap =
    PERFECT_WINDOWS[contentType] || PERFECT_WINDOWS.acc_gimnasio;

  const brandMeta = brandsData.find((b) => b.key === currentBrand);
  const allowedPlatforms = brandMeta?.platforms?.length
    ? brandMeta.platforms
    : ["tiktok", "instagram", "facebook"];

  wrap.innerHTML = allowedPlatforms
    .filter((p) => categoryMap[p])
    .map(
      (p) => `
      <div class="best-times-platform">
        <div class="btp-header ${
          p === "instagram"
            ? "insta-color"
            : p === "facebook"
              ? "fb-color"
              : "tiktok-color"
        }">${platformLabel(p)}</div>
        <div class="btp-times">${categoryMap[p]}</div>
      </div>`,
    )
    .join("");
}

function filterPlatformsForBrand(brand) {
  const wrap = document.getElementById("platformChecks");
  if (!wrap) return;
  wrap.querySelectorAll(".plat-check").forEach((row) => {
    const input = row.querySelector("input");
    const plat = input?.value;
    if (brand.platforms.includes(plat)) {
      row.classList.remove("hidden");
    } else {
      row.classList.add("hidden");
      if (input) input.checked = false;
    }
  });
  // auto-check gymark default platforms
  wrap.querySelectorAll(".plat-check:not(.hidden) input").forEach((i) => {
    i.checked = true;
  });
}

function filterContentTypesForBrand(brand) {
  const sel = document.getElementById("contentTypeSelect");
  if (!sel) return;
  [...sel.options].forEach((opt) => {
    opt.hidden = !brand.categories.includes(opt.value);
  });
  // select first visible option
  const firstVisible = [...sel.options].find((o) => !o.hidden);
  if (firstVisible) sel.value = firstVisible.value;
}

async function populateVideoSelect() {
  const list = document.getElementById("schedVideoList");
  if (!list) return;
  try {
    videos = await get("/api/videos");
    const filtered = videos.filter(
      (v) => v.brand === currentBrand && (!v.posts || v.posts.length === 0),
    );
    if (filtered.length) {
      list.innerHTML = filtered
        .map(
          (v) =>
            `<label class="video-list-item">
                <input type="checkbox" class="sched-video-checkbox" value="${v.id}" />
                <span class="video-list-main">
                  ${v.thumbnail ? `<img src="${v.thumbnail}" class="video-list-thumb" />` : `<div class="video-list-placeholder"></div>`}
                  <div class="video-list-text">
                      <div class="video-list-name">${getVideoDisplayName(v)}</div>
                      <div class="video-list-meta">${v.file_size_mb} MB ${v.ai_title ? "· ✅ IA lista" : "· ⚠️ Sin IA"}</div>
                  </div>
                </span>
              </label>`,
        )
        .join("");
    } else {
      list.innerHTML = `<div class="empty-msg">– No hay videos para esta cuenta –</div>`;
    }
    updateSelectAllButtonState();
  } catch (e) {}
}

function getScheduleCheckboxes() {
  return Array.from(document.querySelectorAll(".sched-video-checkbox"));
}

function updateSelectAllButtonState() {
  const btn = document.getElementById("btnSelectAllVideos");
  if (!btn) return;

  const allChecks = getScheduleCheckboxes();
  if (!allChecks.length) {
    btn.disabled = true;
    btn.textContent = "Seleccionar todos";
    return;
  }

  btn.disabled = false;
  const selectedCount = allChecks.filter((cb) => cb.checked).length;
  const allSelected = selectedCount === allChecks.length;
  btn.textContent = allSelected ? "Deseleccionar todos" : "Seleccionar todos";
}

function toggleSelectAllVideos() {
  const allChecks = getScheduleCheckboxes();
  if (!allChecks.length) return;

  const allSelected = allChecks.every((cb) => cb.checked);
  allChecks.forEach((cb) => {
    cb.checked = !allSelected;
  });

  onVideoSelectChange();
  updateSelectAllButtonState();
}

async function loadContentTypes() {
  const sel = document.getElementById("contentTypeSelect");
  if (!sel) return;
  try {
    const types = await get("/api/hashtags/content-types");
    sel.innerHTML = types
      .map((t) => `<option value="${t.key}">${t.label}</option>`)
      .join("");
    const activeBrand = brandsData.find((b) => b.key === currentBrand);
    if (activeBrand) filterContentTypesForBrand(activeBrand);
  } catch (e) {
    sel.innerHTML = `<option value="">Error al cargar</option>`;
  }
}

function getSelectedPlatforms() {
  return Array.from(
    document.querySelectorAll("#platformChecks input:checked"),
  ).map((i) => i.value);
}

function onVideoSelectChange() {
  const checkboxes = document.querySelectorAll(".sched-video-checkbox:checked");
  if (checkboxes.length === 0) {
    document.getElementById("schedPreviewVideo").classList.add("hidden");
    document.getElementById("previewPlaceholder").classList.remove("hidden");
    return;
  }

  // Show preview of the first checked video
  const id = checkboxes[0].value;
  const video = videos.find((v) => v.id == id);
  const previewEl = document.getElementById("schedPreviewVideo");
  const placeholder = document.getElementById("previewPlaceholder");
  const metaEl = document.getElementById("previewMeta");

  if (video) {
    previewEl.src = `/static/uploads/${video.filename}`;
    previewEl.classList.remove("hidden");
    placeholder.classList.add("hidden");
    if (metaEl)
      metaEl.textContent =
        `${getVideoDisplayName(video)} · ${video.file_size_mb} MB` +
        (video.duration ? ` · ${video.duration}s` : "");

    // Auto-select AI-detected category for Gymark videos
    const ctSelect = document.getElementById("contentTypeSelect");
    if (ctSelect && video.category_id) {
      const opt = [...ctSelect.options].find(
        (o) => o.value === video.category_id && !o.hidden,
      );
      if (opt) {
        ctSelect.value = video.category_id;
        // Visual indicator that the category was set by AI
        ctSelect.title = `Categoría detectada por IA: ${video.category_id}`;
        ctSelect.style.borderColor = "#6c63ff";
      }
    }

    loadSchedulePreview();
    renderBestTimesReference();
  }
}

async function handleAIGenerate() {
  // No longer needed from UI, but keep empty so event listeners don't break.
}

function loadSchedulePreview() {
  const previewEl = document.getElementById("schedulePreviewContent");
  if (!previewEl) return;

  const checkboxes = document.querySelectorAll(".sched-video-checkbox:checked");
  if (checkboxes.length === 0) {
    previewEl.innerHTML =
      '<div style="padding:15px; color:#888;">Selecciona un video para la vista previa</div>';
    return;
  }

  const id = checkboxes[0].value;
  const video = videos.find((v) => v.id == id);
  if (!video) return;

  const titleText = getVideoDisplayName(video);
  const descText = video.ai_description || "";

  let html = `<div style="font-size:14px; font-weight:bold; margin-bottom:5px;">${titleText}</div>`;
  if (descText)
    html += `<div style="font-size:13px; color:#ddd; margin-bottom:5px;">${descText}</div>`;
  html += `<div style="font-size:12px; color:#00f2fe; margin-bottom:5px;">Hashtags fijos por cuenta/categoría se aplicarán al programar</div>`;

  if (checkboxes.length > 1) {
    html += `<div style="font-size:12px; color:#ff0050; margin-top:10px; font-style:italic;">Y ${checkboxes.length - 1} video(s) más seleccionados</div>`;
  }

  previewEl.innerHTML = html;
}

async function submitSchedule() {
  const checkboxes = document.querySelectorAll(".sched-video-checkbox:checked");
  const ctSel = document.getElementById("contentTypeSelect");
  // fallback: pick first visible option if value is somehow empty
  let contentType = ctSel?.value || "";
  if (!contentType) {
    const firstVisible = ctSel
      ? [...ctSel.options].find((o) => !o.hidden && o.value)
      : null;
    if (firstVisible) {
      contentType = firstVisible.value;
      ctSel.value = firstVisible.value;
    }
  }
  const platforms = getSelectedPlatforms();

  if (checkboxes.length === 0) {
    toast("Selecciona al menos un video", "error");
    return;
  }
  if (!platforms.length) {
    toast("Elige al menos una plataforma", "error");
    return;
  }

  const btn = document.getElementById("btnSchedule");
  btn.disabled = true;
  btn.innerHTML = `Programando...`;

  let successCount = 0;

  for (const box of checkboxes) {
    const videoId = box.value;
    const video = videos.find((v) => v.id == videoId);
    if (!video) continue;

    const payload = {
      video_id: parseInt(videoId),
      brand: currentBrand,
      platforms,
      content_type: contentType,
      title: getVideoDisplayName(video),
      description: video.ai_description || "",
      schedule_mode: scheduleMode,
    };

    if (scheduleMode === "manual") {
      const dateVal = document.getElementById("postDate").value;
      const timeVal = document.getElementById("postTime").value;
      if (!dateVal || !timeVal) {
        toast(
          "Ingresa fecha y hora para programar " + getVideoDisplayName(video),
          "error",
        );
        continue; // Skip this one, or just stop
      }
      payload.post_date = `${dateVal}T${timeVal}:00`;
    }

    try {
      await post("/api/posts/schedule", payload);
      successCount++;
    } catch (e) {
      toast(
        `Error con ${getVideoDisplayName(video)}: ${e.error || JSON.stringify(e)}`,
        "error",
      );
    }
  }

  // Finish
  if (successCount > 0) {
    toast(`${successCount} video(s) programado(s) con éxito`, "success");
    document
      .querySelectorAll(".sched-video-checkbox")
      .forEach((cb) => (cb.checked = false));
    await refreshAllData();
    loadSchedulePreview();
  }

  btn.disabled = false;
  btn.innerHTML = `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg> Programar Post`;
}

/* ══════════════════════════════════════════════════════════════
     POSTS TABLE
  ════════════════════════════════════════════════════════════ */
function initPostsFilter() {
  document.querySelectorAll(".filter-btn[data-status]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document
        .querySelectorAll(".filter-btn[data-status]")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.status;
      loadPostsTable();
    });
  });

  const btnClear = document.getElementById("btnClearAllPosts");
  if (btnClear) {
    btnClear.addEventListener("click", async () => {
      if (
        !confirm(
          "¿Seguro que quieres eliminar TODOS los posts del calendario? Esta acción no se puede deshacer.",
        )
      )
        return;
      try {
        const res = await del("/api/posts/clear");
        toast(
          `Calendario limpiado: ${res.deleted} posts eliminados`,
          "success",
        );
        await refreshAllData();
      } catch (e) {
        toast("Error al limpiar el calendario", "error");
      }
    });
  }
}

async function loadPostsTable() {
  const tbody = document.getElementById("postsTableBody");
  try {
    const params = currentFilter !== "all" ? `?status=${currentFilter}` : "";
    const posts = await get(`/api/posts${params}`);

    if (!posts.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty-msg">No hay posts con este filtro</td></tr>`;
      return;
    }

    // Store posts for modal access
    window._postsTableCache = {};
    posts.forEach((p) => {
      window._postsTableCache[p.id] = p;
    });

    tbody.innerHTML = posts
      .map((p) => {
        const videoRef = videos.find((v) => v.id === p.video_id);
        const vidName = videoRef
          ? getVideoDisplayName(videoRef)
          : `Video #${p.video_id}`;
        return `
        <tr>
          <td data-label="Video">${truncate(vidName, 22)}</td>
          <td data-label="Plataforma"><div class="plat-icon"><span class="plat-dot ${p.platform}"></span>${platformLabel(p.platform)}</div></td>
          <td data-label="Título">${truncate(p.title, 28)}</td>
          <td data-label="Tipo">${contentTypeLabel(p.content_type)}</td>
          <td data-label="Programado">${p.scheduled_at}</td>
          <td data-label="Estado"><span class="badge badge-${p.status}">${statusLabel(p.status)}</span></td>
          <td data-label="Acciones" style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="btn btn-sm btn-ghost" onclick="openPostDetailFromTable(${p.id})">👁 Ver</button>
            ${p.status === "scheduled" ? `<button class="btn btn-sm btn-ghost" onclick="publishNow(${p.id})">▶ Ahora</button>` : ""}
            ${["scheduled", "failed"].includes(p.status) ? `<button class="btn btn-sm btn-red" onclick="cancelPost(${p.id})">✕</button>` : ""}
          </td>
        </tr>`;
      })
      .join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-msg">Error cargando posts</td></tr>`;
  }
}

function openPostDetailFromTable(postId) {
  const p = window._postsTableCache?.[postId];
  if (!p) return;
  openCalendarPostModal(p);
}

async function publishNow(id) {
  if (!confirm("¿Publicar este post ahora mismo?")) return;
  try {
    await post(`/api/posts/${id}/publish-now`, {});
    toast("Post enviado a publicar", "success");
    await refreshAllData();
  } catch (e) {
    toast("Error al publicar", "error");
  }
}

async function cancelPost(id) {
  if (!confirm("¿Cancelar este post?")) return;
  try {
    await del(`/api/posts/${id}`);
    toast("Post cancelado", "info");
    await refreshAllData();
  } catch (e) {
    toast("Error al cancelar", "error");
  }
}

/* ══════════════════════════════════════════════════════════════
   API STATUS
════════════════════════════════════════════════════════════ */
async function loadApiStatus() {
  try {
    const data = await get("/api/config/status");
    // Side-bar chips (legacy flat fields)
    ["tiktok", "instagram", "facebook"].forEach((p) => {
      const chip = document.getElementById(`chip-${p}`);
      if (data[p]) {
        chip?.classList.add("connected");
        chip?.classList.remove("demo");
      } else {
        chip?.classList.add("demo");
        chip?.classList.remove("connected");
      }
    });
    // Config tab per-brand badges
    if (data.brands) {
      Object.entries(data.brands).forEach(([brand, plats]) => {
        Object.entries(plats).forEach(([plat, connected]) => {
          const badge = document.getElementById(`cfg-${brand}-${plat}`);
          if (!badge) return;
          if (connected) {
            badge.textContent = "Conectado";
            badge.classList.add("connected");
          } else {
            badge.textContent = "Demo";
            badge.classList.remove("connected");
          }
        });
      });
    }
  } catch (e) {}
}

/* ══════════════════════════════════════════════════════════════
   HTTP HELPERS
════════════════════════════════════════════════════════════ */
async function get(url) {
  const r = await fetch(API + url);
  if (!r.ok) {
    let err;
    try {
      err = await r.json();
    } catch (e) {
      err = { error: `HTTP ${r.status}` };
    }
    err._status = r.status;
    throw err;
  }
  return r.json();
}
async function post(url, body) {
  const r = await fetch(API + url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let err;
    try {
      err = await r.json();
    } catch (e) {
      err = { error: `HTTP ${r.status}` };
    }
    err._status = r.status;
    throw err;
  }
  return r.json();
}
async function del(url) {
  const r = await fetch(API + url, { method: "DELETE" });
  if (!r.ok) {
    let err;
    try {
      err = await r.json();
    } catch (e) {
      err = { error: `HTTP ${r.status}` };
    }
    err._status = r.status;
    throw err;
  }
  return r.json();
}

/* ══════════════════════════════════════════════════════════════
   TOAST
════════════════════════════════════════════════════════════ */
function toast(msg, type = "info") {
  const container = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = msg;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add("fade-out");
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

/* ══════════════════════════════════════════════════════════════
   UTILS
════════════════════════════════════════════════════════════ */
function truncate(s, n) {
  return s && s.length > n ? s.slice(0, n) + "…" : s || "";
}

function getVideoDisplayName(video) {
  const aiTitle = String(video?.ai_title || "").trim();
  if (aiTitle) return aiTitle;

  const originalName = String(video?.original_name || "").trim();
  if (!originalName) {
    return video?.id ? `Video #${video.id}` : "Video";
  }
  return originalName.replace(/\.[^/.]+$/, "") || originalName;
}

function isMobileViewport() {
  return window.matchMedia("(max-width: 768px)").matches;
}

function isSmallMobileViewport() {
  return window.matchMedia("(max-width: 480px)").matches;
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function platformLabel(p) {
  return (
    { tiktok: "TikTok", instagram: "Instagram", facebook: "Facebook" }[p] || p
  );
}

function contentTypeLabel(key) {
  const map = {
    gaming: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><line x1="6" x2="10" y1="12" y2="12"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="15" x2="15.01" y1="13" y2="13"/><line x1="18" x2="18.01" y1="11" y2="11"/><rect width="20" height="12" x="2" y="6" rx="2"/></svg> Gaming`,
    acc_gimnasio: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M6.5 6.5h11"/><path d="M6.5 17.5h11"/><path d="m12 6.5 4 11"/><path d="m12 6.5-4 11"/></svg> Acc. Gym`,
    pilates_yoga: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><circle cx="12" cy="6" r="2"/><path d="M10.1 11.23a2 2 0 0 1 3.8 0l1.3 4.4a2 2 0 0 1-2.5 2.5l-1.3-.4-1.3.4a2 2 0 0 1-2.5-2.5z"/></svg> Pilates`,
    sup_naturales: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg> Sup. Nat.`,
    ropa_deportiva: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M20.38 3.46 16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/></svg> Ropa`,
    sup_deportivos: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M12 4c.6 0 1.9 1 3 2.5s2 3.5 2 5v2s-1 1-1 3-1 2-2 2h-3v-2"/><path d="M12 4V2"/><path d="m12 6-2 1M12 4H8"/></svg> Sup. Dep.`,
    home_gym: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg> Home Gym`,
  };
  return map[key] || key;
}

function statusLabel(s) {
  return (
    {
      scheduled: "Programado",
      posting: "Publicando…",
      published: "Publicado",
      failed: "Fallido",
      cancelled: "Cancelado",
    }[s] || s
  );
}

/* ══════════════════════════════════════════════════════════════
   CALENDAR LOGIC (ADDED)
════════════════════════════════════════════════════════════ */
let calendarDate = new Date();
let calendarPosts = [];
let allVideosCache = [];
let calendarFilter = "all";
let calendarView = "month"; // "month", "week", "day"
let calendarFeedInfoCache = null;

function initCalendar() {
  document
    .getElementById("prevMonth")
    ?.addEventListener("click", () => changeDate(-1));
  document
    .getElementById("nextMonth")
    ?.addEventListener("click", () => changeDate(1));

  document
    .getElementById("goToday")
    ?.addEventListener("click", () => goToToday());

  document
    .getElementById("copyCalendarFeed")
    ?.addEventListener("click", copyCalendarFeed);

  document.querySelectorAll(".cal-filters .filter-chip").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      document
        .querySelectorAll(".cal-filters .filter-chip")
        .forEach((b) => b.classList.remove("active"));
      e.currentTarget.classList.add("active");
      calendarFilter = e.currentTarget.dataset.filter;
      renderCalendarGrid();
    });
  });

  document.querySelectorAll(".cal-views .view-chip").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      setCalendarView(e.currentTarget.dataset.view);
    });
  });

  if (isMobileViewport()) {
    setCalendarView(isSmallMobileViewport() ? "day" : "week");
  }

  const modalOverlay = document.getElementById("modalOverlay");
  const modalClose = document.getElementById("modalClose");
  modalClose?.addEventListener("click", closeCalendarPostModal);
  modalOverlay?.addEventListener("click", (e) => {
    if (e.target === modalOverlay) closeCalendarPostModal();
  });

  document.addEventListener("keydown", handleCalendarShortcuts);
}

function setCalendarView(view) {
  calendarView = view;
  document
    .querySelectorAll(".cal-views .view-chip")
    .forEach((b) => b.classList.remove("active"));
  const btn = document.querySelector(
    `.cal-views .view-chip[data-view="${view}"]`,
  );
  if (btn) btn.classList.add("active");
  renderCalendarGrid();
}

function handleCalendarShortcuts(e) {
  const activeTab = document.querySelector(".nav-btn.active")?.dataset?.tab;
  if (activeTab !== "calendar") return;

  const tag = document.activeElement?.tagName;
  const isTyping =
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    document.activeElement?.isContentEditable;
  if (isTyping) return;

  const key = e.key.toLowerCase();
  if (key === "j" || e.key === "ArrowRight") {
    e.preventDefault();
    changeDate(1);
  } else if (key === "k" || e.key === "ArrowLeft") {
    e.preventDefault();
    changeDate(-1);
  } else if (key === "t") {
    e.preventDefault();
    goToToday();
  } else if (key === "m") {
    e.preventDefault();
    setCalendarView("month");
  } else if (key === "w") {
    e.preventDefault();
    setCalendarView("week");
  } else if (key === "d") {
    e.preventDefault();
    setCalendarView("day");
  } else if (key === "?") {
    e.preventDefault();
    toast("Atajos: →/← mover · T hoy · M mes · W semana · D día", "info");
  }
}

function goToToday() {
  calendarDate = new Date();
  renderCalendarGrid();
}

function formatDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function copyCalendarFeed() {
  const run = async () => {
    calendarFeedInfoCache = await get("/api/calendar/feed-info");

    const feedUrl = calendarFeedInfoCache.feed_url;
    const webcalUrl =
      calendarFeedInfoCache.webcal_url ||
      feedUrl.replace(/^https?:\/\//, "webcal://");
    const googleUrl =
      calendarFeedInfoCache.google_subscribe_url ||
      "https://calendar.google.com/calendar/r/settings/addbyurl";

    await navigator.clipboard?.writeText(webcalUrl);
    toast("Link del calendario copiado ✓", "success");
    window.open(googleUrl, "_blank");
  };

  run().catch(() => {
    toast("No se pudo copiar el link", "error");
  });
}

async function loadCalendarTab() {
  try {
    calendarFeedInfoCache = await get("/api/calendar/feed-info");

    const [resP, resV] = await Promise.all([
      fetch("/api/posts"),
      fetch("/api/videos"),
    ]);

    const posts = await resP.json();
    const videos = await resV.json();

    calendarPosts = posts;
    allVideosCache = videos;
    calendarFilter = "all";

    const filterBtn = document.getElementById("calendarAccountFilter");
    if (filterBtn && calendarFeedInfoCache?.brand) {
      filterBtn.textContent = `Cuenta: ${String(calendarFeedInfoCache.brand).toUpperCase()}`;
    }

    if (isMobileViewport() && calendarView === "month") {
      setCalendarView(isSmallMobileViewport() ? "day" : "week");
      return;
    }
    renderCalendarGrid();
  } catch (e) {
    console.error("Error loading calendar data:", e);
    toast("Error cargando calendario", "error");
  }
}

function renderCalendarQueue(videos) {
  const list = document.getElementById("calendarQueueList");
  const count = document.getElementById("queueCount");
  if (!list || !count) return;

  count.textContent = videos.length;

  if (videos.length === 0) {
    list.innerHTML = '<div class="empty-queue">No hay videos pendientes</div>';
    return;
  }

  list.innerHTML = videos
    .map(
      (v) => `
      <div class="queue-item" data-id="${v.id}">
        <img src="${v.thumbnail ? `/static/uploads/thumbs/${v.thumbnail}` : ""}" class="queue-thumbnail" loading="lazy">
        <div class="queue-title">${getVideoDisplayName(v)}</div>
        <div class="queue-drag-hint"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/></svg> Programa desde la pestaña Programar</div>
      </div>
    `,
    )
    .join("");
}

function changeDate(delta) {
  if (calendarView === "month") {
    calendarDate.setMonth(calendarDate.getMonth() + delta);
  } else if (calendarView === "week") {
    calendarDate.setDate(calendarDate.getDate() + delta * 7);
  } else if (calendarView === "day") {
    calendarDate.setDate(calendarDate.getDate() + delta);
  }
  renderCalendarGrid();
}

function renderCalendarGrid() {
  const grid = document.getElementById("calendarGrid");
  const label = document.getElementById("currentMonthLabel");
  const headerMap = document.getElementById("calendarGridHeader");
  if (!grid || !label) return;

  // Set Header
  const year = calendarDate.getFullYear();
  const month = calendarDate.getMonth();
  const monthNames = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
  ];
  const dayNames = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
  label.textContent = `${monthNames[month]} ${year}`;

  grid.innerHTML = "";

  // Classes
  grid.className = `calendar-grid view-${calendarView}`;
  if (headerMap) {
    headerMap.className = `calendar-grid-header view-${calendarView}`;
  }

  let daysToRender = [];

  if (calendarView === "month") {
    // En vista mes ocultamos el header externo y ponemos los nombres dentro del grid
    // para que siempre estén alineados con sus columnas (evita desplazamiento con scrollbar)
    if (headerMap) {
      headerMap.style.display = "none";
    }

    const firstDay = new Date(year, month, 1).getDay(); // 0 = Sunday
    const startOffset = firstDay === 0 ? 6 : firstDay - 1; // Adjust for Monday start
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const prevMonthDays = new Date(year, month, 0).getDate();

    // Previous month filler
    for (let i = 0; i < startOffset; i++) {
      const d = prevMonthDays - startOffset + i + 1;
      daysToRender.push({
        date: new Date(year, month - 1, d),
        otherMonth: true,
      });
    }

    // Current month
    for (let d = 1; d <= daysInMonth; d++) {
      daysToRender.push({ date: new Date(year, month, d), otherMonth: false });
    }

    // Fill end of grid to complete weeks (up to 42 cells total usually, or just modulo 7)
    while (daysToRender.length % 7 !== 0) {
      const currentLen = daysToRender.length;
      const remaining = currentLen % 7;
      const nextDays = 7 - remaining;
      for (let i = 1; i <= nextDays; i++) {
        daysToRender.push({
          date: new Date(year, month + 1, i),
          otherMonth: true,
        });
      }
    }
  } else if (calendarView === "week") {
    if (headerMap) headerMap.style.display = "";
    const currentDay = calendarDate.getDay();
    const startOffset = currentDay === 0 ? 6 : currentDay - 1; // Adjust for Monday start
    const weekStart = new Date(
      year,
      month,
      calendarDate.getDate() - startOffset,
    );

    const endWeekMonth = new Date(weekStart);
    endWeekMonth.setDate(weekStart.getDate() + 6);
    if (weekStart.getMonth() !== endWeekMonth.getMonth()) {
      label.textContent = `${monthNames[weekStart.getMonth()]} - ${monthNames[endWeekMonth.getMonth()]} ${endWeekMonth.getFullYear()}`;
    } else {
      label.textContent = `Semana de ${weekStart.getDate()} ${monthNames[weekStart.getMonth()]} ${year}`;
    }

    if (headerMap) {
      let wkHeaders = [];
      for (let i = 0; i < 7; i++) {
        const d = new Date(weekStart);
        d.setDate(d.getDate() + i);
        wkHeaders.push(`<div>${dayNames[d.getDay()]} ${d.getDate()}</div>`);
      }
      headerMap.innerHTML = wkHeaders.join("");
    }

    for (let i = 0; i < 7; i++) {
      const d = new Date(weekStart);
      d.setDate(d.getDate() + i);
      daysToRender.push({ date: d, otherMonth: d.getMonth() !== month });
    }
  } else if (calendarView === "day") {
    if (headerMap) headerMap.style.display = "";
    label.textContent = `${calendarDate.getDate()} de ${monthNames[month]} ${year}`;
    if (headerMap) {
      headerMap.innerHTML = `<div>${dayNames[calendarDate.getDay()]}</div>`;
    }
    daysToRender.push({ date: new Date(calendarDate), otherMonth: false });
  }

  const today = new Date();

  // Render the grid cells — acumulamos HTML en string para luego asignarlo de una sola vez
  // (evita reconstruir el DOM en cada iteración y mantiene alineación correcta)
  let gridHtml = "";

  // En vista mes: insertar cabeceras de días como primera fila del grid (sticky)
  // Así siempre estarán alineadas con sus columnas sin importar el scrollbar
  if (calendarView === "month") {
    const hdrDays = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
    gridHtml += hdrDays
      .map((d) => `<div class="cal-header-cell">${d}</div>`)
      .join("");
  }

  daysToRender.forEach((item) => {
    const cellDate = item.date;
    const dateStr = formatDateKey(cellDate);
    const isToday =
      today.getDate() === cellDate.getDate() &&
      today.getMonth() === cellDate.getMonth() &&
      today.getFullYear() === cellDate.getFullYear();

    let cellHtml = `<div class="cal-day ${isToday ? "today" : ""} ${item.otherMonth ? "other-month" : ""}" data-date="${dateStr}">
          <span class="cal-day-num">${cellDate.getDate()}</span>
          <div class="cal-events">`;

    const dayPosts = calendarPosts.filter((p) => {
      if (!p.scheduled_at) return false;
      const postDate = String(p.scheduled_at).slice(0, 10).replace(/\//g, "-");
      return postDate === dateStr;
    });

    dayPosts.forEach((p) => {
      let statusClass = "status-scheduled";
      if (p.status === "published") statusClass = "status-published";
      if (p.status === "failed") statusClass = "status-failed";

      let timeStr = "";
      try {
        timeStr = String(p.scheduled_at).slice(11, 16) || "??:??";
      } catch (e) {
        timeStr = "??:??";
      }

      // Note: Updated brand fallback to use postflow (or default)
      cellHtml += `
              <div class="cal-event ${p.brand || "postflow"}" data-post-id="${p.id}">
                 <div class="event-status ${statusClass}"></div>
                 <span class="event-time">${timeStr}</span>
                 <span class="event-title">${p.title || "Post"}</span>
              </div>
            `;
    });

    cellHtml += `</div></div>`;
    gridHtml += cellHtml;
  });

  grid.innerHTML = gridHtml;

  grid.querySelectorAll(".cal-event[data-post-id]").forEach((eventEl) => {
    eventEl.addEventListener("click", () => {
      const postId = Number(eventEl.dataset.postId);
      const post = calendarPosts.find((p) => p.id === postId);
      if (post) openCalendarPostModal(post);
    });
  });
}

function closeCalendarPostModal() {
  const overlay = document.getElementById("modalOverlay");
  if (!overlay) return;
  overlay.classList.add("hidden");
}

function openCalendarPostModal(post) {
  const overlay = document.getElementById("modalOverlay");
  const modal = document.getElementById("modal");
  const content = document.getElementById("modalContent");
  if (!overlay || !modal || !content) return;

  modal.classList.add("calendar-post-modal");

  const video =
    allVideosCache.find((v) => v.id === post.video_id) ||
    videos.find((v) => v.id === post.video_id);
  const videoSrc = video?.filename ? `/static/uploads/${video.filename}` : "";
  const downloadUrl = `/api/posts/${post.id}/download-video`;
  const hashtags = Array.isArray(post.hashtags) ? post.hashtags : [];
  const desc = post.description?.trim() || "Sin descripción";
  const contentType = contentTypeLabel(post.content_type || "")
    .replace(/<[^>]*>/g, "")
    .trim();

  const canRegenerate = ["scheduled", "failed"].includes(post.status);

  content.innerHTML = `
    <div class="calendar-post-head">
      <div class="calendar-post-title" id="cpm-title-${post.id}">${post.title || "Post sin título"}</div>
      <div class="calendar-post-meta">
        <span class="calendar-chip"><span class="plat-dot ${post.platform}"></span>${platformLabel(post.platform)}</span>
        <span class="calendar-chip">${statusLabel(post.status)}</span>
        <span class="calendar-chip">${post.scheduled_at || "Sin fecha"}</span>
        <span class="calendar-chip">${post.brand ? post.brand.toUpperCase() : ""}</span>
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
        <a class="btn btn-ghost btn-sm" href="${downloadUrl}">
          <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>
          Descargar video HQ
        </a>
      </div>
    </div>
    <div class="calendar-post-body">
      <div class="calendar-post-video-wrap">
        ${
          videoSrc
            ? `<video src="${videoSrc}" controls preload="metadata"></video>`
            : `<div class="calendar-post-fallback">No se encontró el video asociado.</div>`
        }
      </div>
      <div class="calendar-post-content">
        <div class="calendar-detail-block">
          <div class="calendar-detail-label">Tipo de contenido</div>
          <div class="calendar-detail-text">${contentType || "No definido"}</div>
        </div>
        <div class="calendar-detail-block">
          <div class="calendar-detail-label">Descripción</div>
          <div class="calendar-detail-text" id="cpm-desc-${post.id}">${desc}</div>
        </div>
        <div class="calendar-detail-block">
          <div class="calendar-detail-label">Hashtags</div>
          <div class="calendar-hashtags" id="cpm-hashtags-${post.id}">
            ${
              hashtags.length
                ? hashtags
                    .map((h) => `<span class="calendar-hashtag">${h}</span>`)
                    .join("")
                : `<span class="calendar-detail-text">Sin hashtags</span>`
            }
          </div>
        </div>
        ${
          canRegenerate
            ? `
        <div class="calendar-detail-block regen-block">
          <div class="calendar-detail-label">✨ Regenerar con IA</div>
          <textarea
            id="regenFeedback-${post.id}"
            class="form-input regen-feedback"
            rows="2"
            placeholder="Opcional: indica qué mejorar (ej: más llamativo, enfocarse en el producto, tono motivacional...)"
          ></textarea>
          <button
            class="btn btn-primary btn-sm mt-8"
            id="regenBtn-${post.id}"
            onclick="regeneratePostContent(${post.id})"
          >
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline" style="margin-right:4px"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
            Regenerar con IA
          </button>
        </div>
        `
            : ""
        }
      </div>
    </div>
  `;

  overlay.classList.remove("hidden");
}

async function regeneratePostContent(postId) {
  const btn = document.getElementById(`regenBtn-${postId}`);
  const feedbackEl = document.getElementById(`regenFeedback-${postId}`);
  const feedback = feedbackEl ? feedbackEl.value.trim() : "";

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline" style="margin-right:4px;animation:spin 1s linear infinite"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg> Analizando video...`;
  }

  try {
    const updated = await post(`/api/posts/${postId}/regenerate`, { feedback });

    // Update modal fields in-place
    const titleEl = document.getElementById(`cpm-title-${postId}`);
    const descEl = document.getElementById(`cpm-desc-${postId}`);
    const hashtagsEl = document.getElementById(`cpm-hashtags-${postId}`);

    if (titleEl) titleEl.textContent = updated.title || "";
    if (descEl) descEl.textContent = updated.description || "";
    if (hashtagsEl) {
      const tags = Array.isArray(updated.hashtags) ? updated.hashtags : [];
      hashtagsEl.innerHTML = tags.length
        ? tags.map((h) => `<span class="calendar-hashtag">${h}</span>`).join("")
        : `<span class="calendar-detail-text">Sin hashtags</span>`;
    }

    toast("✨ Contenido regenerado con éxito", "success");
    await refreshAllData();
  } catch (e) {
    toast(`Error al regenerar: ${e.error || "intenta de nuevo"}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" class="icon-inline" style="margin-right:4px"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg> Regenerar con IA`;
    }
  }
}
