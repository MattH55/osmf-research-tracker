-- Hospital Ranking — PostgreSQL schema (PostGIS optional for production)
-- Run: psql $DATABASE_URL -f db/schema.sql

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS procedures (
  id            TEXT PRIMARY KEY,
  slug          TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  plain_name    TEXT NOT NULL,
  description   TEXT,
  cpt_codes     TEXT[] NOT NULL DEFAULT '{}',
  drg_codes     TEXT[] NOT NULL DEFAULT '{}',
  category      TEXT NOT NULL,
  is_shoppable  BOOLEAN NOT NULL DEFAULT TRUE,
  search_terms  TEXT[] NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hospitals (
  id                    TEXT PRIMARY KEY,
  cms_provider_id       TEXT UNIQUE,
  npi                   TEXT,
  name                  TEXT NOT NULL,
  address               TEXT NOT NULL,
  city                  TEXT NOT NULL,
  state                 CHAR(2) NOT NULL,
  zip                   CHAR(5) NOT NULL,
  phone                 TEXT,
  website               TEXT,
  shoppable_url         TEXT,
  latitude              DOUBLE PRECISION NOT NULL,
  longitude             DOUBLE PRECISION NOT NULL,
  location              GEOGRAPHY(POINT, 4326),
  cms_overall_stars     NUMERIC(2,1),
  hcahps_summary        NUMERIC(4,1),
  readmission_rate      NUMERIC(5,2),
  mortality_rate        NUMERIC(5,2),
  safety_rating         NUMERIC(2,1),
  data_vintage          DATE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hospitals_zip ON hospitals (zip);
CREATE INDEX IF NOT EXISTS idx_hospitals_state ON hospitals (state);
CREATE INDEX IF NOT EXISTS idx_hospitals_location ON hospitals USING GIST (location);

CREATE TABLE IF NOT EXISTS procedure_prices (
  id                      TEXT PRIMARY KEY,
  hospital_id             TEXT NOT NULL REFERENCES hospitals (id) ON DELETE CASCADE,
  procedure_id            TEXT NOT NULL REFERENCES procedures (id) ON DELETE CASCADE,
  cash_price_low          INTEGER,
  cash_price_median       INTEGER,
  cash_price_high         INTEGER,
  negotiated_median       INTEGER,
  negotiated_low          INTEGER,
  negotiated_high         INTEGER,
  estimated_oop_uninsured INTEGER,
  estimated_oop_ppo       INTEGER,
  estimated_oop_hdhp        INTEGER,
  price_source            TEXT NOT NULL DEFAULT 'sample',
  price_vintage           DATE,
  mrf_url                 TEXT,
  UNIQUE (hospital_id, procedure_id)
);

CREATE INDEX IF NOT EXISTS idx_prices_procedure ON procedure_prices (procedure_id);
CREATE INDEX IF NOT EXISTS idx_prices_hospital ON procedure_prices (hospital_id);

CREATE TABLE IF NOT EXISTS data_refresh_log (
  id            SERIAL PRIMARY KEY,
  source        TEXT NOT NULL,
  status        TEXT NOT NULL,
  records       INTEGER,
  message       TEXT,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at   TIMESTAMPTZ
);