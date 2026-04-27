import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";
import { DATABASE_PATH, TIMEZONE } from "./config.js";

fs.mkdirSync(path.dirname(DATABASE_PATH), { recursive: true });

export const db = new Database(DATABASE_PATH);
db.pragma("journal_mode = WAL");
db.pragma("foreign_keys = ON");

function ensureColumns(tableName, columns) {
  const existing = new Set(
    db
      .prepare(`PRAGMA table_info(${tableName})`)
      .all()
      .map((col) => String(col.name)),
  );

  for (const [name, definition] of columns) {
    if (existing.has(name)) continue;
    db.exec(`ALTER TABLE ${tableName} ADD COLUMN ${name} ${definition}`);
  }
}

export function initDb() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS videos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      filename TEXT NOT NULL,
      original_name TEXT NOT NULL,
      brand TEXT NOT NULL DEFAULT 'gymark',
      file_path TEXT NOT NULL,
      source_file_path TEXT,
      processed_file_path TEXT,
      file_size INTEGER DEFAULT 0,
      duration REAL DEFAULT 0,
      thumbnail TEXT,
      uploaded_at TEXT DEFAULT (datetime('now')),
      category_id TEXT,
      ai_title TEXT,
      ai_description TEXT
    );

    CREATE TABLE IF NOT EXISTS posts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      video_id INTEGER NOT NULL,
      brand TEXT NOT NULL DEFAULT 'gymark',
      platform TEXT NOT NULL,
      title TEXT NOT NULL,
      description TEXT,
      hashtags TEXT,
      content_type TEXT,
      scheduled_at TEXT NOT NULL,
      posted_at TEXT,
      status TEXT DEFAULT 'scheduled',
      platform_post_id TEXT,
      error_message TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
    );
  `);

  ensureColumns("videos", [
    ["source_file_path", "TEXT"],
    ["processed_file_path", "TEXT"],
    ["file_size", "INTEGER DEFAULT 0"],
    ["category_id", "TEXT"],
    ["ai_title", "TEXT"],
    ["ai_description", "TEXT"],
  ]);

  ensureColumns("posts", [
    ["content_type", "TEXT"],
    ["error_message", "TEXT"],
  ]);
}

export function rowToVideo(row, posts = []) {
  const selectedPath = row.processed_file_path || row.file_path;
  const toUrl = (diskPath) => {
    if (!diskPath) return null;
    const norm = String(diskPath).replace(/\\/g, "/");
    const idx = norm.lastIndexOf("/static/");
    if (idx >= 0) return norm.slice(idx);
    if (norm.includes("static/")) return `/${norm.split("static/")[1]}`;
    return null;
  };

  return {
    id: row.id,
    filename: row.filename,
    original_name: row.original_name,
    brand: row.brand,
    file_size_mb: Number(((row.file_size || 0) / (1024 * 1024)).toFixed(2)),
    duration: row.duration || 0,
    thumbnail: row.thumbnail || null,
    uploaded_at: formatDateTime(row.uploaded_at),
    category_id: row.category_id || null,
    ai_title: row.ai_title || null,
    ai_description: row.ai_description || null,
    video_url: toUrl(selectedPath),
    source_video_url: toUrl(row.source_file_path || row.file_path),
    is_customized: Boolean(row.processed_file_path),
    posts,
  };
}

export function rowToPost(row) {
  let hashtags = [];
  try {
    hashtags = row.hashtags ? JSON.parse(row.hashtags) : [];
    if (!Array.isArray(hashtags)) hashtags = [];
  } catch {
    hashtags = [];
  }

  return {
    id: row.id,
    video_id: row.video_id,
    brand: row.brand,
    platform: row.platform,
    title: row.title,
    description: row.description || "",
    hashtags,
    content_type: row.content_type || "",
    scheduled_at: formatDateTime(row.scheduled_at),
    posted_at: row.posted_at ? formatDateTime(row.posted_at) : null,
    status: row.status,
    platform_post_id: row.platform_post_id || null,
    error_message: row.error_message || null,
  };
}

export function formatDateTime(value) {
  if (!value) return "";
  const raw = String(value).replace(" ", "T");
  const dt = raw.endsWith("Z") ? new Date(raw) : new Date(raw);
  if (Number.isNaN(dt.getTime()))
    return String(value).slice(0, 16).replace("T", " ");
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(dt)
    .replace(" ", " ");
}
