-- Remove legacy ai_hashtags column from videos table
-- Date: 2026-03-16

-- PostgreSQL / Railway
ALTER TABLE videos DROP COLUMN IF EXISTS ai_hashtags;

-- SQLite (fallback when DROP COLUMN is not supported by your SQLite version):
-- 1) CREATE TABLE videos_new with the same schema as videos but WITHOUT ai_hashtags
-- 2) INSERT INTO videos_new (id, filename, original_name, brand, file_path, file_size, duration, thumbnail, uploaded_at, category_id, ai_title, ai_description)
--    SELECT id, filename, original_name, brand, file_path, file_size, duration, thumbnail, uploaded_at, category_id, ai_title, ai_description
--    FROM videos;
-- 3) DROP TABLE videos;
-- 4) ALTER TABLE videos_new RENAME TO videos;
