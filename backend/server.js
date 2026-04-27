import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import express from "express";
import cors from "cors";
import multer from "multer";
import session from "express-session";
import nunjucks from "nunjucks";
import {
  ALLOWED_EXTENSIONS,
  BASE_DIR,
  BRANDS,
  BRAND_CATEGORIES,
  BRAND_CALENDAR_TOKENS,
  BRAND_LOGIN_PASSWORDS,
  MAX_VIDEO_MB,
  SECRET_KEY,
  FRONTEND_DIR,
  THUMBS_DIR,
  TIMEZONE,
  UPLOAD_DIR,
  PUBLIC_BASE_URL,
  VIDEO_INTROS_DIR,
  VIDEO_OUTROS_DIR,
  defaultContentTypeForBrand,
  brandTimezone,
} from "./src/config.js";
import { db, initDb, rowToPost, rowToVideo } from "./src/db.js";
import { HashtagService } from "./src/services/hashtagService.js";
import { SchedulerService } from "./src/services/schedulerService.js";
import { AIService } from "./src/services/aiService.js";

const app = express();
const hashtagService = new HashtagService();
const scheduler = new SchedulerService();
const aiService = new AIService();

const AI_STATUS_DIR = path.join(os.tmpdir(), "postflow_ai_status");
fs.mkdirSync(AI_STATUS_DIR, { recursive: true });
fs.mkdirSync(UPLOAD_DIR, { recursive: true });
fs.mkdirSync(THUMBS_DIR, { recursive: true });
fs.mkdirSync(VIDEO_INTROS_DIR, { recursive: true });
fs.mkdirSync(VIDEO_OUTROS_DIR, { recursive: true });

initDb();
scheduler.start();

nunjucks.configure(path.join(FRONTEND_DIR, "templates"), {
  autoescape: true,
  express: app,
  noCache: true,
});
app.set("view engine", "html");

app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true }));
app.use(
  session({
    secret: SECRET_KEY,
    resave: false,
    saveUninitialized: false,
    cookie: { httpOnly: true, maxAge: 1000 * 60 * 60 * 24 * 30 },
  }),
);

