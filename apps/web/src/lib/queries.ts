// apps/web/src/lib/queries.ts
import { pool } from "./db";

export type TopMoveRow = {
  transaction_date: string;
  issuer_cik: string;
  accession_number: string;
  ticker: string;
  company_name: string;
  owner_name: string | null;
  transaction_code: string | null;
  shares: string | null;
  price: string | null;
  total_value: string | null;
  security_title: string | null;
};

export type CompanyTxnRow = {
  transaction_date: string;
  issuer_cik: string;
  accession_number: string;
  ticker: string | null;
  company_name: string | null;
  owner_name: string | null;
  transaction_code: string | null;
  shares: string | null;
  price: string | null;
  total_value: string | null;
  is_direct: boolean | null;
  security_title: string | null;
};

export type SideFilter = "all" | "buy" | "sell";

function clampLimit(limit: number, def: number, max: number): number {
  if (!Number.isFinite(limit)) return def;
  const i = Math.floor(limit);
  if (!Number.isFinite(i)) return def;
  return Math.max(1, Math.min(max, i));
}

function normalizeSide(value: string | null | undefined): SideFilter {
  const v = (value ?? "").toLowerCase().trim();
  if (v === "buy") return "buy";
  if (v === "sell") return "sell";
  return "all";
}

export async function getTopMoves(
  limit: number,
  opts?: { q?: string | null; side?: SideFilter | string | null },
): Promise<TopMoveRow[]> {
  const safeLimit = clampLimit(limit, 50, 200);
  const q = (opts?.q ?? "").trim();
  const side = normalizeSide(opts?.side ?? "all");

  // Build WHERE conditions safely (no "param type unknown" issues)
  const where: string[] = [];
const params: Array<number | string> = [safeLimit];
  let p = 2;

  // Only show rows that actually have a ticker (clean dashboard)
  where.push("nullif(trim(c1.ticker), '') is not null");

  if (q) {
    params.push(`%${q}%`);
    where.push(
      `(c1.ticker ILIKE $${p} OR c1.name ILIKE $${p} OR a.owner_name ILIKE $${p})`,
    );
    p += 1;
  }

  if (side === "buy") where.push("a.total_value_sum > 0");
  if (side === "sell") where.push("a.total_value_sum < 0");

  const whereSql = where.length ? `where ${where.join(" and ")}` : "";

  const { rows } = await pool.query<TopMoveRow>(
    `
    with c1 as (
      select distinct on (issuer_cik)
        issuer_cik, name, ticker
      from companies
      order by
        issuer_cik,
        (ticker is null or ticker = '') asc,
        id desc
    ),
    tx_norm as (
      select
        t.transaction_date,
        t.issuer_cik,
        t.accession_number,
        nullif(trim(t.owner_name), '') as owner_name,
        nullif(trim(t.transaction_code), '') as transaction_code,
        nullif(trim(t.security_title), '') as security_title,

        nullif(t.shares::text, '')::numeric as shares_num,
        nullif(t.price::text, '')::numeric as price_num,
        nullif(t.total_value::text, '')::numeric as total_value_num
      from transactions t
      where t.transaction_date is not null
    ),
    agg as (
      -- ONE ROW PER COMPANY PER DAY
      select
        x.transaction_date,
        x.issuer_cik,

        sum(x.shares_num) as shares_sum,
        sum(x.total_value_num) as total_value_sum,

        -- weighted avg price (only when price exists)
        case
          when nullif(sum(x.shares_num) filter (where x.price_num is not null), 0) is null then null
          else (
            sum(x.shares_num * x.price_num) /
            nullif(sum(x.shares_num) filter (where x.price_num is not null), 0)
          )
        end as price_wavg,

        max(x.accession_number) as accession_number,
        max(x.owner_name) filter (where x.owner_name is not null) as owner_name,
        max(x.transaction_code) filter (where x.transaction_code is not null) as transaction_code,
        max(x.security_title) filter (where x.security_title is not null) as security_title
      from tx_norm x
      group by x.transaction_date, x.issuer_cik
    )
    select
      a.transaction_date,
      a.issuer_cik,
      a.accession_number,
      c1.ticker,
      c1.name as company_name,
      a.owner_name,
      a.transaction_code,

      to_char(a.shares_sum, 'FM999999999999999999') as shares,
      to_char(a.price_wavg, 'FM9999999990.00') as price,
      to_char(a.total_value_sum, 'FM9999999999999999990.########') as total_value,

      a.security_title
    from agg a
    join c1 on c1.issuer_cik = a.issuer_cik
    ${whereSql}
    order by abs(coalesce(a.total_value_sum, 0)) desc
    limit $1;
    `,
    params,
  );

  return rows;
}

export async function getCompanyTransactions(
  ticker: string,
  limit: number,
): Promise<CompanyTxnRow[]> {
  const safeLimit = clampLimit(limit, 200, 200);
  const tkr = (ticker ?? "").trim().toUpperCase();
  if (!tkr) return [];

  // Resolve ticker -> issuer_cik (latest row)
  const resolved = await pool.query<{ issuer_cik: string }>(
    `
    select issuer_cik
    from companies
    where upper(trim(ticker)) = $1
    order by id desc
    limit 1;
    `,
    [tkr],
  );

  const issuerCik = resolved.rows[0]?.issuer_cik;
  if (!issuerCik) return [];

  // Pull transactions by issuer_cik (this guarantees matching homepage)
  const { rows } = await pool.query<CompanyTxnRow>(
    `
    with c1 as (
      select distinct on (issuer_cik)
        issuer_cik, name, ticker
      from companies
      order by
        issuer_cik,
        (ticker is null or ticker = '') asc,
        id desc
    )
    select
      t.transaction_date,
      t.issuer_cik,
      t.accession_number,
      c1.ticker,
      c1.name as company_name,
      nullif(trim(t.owner_name), '') as owner_name,
      nullif(trim(t.transaction_code), '') as transaction_code,
      to_char(t.shares, 'FM999999999999999999') as shares,
      to_char(t.price, 'FM9999999990.00') as price,
      to_char(t.total_value, 'FM9999999999999999990.########') as total_value,
      t.is_direct,
      nullif(trim(t.security_title), '') as security_title
    from transactions t
    join c1 on c1.issuer_cik = t.issuer_cik
    where t.issuer_cik = $2
      and t.transaction_date is not null
    order by
      t.transaction_date desc,
      abs(coalesce(t.total_value, 0)) desc,
      t.id desc
    limit $1;
    `,
    [safeLimit, issuerCik],
  );

  return rows;
}