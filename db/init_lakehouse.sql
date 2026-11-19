-- ====================================================================
-- LAKEHOUSE DATABASE INITIALIZATION (Medallion Architecture)
-- Schemas: BRONZE (Raw) -> SILVER (Cleaned) -> GOLD (Analytics / BI)
-- ====================================================================

-- 1. Buat Schema Medallion
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- ====================================================================
-- LAYER 1: BRONZE (DATA MENTAH / RAW DATA)
-- Prinsip: Purely raw as-is from scraper, no alteration to content.
-- Idempotency: url / urlhash UNIQUE untuk mencegah duplikasi data mentah.
-- ====================================================================
DROP TABLE IF EXISTS bronze.articles CASCADE;

CREATE TABLE bronze.articles (
    id BIGSERIAL PRIMARY KEY,
    urlhash VARCHAR(64) UNIQUE NOT NULL,      -- Hash MD5 / SHA256 dari URL
    url TEXT UNIQUE NOT NULL,                  -- URL lengkap artikel
    id_url VARCHAR(50),                        -- ID unik artikel dari URL (misal: '603139')
    title TEXT,                                -- Judul mentah
    kategori VARCHAR(100),                     -- Kategori mentah
    published_time TEXT,                       -- Tanggal mentah berbentuk string (misal: "19 November 2026, 09:05 |")
    content TEXT,                              -- Isi artikel mentah
    tim_redaksi JSONB DEFAULT '[]'::jsonb,     -- Array of object: [{"href": "...", "text": "...", "bagian": "..."}]
    tags JSONB DEFAULT '[]'::jsonb,            -- Array of object: [{"href": "...", "text": "..."}]
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Waktu scraping
);

-- Index untuk performa pencarian deduplikasi di bronze
CREATE INDEX IF NOT EXISTS idx_bronze_url ON bronze.articles(url);
CREATE INDEX IF NOT EXISTS idx_bronze_urlhash ON bronze.articles(urlhash);
CREATE INDEX IF NOT EXISTS idx_bronze_id_url ON bronze.articles(id_url);


-- ====================================================================
-- LAYER 2: SILVER (DATA BERSIH / TRANSFORMED & VALIDATED)
-- Prinsip: Bersih, null handled, tipe data sesuai (timestamp, array),
--          isi konten normal (tidak ada tag HTML liar/whitespace ganda).
-- ====================================================================
DROP TABLE IF EXISTS silver.articles CASCADE;

CREATE TABLE silver.articles (
    id BIGSERIAL PRIMARY KEY,
    bronze_id BIGINT REFERENCES bronze.articles(id) ON DELETE SET NULL, -- Lineage tracking ke data mentah
    url TEXT UNIQUE NOT NULL,
    id_url VARCHAR(50),
    title TEXT NOT NULL,
    kategori VARCHAR(100) NOT NULL,
    published_date TIMESTAMP WITH TIME ZONE NOT NULL, -- Format datetime standar ISO
    content TEXT NOT NULL,                            -- Teks bersih hasil preprocessing
    author VARCHAR(150),                              -- Reporter / Penulis utama yang sudah diekstrak
    editor VARCHAR(150),                              -- Editor yang sudah diekstrak
    tim_redaksi JSONB DEFAULT '[]'::jsonb,            -- Array of object bersih: [{"text": "...", "bagian": "..."}] (tanpa href)
    tags JSONB DEFAULT '[]'::jsonb,                   -- Array teks string bersih: ["ijazah", "dpr"] (tanpa href)
    word_count INTEGER,                               -- Total kata pada artikel
    char_count INTEGER,                               -- Total karakter artikel
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_silver_kategori ON silver.articles(kategori);
CREATE INDEX IF NOT EXISTS idx_silver_published_date ON silver.articles(published_date);


-- ====================================================================
-- LAYER 3: GOLD (DATA MARTS / AGGREGATION / DATA WAREHOUSE)
-- Prinsip: Siap dikonsumsi untuk visualisasi dashboard (PowerBI / Metabase / Tableau)
-- ====================================================================

-- Tabel 1: Agregasi Harian per Kategori (Tren Berita & Produksi Artikel)
DROP TABLE IF EXISTS gold.daily_article_metrics CASCADE;

CREATE TABLE gold.daily_article_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    kategori VARCHAR(100) NOT NULL,
    total_articles INTEGER DEFAULT 0,
    avg_words_per_article NUMERIC(10, 2) DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_date_kategori UNIQUE (metric_date, kategori)
);

-- Tabel 2: Agregasi Produktivitas Tim Redaksi (Reporter & Editor)
DROP TABLE IF EXISTS gold.editor_team_productivity CASCADE;

CREATE TABLE gold.editor_team_productivity (
    id BIGSERIAL PRIMARY KEY,
    member_name VARCHAR(150) NOT NULL,
    role VARCHAR(50) NOT NULL,              -- 'Reporter' atau 'Editor'
    total_articles INTEGER DEFAULT 0,
    first_article_date DATE,
    latest_article_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_member_role UNIQUE (member_name, role)
);

-- View: View Analitik Berita Terkini untuk Dashboard
CREATE OR REPLACE VIEW gold.v_recent_articles_dashboard AS
SELECT 
    id,
    title,
    kategori,
    author,
    editor,
    published_date,
    word_count,
    url
FROM silver.articles
ORDER BY published_date DESC;
