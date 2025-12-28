-- 001_init.sql
-- Minimal schema for Insider Radar (M1 foundation)

CREATE TABLE IF NOT EXISTS companies (
  id BIGSERIAL PRIMARY KEY,
  issuer_cik TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  ticker TEXT,
  sic TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS insiders (
  id BIGSERIAL PRIMARY KEY,
  owner_cik TEXT,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_cik, name)
);

CREATE TABLE IF NOT EXISTS form4_filings (
  id BIGSERIAL PRIMARY KEY,
  accession_number TEXT NOT NULL UNIQUE,
  issuer_cik TEXT NOT NULL,
  filed_at TIMESTAMPTZ,
  report_period DATE,
  primary_doc TEXT,
  sec_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
  id BIGSERIAL PRIMARY KEY,
  accession_number TEXT NOT NULL,
  issuer_cik TEXT NOT NULL,
  owner_name TEXT NOT NULL,
  transaction_date DATE,
  transaction_code TEXT,
  shares NUMERIC,
  price NUMERIC,
  total_value NUMERIC,
  is_direct BOOLEAN,
  security_title TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (
    accession_number,
    transaction_date,
    transaction_code,
    shares,
    price,
    security_title
  )
);

CREATE INDEX IF NOT EXISTS idx_tx_issuer_date ON transactions (issuer_cik, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_tx_owner ON transactions (owner_name);
