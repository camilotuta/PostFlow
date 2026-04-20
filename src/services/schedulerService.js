import { db, rowToPost } from "../db.js";
import {
  ACTIVE_POST_STATES,
  DAILY_PLATFORM_LIMITS,
  DAILY_TOTAL_LIMITS,
  SCHEDULE_SLOTS,
  brandTimezone,
  defaultContentTypeForBrand,
  BRANDS,
} from "../config.js";

function parseSlot(slot) {
  if (typeof slot === "number") return [slot, 0];
  if (typeof slot === "string" && slot.includes(":")) {
    const [h, m] = slot.split(":");
    return [Number(h), Number(m)];
  }
  return [Number(slot || 10), 0];
}

function toUtcIsoFromBrand(brand, dateObj) {
  const locale = dateObj.toLocaleString("sv-SE", { timeZone: brandTimezone(brand) }).replace(" ", "T");
  const fakeLocal = new Date(locale);
  return fakeLocal.toISOString();
}

function nowInBrandTime(brand) {
  const local = new Date().toLocaleString("sv-SE", { timeZone: brandTimezone(brand) }).replace(" ", "T");
  return new Date(local);
}

export class SchedulerService {
  constructor() {
    this._timer = null;
  }

  start() {
    if (this._timer) return;
    this._timer = setInterval(() => this.processDuePosts(), 60_000);
  }

  stop() {
    if (!this._timer) return;
    clearInterval(this._timer);
    this._timer = null;
  }

  getNextBestTime({ platform, after, contentType, brand, extraBrandDayCounts = {}, extraPlatformDayCounts = {}, searchDays = 120 }) {
    const baseType = SCHEDULE_SLOTS[contentType] ? contentType : defaultContentTypeForBrand(brand);
    const table = SCHEDULE_SLOTS[baseType]?.[platform] || SCHEDULE_SLOTS[baseType]?.tiktok || {};
    const now = after ? new Date(after) : nowInBrandTime(brand);

    for (let daysAhead = 0; daysAhead < searchDays; daysAhead += 1) {
      const candidateDay = new Date(now);
      candidateDay.setDate(now.getDate() + daysAhead);
      const weekday = (candidateDay.getDay() + 6) % 7; // monday=0
      const slots = table[weekday] || [];
      for (const s of slots) {
        const [hour, minute] = parseSlot(s);
        const local = new Date(candidateDay);
        local.setHours(hour, minute, 0, 0);
        if (local.getTime() <= now.getTime() + 5 * 60 * 1000) continue;

        const dayKey = local.toISOString().slice(0, 10);
        const platKey = `${dayKey}:${platform}`;
        const limit = this.checkDailyLimits({
          brand,
          platform,
          scheduledAt: local,
          extraBrandDay: extraBrandDayCounts[dayKey] || 0,
          extraPlatformDay: extraPlatformDayCounts[platKey] || 0,
        });
        if (!limit.allowed) continue;
        return local;
      }
    }
    throw new Error(`No hay horarios disponibles para ${platform} en ${brand} dentro de ${searchDays} días.`);
  }

  checkDailyLimits({ brand, platform, scheduledAt, extraBrandDay = 0, extraPlatformDay = 0 }) {
    const target = new Date(scheduledAt);
    const dayStart = new Date(target);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(dayStart);
    dayEnd.setDate(dayEnd.getDate() + 1);

    const startIso = toUtcIsoFromBrand(brand, dayStart);
    const endIso = toUtcIsoFromBrand(brand, dayEnd);

    const brandDayCount = db.prepare(`
      SELECT COUNT(*) AS total FROM posts
      WHERE brand = ? AND status IN (${ACTIVE_POST_STATES.map(() => "?").join(",")})
        AND scheduled_at >= ? AND scheduled_at < ?
    `).get(brand, ...ACTIVE_POST_STATES, startIso, endIso).total;

    const brandLimit = DAILY_TOTAL_LIMITS[brand];
    if (brandLimit != null && brandDayCount + extraBrandDay >= brandLimit) {
      return { allowed: false, error: `Límite diario alcanzado para ${brand}: máximo ${brandLimit} posts/día` };
    }

    const platformDayCount = db.prepare(`
      SELECT COUNT(*) AS total FROM posts
      WHERE brand = ? AND platform = ? AND status IN (${ACTIVE_POST_STATES.map(() => "?").join(",")})
        AND scheduled_at >= ? AND scheduled_at < ?
    `).get(brand, platform, ...ACTIVE_POST_STATES, startIso, endIso).total;

    const platformLimit = DAILY_PLATFORM_LIMITS[brand]?.[platform];
    if (platformLimit != null && platformDayCount + extraPlatformDay >= platformLimit) {
      return { allowed: false, error: `Límite diario alcanzado para ${brand} en ${platform}: máximo ${platformLimit}/día` };
    }

    return { allowed: true, error: null };
  }

  getSchedulePreview({ platforms, contentType, brand }) {
    const preview = {};
    for (const platform of platforms) {
      const slots = [];
      let after = null;
      for (let i = 0; i < 3; i += 1) {
        const date = this.getNextBestTime({ platform, after, contentType, brand });
        slots.push(date.toLocaleString("es-CO", { weekday: "long", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }));
        after = new Date(date.getTime() + 10 * 60 * 1000);
      }
      preview[platform] = slots;
    }
    return preview;
  }

  processDuePosts() {
    for (const brand of Object.keys(BRANDS)) {
      const now = new Date().toISOString();
      const due = db.prepare(
        `SELECT * FROM posts WHERE status = 'scheduled' AND brand = ? AND scheduled_at <= ?`
      ).all(brand, now);
      for (const post of due) this.publishPost(post.id);
    }
  }

  publishPost(postId) {
    const post = db.prepare("SELECT * FROM posts WHERE id = ?").get(postId);
    if (!post) return null;

    db.prepare("UPDATE posts SET status = 'posting' WHERE id = ?").run(postId);
    const publishId = `demo-${post.platform}-${post.id}`;
    db.prepare(
      "UPDATE posts SET status = 'published', posted_at = ?, platform_post_id = ?, error_message = NULL WHERE id = ?"
    ).run(new Date().toISOString(), publishId, postId);

    const updated = db.prepare("SELECT * FROM posts WHERE id = ?").get(postId);
    return rowToPost(updated);
  }
}
