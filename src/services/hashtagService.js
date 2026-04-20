import { HASHTAGS, GYMARK_VIRAL_HASHTAGS, CONTENT_TYPES, defaultContentTypeForBrand } from "../config.js";

function dedupe(items) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    const key = String(item || "").toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function normalizeHashtag(tag) {
  const text = String(tag || "").trim();
  if (!text) return "";
  return text.startsWith("#") ? text : `#${text}`;
}

export class HashtagService {
  getHashtags(contentType, platform, { brand, count } = {}) {
    const fallbackType = defaultContentTypeForBrand(brand);
    const effectiveType = HASHTAGS[contentType] ? contentType : fallbackType;

    let fixed = [...(HASHTAGS[effectiveType] || HASHTAGS[fallbackType] || [])];
    if (brand === "gymark") fixed = dedupe([...fixed, ...GYMARK_VIRAL_HASHTAGS]);

    let limit = Number.isFinite(Number(count)) ? Number(count) : null;
    if (limit == null && platform === "tiktok" && (brand === "tatuct" || brand === "milita")) limit = 12;
    if (limit == null && brand === "escape") limit = platform === "tiktok" ? 12 : platform === "instagram" ? 10 : fixed.length;
    if (limit == null) limit = fixed.length;

    return fixed.slice(0, Math.max(1, limit)).map(normalizeHashtag).filter(Boolean);
  }

  getContentTypes() {
    return CONTENT_TYPES;
  }
}
