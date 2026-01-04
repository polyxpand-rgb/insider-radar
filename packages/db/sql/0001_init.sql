-- packages/db/sql/0001_init.sql
-- Safe, idempotent baseline schema

create table if not exists companies (
  id bigserial primary key,
  issuer_cik text not null,
  name text not null,
  ticker text null,
  created_at timestamptz not null default now()
);

create index if not exists idx_companies_issuer_cik on companies(issuer_cik);
create index if not exists idx_companies_ticker on companies(ticker);

create table if not exists transactions (
  id bigserial primary key,
  issuer_cik text not null,
  accession_number text not null,
  transaction_date timestamptz null,
  owner_name text null,
  transaction_code text null,
  shares text null,
  price text null,
  total_value text null,
  security_title text null,
  is_direct boolean null,
  created_at timestamptz not null default now()
);

create index if not exists idx_tx_issuer_cik on transactions(issuer_cik);
create index if not exists idx_tx_date on transactions(transaction_date);
create index if not exists idx_tx_accession on transactions(accession_number);