app.use(
  "/static",
  express.static(path.join(FRONTEND_DIR, "static"), { etag: false, maxAge: 0 }),
);

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, UPLOAD_DIR),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname || "").toLowerCase();
    cb(null, `${crypto.randomUUID().replace(/-/g, "")}${ext}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: MAX_VIDEO_MB * 1024 * 1024 },
});

const brandAssetUpload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 200 * 1024 * 1024 },
});

function authBrand(req) {
  const b = req.session?.auth_brand;
  return BRANDS[b] ? b : null;
}

function aiStatusPath(requestId) {
  const safe = String(requestId || "").replace(/[^a-zA-Z0-9_-]/g, "");
  return path.join(AI_STATUS_DIR, `${safe}.json`);
}

function setAiStatus(requestId, payload) {
  if (!requestId) return;
  const fp = aiStatusPath(requestId);
  let current = {};
  try {
    current = JSON.parse(fs.readFileSync(fp, "utf8"));
  } catch {}
  current = { ...current, ...payload, updated_at: new Date().toISOString() };
  fs.writeFileSync(fp, JSON.stringify(current));
}

function getExt(name) {
  return String(name || "")
    .split(".")
    .pop()
    .toLowerCase();
}

function getBrandAssetDir(type) {
  return type === "intro" ? VIDEO_INTROS_DIR : VIDEO_OUTROS_DIR;
}

function listBrandAsset(brand, type) {
  const dir = getBrandAssetDir(type);
  const prefix = `${brand}-${type}.`;
  const found = fs.readdirSync(dir).find((name) => name.startsWith(prefix));
  if (!found) return { has_file: false, name: null, url: null };
  return {
    has_file: true,
    name: found,
    url: `/static/uploads/brand-assets/${type}/${found}`,
  };
}

function cleanupBrandAsset(brand, type) {
  const dir = getBrandAssetDir(type);
  const prefix = `${brand}-${type}.`;
  for (const name of fs.readdirSync(dir)) {
    if (!name.startsWith(prefix)) continue;
    try {
      fs.unlinkSync(path.join(dir, name));
    } catch {}
  }
}

function ffprobeDuration(filePath) {
  const r = spawnSync(
    "ffprobe",
    [
      "-v",
      "error",
      "-show_entries",
      "format=duration",
      "-of",
      "default=noprint_wrappers=1:nokey=1",
      filePath,
    ],
    { encoding: "utf8" },
  );
  if (r.status !== 0) return 0;
  const duration = Number(String(r.stdout || "").trim());
  return Number.isFinite(duration) ? Math.round(duration * 100) / 100 : 0;
}

function generateThumb(videoPath, uniqueName) {
  const out = path.join(THUMBS_DIR, `${uniqueName}.jpg`);
  const r = spawnSync(
    "ffmpeg",
    ["-y", "-i", videoPath, "-ss", "00:00:01", "-vframes", "1", out],
    { encoding: "utf8" },
  );
  if (r.status !== 0 || !fs.existsSync(out)) return null;
  return `/static/uploads/thumbs/${path.basename(out)}`;
}

function dateToBrandIso(brand, input) {
  const local = new Date(input);
  const tz = brandTimezone(brand);
  const inBrand = local
    .toLocaleString("sv-SE", { timeZone: tz })
    .replace(" ", "T");
  return new Date(inBrand).toISOString();
}

function requireAuth(req, res, next) {
  const open = new Set([
    "/login",
    "/terms",
    "/privacy",
    "/favicon.ico",
    "/auth/tiktok",
    "/callback",
  ]);
  if (
    open.has(req.path) ||
    req.path.startsWith("/static/") ||
    req.path.startsWith("/calendar/feed/")
  )
    return next();
  if (req.path === "/tiktokvMpBF2nnx9wF8HkcdB6FQfB8ksMO9Isq.txt") return next();
  if (authBrand(req)) return next();
  if (req.path.startsWith("/api/"))
    return res.status(401).json({ error: "No autenticado" });
  return res.redirect("/login");
}

app.use(requireAuth);

app.get("/favicon.ico", (_req, res) => {
  return res
    .type("image/svg+xml")
    .sendFile(path.join(FRONTEND_DIR, "static", "favicon.svg"));
});

app.get("/", (req, res) => {
  const brand = authBrand(req);
  res.render("index", {
    auth_brand: brand,
    auth_label: BRANDS[brand]?.label || "",
  });
});

app
  .route("/login")
  .get((req, res) => {
    if (authBrand(req)) return res.redirect("/");
    return res.render("login", { brands: BRANDS, error: "" });
  })
  .post((req, res) => {
    const brand = String(req.body?.brand || "").trim();
    const password = String(req.body?.password || "");
    if (
      !BRAND_LOGIN_PASSWORDS[brand] ||
      BRAND_LOGIN_PASSWORDS[brand] !== password
    ) {
      if (req.is("application/json"))
        return res.status(401).json({ error: "Credenciales inválidas" });
      return res
        .status(401)
        .render("login", { brands: BRANDS, error: "Credenciales inválidas" });
    }
    req.session.auth_brand = brand;
    if (req.is("application/json"))
      return res.json({ message: "Login exitoso", brand });
    return res.redirect("/");
  });

app.post("/logout", (req, res) => {
  req.session.destroy(() => res.redirect("/login"));
});

app.get("/terms", (_req, res) => res.render("terms"));
app.get("/privacy", (_req, res) => res.render("privacy"));

app.get("/auth/tiktok", (req, res) => {
  const brand = authBrand(req) || "gymark";
  const state = crypto.randomBytes(24).toString("base64url");
  req.session.oauth_state = state;
  req.session.oauth_brand = brand;

  const upper = brand.toUpperCase();
  const clientKey = process.env[`${upper}_TIKTOK_CLIENT_KEY`] || "";
  if (!clientKey) {
    return res
      .status(400)
      .send(
        "<h2>OAuth TikTok</h2><p>Falta CLIENT_KEY en variables de entorno.</p>",
      );
  }

  const params = new URLSearchParams({
    client_key: clientKey,
    scope: "user.info.profile,user.info.stats,video.list,video.upload",
    response_type: "code",
    redirect_uri: `${PUBLIC_BASE_URL}/callback`,
    state,
  });
  return res.redirect(
    `https://sandbox-open-api.tiktok.com/auth/authorize/?${params.toString()}`,
  );
});

