// apps/web/src/app/api/health/route.ts
import { pool } from "@/lib/db";

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return "Unknown error";
  }
}

export async function GET() {
  try {
    const r = await pool.query<{ now: string; ok: number }>(
      "SELECT now() as now, 1 as ok",
    );

    return Response.json({
      ok: true,
      web_db_ok: r.rows[0]?.ok === 1,
      now: r.rows[0]?.now ?? null,
    });
  } catch (err: unknown) {
    return Response.json(
      { ok: false, web_db_ok: false, error: errorMessage(err) },
      { status: 500 },
    );
  }
}