-- Backfill original_name with AI title (+ existing file extension) for existing rows
-- Date: 2026-03-16

-- PostgreSQL version:
UPDATE videos
SET original_name = CONCAT(
    TRIM(ai_title),
    COALESCE(NULLIF(SUBSTRING(filename FROM '\\.[^\\.]+$'), ''), '')
)
WHERE ai_title IS NOT NULL
  AND TRIM(ai_title) <> '';

-- SQLite fallback (if needed), run manually with care:
-- UPDATE videos
-- SET original_name = TRIM(ai_title) ||
--     CASE
--       WHEN instr(filename, '.') > 0 THEN substr(filename, instr(filename, '.'))
--       ELSE ''
--     END
-- WHERE ai_title IS NOT NULL
--   AND TRIM(ai_title) <> '';