app.get("/callback", async (req, res) => {
  const brand = req.session.oauth_brand || authBrand(req) || "gymark";
  const code = String(req.query.code || "");
  const state = String(req.query.state || "");
  const error = String(req.query.error || "");

  if (!state || state !== req.session.oauth_state) {
    return res.status(400).send("<h2>Error OAuth</h2><p>Estado inválido.</p>");
  }
  if (error) {
    return res.status(400).send(`<h2>Error OAuth</h2><p>${error}</p>`);
  }
  if (!code) {
    return res
      .status(400)
      .send("<h2>Error OAuth</h2><p>No se recibió código.</p>");
  }

  const upper = brand.toUpperCase();
  const clientKey = process.env[`${upper}_TIKTOK_CLIENT_KEY`] || "";
  const clientSecret = process.env[`${upper}_TIKTOK_CLIENT_SECRET`] || "";
  if (!clientKey || !clientSecret) {
    return res
      .status(400)
      .send("<h2>Error OAuth</h2><p>Falta client key/secret.</p>");
  }

  try {
    const form = new URLSearchParams({
      client_key: clientKey,
      client_secret: clientSecret,
      code,
      grant_type: "authorization_code",
      redirect_uri: `${PUBLIC_BASE_URL}/callback`,
    });

    const response = await fetch(
      "https://sandbox-open-api.tiktok.com/oauth/token/",
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form,
      },
    );

    const payload = await response.json();
    if (!response.ok) {
      return res
        .status(400)
        .send(
          `<h2>Error OAuth</h2><pre>${JSON.stringify(payload, null, 2)}</pre>`,
        );
    }

    const accessToken = payload.access_token || "";
    const openId = payload.open_id || "";
    if (!accessToken || !openId) {
      return res
        .status(400)
        .send(
          `<h2>Error OAuth</h2><pre>${JSON.stringify(payload, null, 2)}</pre>`,
        );
    }

    return res.send(
      `<h2>🎉 OAuth Exitoso</h2><pre>${upper}_TIKTOK_ACCESS_TOKEN=${accessToken}\n${upper}_TIKTOK_OPEN_ID=${openId}</pre><p><a href='/'>Volver</a></p>`,
    );
  } catch (e) {
    return res
      .status(500)
      .send(`<h2>Error OAuth</h2><p>${String(e.message || e)}</p>`);
  }
});

app.get("/tiktokvMpBF2nnx9wF8HkcdB6FQfB8ksMO9Isq.txt", (_req, res) => {
  const f = path.join(
    BASE_DIR,
    "static",
    "tiktokvMpBF2nnx9wF8HkcdB6FQfB8ksMO9Isq.txt",
  );
  if (!fs.existsSync(f)) return res.status(404).end();
  res.type("text/plain");
  return res.sendFile(f);
});

app.get("/api/brands", (req, res) => {
  const b = authBrand(req);
  if (!b || !BRANDS[b]) return res.json([]);
  return res.json([
    {
      key: b,
      label: BRANDS[b].label,
      color: BRANDS[b].color,
      platforms: BRANDS[b].platforms,
      categories: BRAND_CATEGORIES[b] || [],
    },
  ]);
});

app.get("/api/videos", (req, res) => {
  const brand = authBrand(req);
  const videos = db
    .prepare("SELECT * FROM videos WHERE brand = ? ORDER BY uploaded_at DESC")
    .all(brand);
  const postStmt = db.prepare("SELECT * FROM posts WHERE video_id = ?");
  const payload = videos.map((v) =>
    rowToVideo(v, postStmt.all(v.id).map(rowToPost)),
  );
  res.json(payload);
});

app.post("/api/videos/upload", upload.single("video"), (req, res) => {
  if (!req.file)
    return res.status(400).json({ error: "No se encontró el campo 'video'" });

  const ext = getExt(req.file.originalname);
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    fs.unlinkSync(req.file.path);
    return res.status(400).json({
      error: `Formato no permitido. Usa: ${Array.from(ALLOWED_EXTENSIONS).join(", ")}`,
    });
  }

  const brand = authBrand(req) || "gymark";
  const requestedCategory = String(req.body?.category_id || "").trim();
  let categoryId = requestedCategory;
  const allowed = new Set(BRAND_CATEGORIES[brand] || []);
  if (!categoryId && brand !== "gymark")
    categoryId = defaultContentTypeForBrand(brand);
  if (categoryId && !allowed.has(categoryId))
    categoryId = defaultContentTypeForBrand(brand);

  const fileSize = req.file.size || 0;
  const duration = ffprobeDuration(req.file.path);
  const thumb = generateThumb(
    req.file.path,
    path.basename(req.file.filename, path.extname(req.file.filename)),
  );

  const result = db
    .prepare(
      `
    INSERT INTO videos (filename, original_name, brand, file_path, source_file_path, file_size, duration, thumbnail, category_id, uploaded_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `,
    )
    .run(
      req.file.filename,
      req.file.originalname,
      brand,
      req.file.path,
      req.file.path,
      fileSize,
      duration,
      thumb,
      categoryId,
      new Date().toISOString(),
    );

  const video = db
    .prepare("SELECT * FROM videos WHERE id = ?")
    .get(result.lastInsertRowid);
  const payload = rowToVideo(video, []);
  payload.metadata_stripped = true;
  return res.status(201).json(payload);
});

