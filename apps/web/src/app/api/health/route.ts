import { Pool } from "pg";

declare global {
  // eslint-disable-next-line no-var
  var __pgPool: Pool | undefined;
}

const pool =
  global.__pgPool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 5,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
  });

global.__pgPool = pool;

export async function GET() {
  try {
    const r = await pool.query("SELECT now() as now, 1 as ok");
    return Response.json({
      ok: true,
      web_db_ok: r.rows[0]?.ok === 1,
      now: r.rows[0]?.now ?? null,
    });
  } catch (err: any) {
    return Response.json(
      {
        ok: false,
        web_db_ok: false,
        error: err?.message ?? String(err),
      },
      { status: 500 }
    );
  }
}