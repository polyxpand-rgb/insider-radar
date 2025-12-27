import { Pool } from "pg";

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

export async function GET() {
  const r = await pool.query("SELECT 1 as ok");
  return Response.json({ web_db_ok: r.rows[0]?.ok === 1 });
}