app.delete("/api/videos/:id", (req, res) => {
  const id = Number(req.params.id);
  const brand = authBrand(req);
  const video = db
    .prepare("SELECT * FROM videos WHERE id = ? AND brand = ?")
    .get(id, brand);
  if (!video) return res.status(404).json({ error: "Video no encontrado" });

  for (const disk of [
    video.file_path,
    video.source_file_path,
    video.processed_file_path,
  ]) {
    if (disk && fs.existsSync(disk)) {
      try {
        fs.unlinkSync(disk);
      } catch {}
    }
  }
  if (video.thumbnail) {
    const thumbPath = path.join(BASE_DIR, video.thumbnail.replace(/^\//, ""));
    if (fs.existsSync(thumbPath)) {
      try {
        fs.unlinkSync(thumbPath);
      } catch {}
    }
  }

  db.prepare("DELETE FROM videos WHERE id = ?").run(id);
  res.json({ message: "Video eliminado" });
});

app.get("/api/brand/assets", (req, res) => {
  const brand = authBrand(req) || "gymark";
  res.json({
    intro: listBrandAsset(brand, "intro"),
    outro: listBrandAsset(brand, "outro"),
  });
});

app.post(
  "/api/brand/:type",
  brandAssetUpload.single("intro_file"),
  (req, res, next) => {
    if (req.params.type !== "intro") return next();
    const brand = authBrand(req) || "gymark";
    const file = req.file;
    if (!file)
      return res.status(400).json({ error: "No se recibió intro_file" });

    const ext = getExt(file.originalname);
    if (!ALLOWED_EXTENSIONS.has(ext))
      return res.status(400).json({ error: "Formato no permitido" });
    cleanupBrandAsset(brand, "intro");
    const targetName = `${brand}-intro.${ext}`;
    fs.writeFileSync(path.join(VIDEO_INTROS_DIR, targetName), file.buffer);
    return res.json(listBrandAsset(brand, "intro"));
  },
);

app.post(
  "/api/brand/:type",
  brandAssetUpload.single("outro_file"),
  (req, res) => {
    if (req.params.type !== "outro")
      return res.status(404).json({ error: "Tipo inválido" });
    const brand = authBrand(req) || "gymark";
    const file = req.file;
    if (!file)
      return res.status(400).json({ error: "No se recibió outro_file" });

    const ext = getExt(file.originalname);
    if (!ALLOWED_EXTENSIONS.has(ext))
      return res.status(400).json({ error: "Formato no permitido" });
    cleanupBrandAsset(brand, "outro");
    const targetName = `${brand}-outro.${ext}`;
    fs.writeFileSync(path.join(VIDEO_OUTROS_DIR, targetName), file.buffer);
    return res.json(listBrandAsset(brand, "outro"));
  },
);

app.delete("/api/brand/:type", (req, res) => {
  const type = req.params.type;
  if (type !== "intro" && type !== "outro")
    return res.status(404).json({ error: "Tipo inválido" });
  const brand = authBrand(req) || "gymark";
  cleanupBrandAsset(brand, type);
  return res.json(listBrandAsset(brand, type));
});

app.post("/api/ai/generate", async (req, res) => {
  const {
    video_id: videoId,
    category_id: categoryId,
    request_id: requestId = "",
    brand: targetBrand = null,
  } = req.body || {};
  if (!videoId) return res.status(400).json({ error: "Falta video_id" });

  const auth = authBrand(req);
  const video = db
    .prepare("SELECT * FROM videos WHERE id = ? AND brand = ?")
    .get(Number(videoId), auth);
  if (!video) return res.status(404).json({ error: "Video no encontrado" });

  let resolvedBrand = auth;
  if (targetBrand && BRANDS[targetBrand]) {
    resolvedBrand = targetBrand;
    db.prepare("UPDATE videos SET brand = ? WHERE id = ?").run(
      resolvedBrand,
      video.id,
    );
  }

  const allowedCategories = new Set(BRAND_CATEGORIES[resolvedBrand] || []);
  const requestedCategory = String(categoryId || "").trim();
  const shouldInferGymarkCategory =
    resolvedBrand === "gymark" && !requestedCategory;

  let resolvedCategory = requestedCategory;
  if (resolvedCategory && !allowedCategories.has(resolvedCategory)) {
    resolvedCategory = defaultContentTypeForBrand(resolvedBrand);
  }
  if (!resolvedCategory && !shouldInferGymarkCategory) {
    resolvedCategory = defaultContentTypeForBrand(resolvedBrand);
  }

  setAiStatus(requestId, {
    status: "processing",
    model: "Gemini",
    phase: "queued",
  });

  try {
    const result = await aiService.generateMetadata({
      videoPath: video.source_file_path || video.file_path,
      brand: resolvedBrand,
      categoryId: shouldInferGymarkCategory ? "" : resolvedCategory,
      progressCallback: (model, phase) =>
        setAiStatus(requestId, { status: "processing", model, phase }),
    });

    const finalCategoryRaw = shouldInferGymarkCategory
      ? String(result.category_id || "").trim()
      : resolvedCategory;
    const finalCategory = allowedCategories.has(finalCategoryRaw)
      ? finalCategoryRaw
      : defaultContentTypeForBrand(resolvedBrand);

    db.prepare(
      "UPDATE videos SET ai_title = ?, ai_description = ?, category_id = ?, brand = ? WHERE id = ?",
    ).run(
      result.titulo || "",
      result.descripcion || "",
      finalCategory,
      resolvedBrand,
      video.id,
    );

    const currentExt = path.extname(video.filename || "") || "";
    const aiName = String(result.titulo || "").trim();
    if (aiName)
      db.prepare("UPDATE videos SET original_name = ? WHERE id = ?").run(
        `${aiName}${currentExt}`,
        video.id,
      );

    const hashtags = hashtagService.getHashtags(finalCategory, "tiktok", {
      brand: resolvedBrand,
    });
    setAiStatus(requestId, {
      status: "completed",
      model: result.model_used || "Gemini",
      phase: "done",
    });

    return res.json({
      ...result,
      hashtags,
      category_id: finalCategory,
      brand: resolvedBrand,
    });
  } catch (error) {
    setAiStatus(requestId, {
      status: "failed",
      model: null,
      phase: "error",
      error: String(error.message || error),
    });
    return res.status(500).json({ error: String(error.message || error) });
  }
});

app.get("/api/ai/status/:requestId", (req, res) => {
  const fp = aiStatusPath(req.params.requestId);
  if (!fs.existsSync(fp))
    return res
      .status(404)
      .json({ status: "unknown", model: null, phase: null });
  try {
    const payload = JSON.parse(fs.readFileSync(fp, "utf8"));
    return res.json(payload);
  } catch {
    return res
      .status(404)
      .json({ status: "unknown", model: null, phase: null });
  }
});

app.get("/api/posts", (req, res) => {
  const brand = authBrand(req);
  const status = String(req.query.status || "").trim();
  let rows;
  if (status) {
    rows = db
      .prepare(
        "SELECT * FROM posts WHERE brand = ? AND status = ? ORDER BY scheduled_at ASC",
      )
      .all(brand, status);
  } else {
    rows = db
      .prepare("SELECT * FROM posts WHERE brand = ? ORDER BY scheduled_at ASC")
      .all(brand);
  }
  res.json(rows.map(rowToPost));
});

app.post("/api/posts/schedule", (req, res) => {
  const body = req.body || {};
  const required = ["video_id", "platforms", "title"];
  const missing = required.filter(
    (k) => !body[k] || (Array.isArray(body[k]) && body[k].length === 0),
  );
  if (missing.length)
    return res
      .status(400)
      .json({ error: `Faltan campos: ${missing.join(", ")}` });

  const brand = authBrand(req);
  const video = db
    .prepare("SELECT * FROM videos WHERE id = ? AND brand = ?")
    .get(Number(body.video_id), brand);
  if (!video) return res.status(404).json({ error: "Video no encontrado" });

  const platforms = Array.isArray(body.platforms) ? body.platforms : [];
  const allowedPlatforms = new Set(BRANDS[brand]?.platforms || []);
  const invalid = platforms.filter((p) => !allowedPlatforms.has(p));
  if (invalid.length)
    return res.status(400).json({
      error: `Plataformas no permitidas para ${brand}: ${invalid.join(", ")}`,
    });

  let contentType = String(body.content_type || "").trim();
  if (brand === "gymark") {
    contentType = String(video.category_id || "").trim();
    if (!contentType)
      return res.status(400).json({
        error:
          "Este video de Gymark no tiene categoría detectada por IA. Analízalo con IA antes de programar.",
      });
  }
  if (!contentType) contentType = defaultContentTypeForBrand(brand);

  const allowedCategories = new Set(BRAND_CATEGORIES[brand] || []);
  if (!allowedCategories.has(contentType)) {
    return res.status(400).json({
      error: `Categoría '${contentType}' no permitida para la marca ${brand}`,
    });
  }

  const autoTime =
    body.auto_time ?? String(body.schedule_mode || "auto") !== "manual";
  const manualDt = body.scheduled_at || body.post_date || null;
  const created = [];

  for (const platform of platforms) {
    let scheduledAt = null;

    if (autoTime) {
      try {
        scheduledAt = scheduler.getNextBestTime({
          platform,
          contentType,
          brand,
          reserve: true,
        });
      } catch (error) {
        return res.status(400).json({ error: String(error.message || error) });
      }
    } else {
      if (!manualDt)
        return res
          .status(400)
          .json({ error: "scheduled_at requerido cuando auto_time=false" });
      scheduledAt = new Date(manualDt);
      if (Number.isNaN(scheduledAt.getTime()))
        return res.status(400).json({ error: "Fecha manual inválida" });
    }

    const limit = scheduler.checkDailyLimits({ brand, platform, scheduledAt });
    if (!limit.allowed) return res.status(400).json({ error: limit.error });

    const hashtags = hashtagService.getHashtags(contentType, platform, {
      brand,
    });
    const scheduledIso = autoTime
      ? dateToBrandIso(brand, scheduledAt)
      : new Date(manualDt).toISOString();

    const insert = db
      .prepare(
        `
      INSERT INTO posts (video_id, brand, platform, title, description, hashtags, content_type, scheduled_at, status, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)
    `,
      )
      .run(
        Number(body.video_id),
        brand,
        platform,
        String(body.title || "").trim(),
        String(body.description || "").trim(),
        JSON.stringify(hashtags),
        contentType,
        scheduledIso,
        new Date().toISOString(),
      );

    const row = db
      .prepare("SELECT * FROM posts WHERE id = ?")
      .get(insert.lastInsertRowid);
    created.push(rowToPost(row));
  }

  return res.status(201).json({ posts: created });
});

app.delete("/api/posts/clear", (req, res) => {
  const brand = authBrand(req);
  const deleted = db
    .prepare("DELETE FROM posts WHERE brand = ?")
    .run(brand).changes;
  return res.json({ message: `${deleted} posts eliminados`, deleted });
});

app.delete("/api/posts/:id", (req, res) => {
  const id = Number(req.params.id);
  const brand = authBrand(req);
  const row = db
    .prepare("SELECT * FROM posts WHERE id = ? AND brand = ?")
    .get(id, brand);
  if (!row) return res.status(404).json({ error: "Post no encontrado" });
  if (row.status === "published")
    return res
      .status(400)
      .json({ error: "No se puede cancelar un post ya publicado" });
  db.prepare("UPDATE posts SET status = 'cancelled' WHERE id = ?").run(id);
  return res.json({ message: "Post cancelado" });
});

app.post("/api/posts/:id/regenerate", async (req, res) => {
  const id = Number(req.params.id);
  const brand = authBrand(req);
  const post = db
    .prepare("SELECT * FROM posts WHERE id = ? AND brand = ?")
    .get(id, brand);
  if (!post) return res.status(404).json({ error: "Post no encontrado" });

  const video = db
    .prepare("SELECT * FROM videos WHERE id = ?")
    .get(post.video_id);
  if (!video)
    return res.status(404).json({ error: "Video del post no encontrado" });

  try {
    const result = await aiService.generateMetadata({
      videoPath: video.source_file_path || video.file_path,
      brand: post.brand,
      categoryId:
        post.content_type ||
        video.category_id ||
        defaultContentTypeForBrand(post.brand),
      extraContext: String(req.body?.feedback || "").trim(),
    });

    const hashtags = hashtagService.getHashtags(
      post.content_type || defaultContentTypeForBrand(post.brand),
      post.platform,
      { brand: post.brand },
    );
    db.prepare(
      "UPDATE posts SET title = ?, description = ?, hashtags = ? WHERE id = ?",
    ).run(result.titulo, result.descripcion, JSON.stringify(hashtags), id);
    const updated = db.prepare("SELECT * FROM posts WHERE id = ?").get(id);
    return res.json(rowToPost(updated));
  } catch (error) {
    return res.status(500).json({ error: String(error.message || error) });
  }
});

app.post("/api/posts/:id/publish-now", (req, res) => {
  const id = Number(req.params.id);
  const brand = authBrand(req);
  const post = db
    .prepare("SELECT * FROM posts WHERE id = ? AND brand = ?")
    .get(id, brand);
  if (!post) return res.status(404).json({ error: "Post no encontrado" });
  if (!["scheduled", "failed"].includes(post.status)) {
    return res
      .status(400)
      .json({ error: `No se puede publicar con estado: ${post.status}` });
  }
  db.prepare(
    "UPDATE posts SET status = 'scheduled', scheduled_at = ? WHERE id = ?",
  ).run(new Date().toISOString(), id);
  const updated = scheduler.publishPost(id);
  return res.json(updated);
});

app.get("/api/posts/:id/download-video", (req, res) => {
  const id = Number(req.params.id);
  const brand = authBrand(req);
  const post = db
    .prepare("SELECT * FROM posts WHERE id = ? AND brand = ?")
    .get(id, brand);
  if (!post) return res.status(404).json({ error: "Post no encontrado" });

  const video = db
    .prepare("SELECT * FROM videos WHERE id = ? AND brand = ?")
    .get(post.video_id, brand);
  if (!video) return res.status(404).json({ error: "Video no encontrado" });

  const realPath = video.processed_file_path || video.file_path;
  if (!realPath || !fs.existsSync(realPath))
    return res.status(404).json({ error: "Archivo de video no encontrado" });

  const base =
    String(
      post.title ||
        video.ai_title ||
        video.original_name ||
        `video-${video.id}`,
    )
      .replace(/[\\/:*?"<>|]+/g, " ")
      .trim() || `video-${video.id}`;
  const ext = path.extname(realPath) || ".mp4";

  return res.download(realPath, `${base}${ext}`);
});

app.get("/api/hashtags/suggest", (req, res) => {
  const brand = authBrand(req) || "gymark";
  const defaultType = defaultContentTypeForBrand(brand);
  let contentType = String(req.query.content_type || defaultType);
  if (!(BRAND_CATEGORIES[brand] || []).includes(contentType))
    contentType = defaultType;
  const platform = String(req.query.platform || "tiktok");
  const hashtags = hashtagService.getHashtags(contentType, platform, { brand });
  return res.json({
    hashtags,
    hashtags_joined: hashtagService.getHashtagsJoined(contentType, platform, {
      brand,
    }),
  });
});

app.get("/api/hashtags/content-types", (req, res) => {
  const brand = authBrand(req) || "gymark";
  const allowed = new Set(BRAND_CATEGORIES[brand] || []);
  return res.json(
    hashtagService.getContentTypes().filter((t) => allowed.has(t.key)),
  );
});

app.post("/api/schedule/preview", (req, res) => {
  const brand = authBrand(req) || "gymark";
  const allowedPlatforms = new Set(BRANDS[brand]?.platforms || ["tiktok"]);
  let platforms = Array.isArray(req.body?.platforms)
    ? req.body.platforms.filter((p) => allowedPlatforms.has(p))
    : [];
  if (!platforms.length) platforms = [...allowedPlatforms];

  let contentType = String(
    req.body?.content_type || defaultContentTypeForBrand(brand),
  );
  if (!(BRAND_CATEGORIES[brand] || []).includes(contentType))
    contentType = defaultContentTypeForBrand(brand);

  return res.json(
    scheduler.getSchedulePreview({ platforms, contentType, brand }),
  );
});

app.get("/api/dashboard", (req, res) => {
  const brand = authBrand(req);
  const totalVideos = db
    .prepare("SELECT COUNT(*) AS total FROM videos WHERE brand = ?")
    .get(brand).total;
  const totalPosts = db
    .prepare("SELECT COUNT(*) AS total FROM posts WHERE brand = ?")
    .get(brand).total;
  const published = db
    .prepare(
      "SELECT COUNT(*) AS total FROM posts WHERE brand = ? AND status = 'published'",
    )
    .get(brand).total;
  const scheduled = db
    .prepare(
      "SELECT COUNT(*) AS total FROM posts WHERE brand = ? AND status = 'scheduled'",
    )
    .get(brand).total;
  const failed = db
    .prepare(
      "SELECT COUNT(*) AS total FROM posts WHERE brand = ? AND status = 'failed'",
    )
    .get(brand).total;

  const byPlatformRows = db
    .prepare(
      "SELECT platform, COUNT(*) AS total FROM posts WHERE brand = ? GROUP BY platform",
    )
    .all(brand);
  const byPlatform = Object.fromEntries(
    byPlatformRows.map((r) => [r.platform, r.total]),
  );

  const upcoming = db
    .prepare(
      "SELECT * FROM posts WHERE brand = ? AND status = 'scheduled' ORDER BY scheduled_at ASC LIMIT 5",
    )
    .all(brand)
    .map(rowToPost);
  const recent = db
    .prepare(
      "SELECT * FROM posts WHERE brand = ? AND status = 'published' ORDER BY posted_at DESC LIMIT 5",
    )
    .all(brand)
    .map(rowToPost);

  return res.json({
    total_videos: totalVideos,
    total_posts: totalPosts,
    published,
    scheduled,
    failed,
    by_platform: byPlatform,
    upcoming,
    recent,
  });
});

app.get("/api/config/status", (req, res) => {
  const brand = authBrand(req) || "gymark";
  const upper = brand.toUpperCase();
  const tiktokOk = Boolean(
    process.env[`${upper}_TIKTOK_ACCESS_TOKEN`] &&
    process.env[`${upper}_TIKTOK_OPEN_ID`],
  );
  const instagramOk = Boolean(
    process.env[`${upper}_INSTAGRAM_ACCOUNT_ID`] &&
    process.env[`${upper}_FACEBOOK_ACCESS_TOKEN`],
  );
  const facebookOk = Boolean(
    process.env[`${upper}_FACEBOOK_PAGE_ID`] &&
    process.env[`${upper}_FACEBOOK_ACCESS_TOKEN`],
  );

  return res.json({
    timezone: TIMEZONE,
    brands: {
      [brand]: {
        tiktok: tiktokOk,
        instagram: instagramOk,
        facebook: facebookOk,
      },
    },
    tiktok: tiktokOk,
    instagram: instagramOk,
    facebook: facebookOk,
  });
});

function buildCalendarEvent(post, publicFeed = false) {
  const date = new Date(post.scheduled_at);
  const dt = date.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const end =
    new Date(date.getTime() + 30 * 60 * 1000)
      .toISOString()
      .replace(/[-:]/g, "")
      .split(".")[0] + "Z";
  const title = String(post.title || "Post").replace(/\n/g, " ");
  const desc = publicFeed
    ? `${post.platform.toUpperCase()} · ${post.brand.toUpperCase()}`
    : `${post.platform.toUpperCase()} · Estado: ${post.status}`;
  return [
    "BEGIN:VEVENT",
    `UID:postflow-${post.id}@postflow`,
    `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").split(".")[0]}Z`,
    `DTSTART:${dt}`,
    `DTEND:${end}`,
    `SUMMARY:${title}`,
    `DESCRIPTION:${desc}`,
    "END:VEVENT",
  ].join("\r\n");
}

function buildCalendarIcs(brand, posts, publicFeed = false) {
  const header = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//PostFlow//Calendar//ES",
    `X-WR-CALNAME:PostFlow ${brand.toUpperCase()}`,
    "CALSCALE:GREGORIAN",
  ];
  const body = posts.map((p) => buildCalendarEvent(p, publicFeed));
  return `${[...header, ...body, "END:VCALENDAR"].join("\r\n")}\r\n`;
}

app.get("/calendar.ics", (req, res) => {
  const brand = authBrand(req);
  const posts = db
    .prepare(
      "SELECT * FROM posts WHERE brand = ? AND status IN ('scheduled', 'posting', 'published') ORDER BY scheduled_at ASC",
    )
    .all(brand);
  const ics = buildCalendarIcs(brand, posts, false);
  res.setHeader("Content-Type", "text/calendar; charset=utf-8");
  return res.send(ics);
});

app.get("/calendar/feed/:brand.ics", (req, res) => {
  const brand = String(req.params.brand || "").toLowerCase();
  if (!BRANDS[brand]) return res.status(404).end();
  const token = String(req.query.token || "");
  if (!BRAND_CALENDAR_TOKENS[brand] || BRAND_CALENDAR_TOKENS[brand] !== token)
    return res.status(403).end();

  const posts = db
    .prepare(
      "SELECT * FROM posts WHERE brand = ? AND status IN ('scheduled', 'posting', 'published') ORDER BY scheduled_at ASC",
    )
    .all(brand);
  const ics = buildCalendarIcs(brand, posts, true);
  res.setHeader("Content-Type", "text/calendar; charset=utf-8");
  return res.send(ics);
});

app.get("/api/calendar/feed-info", (req, res) => {
  const brand = authBrand(req) || "gymark";
  const token = BRAND_CALENDAR_TOKENS[brand];
  const base = `${req.protocol}://${req.get("host")}`;
  const feedUrl = `${base}/calendar/feed/${brand}.ics?token=${token}`;
  const webcalUrl = feedUrl.replace(/^https?:\/\//, "webcal://");
  const googleSubscribeUrl = `https://calendar.google.com/calendar/render?cid=${encodeURIComponent(webcalUrl)}`;
  return res.json({
    brand,
    feed_url: feedUrl,
    webcal_url: webcalUrl,
    google_subscribe_url: googleSubscribeUrl,
  });
});

const PORT = Number(process.env.PORT || 8080);
app.listen(PORT, () => {
  console.log(`PostFlow Node escuchando en http://0.0.0.0:${PORT}`);
});
