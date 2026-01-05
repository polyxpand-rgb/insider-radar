// apps/web/src/lib/db.ts
import "server-only";
import { Pool } from "pg";

type GlobalPg = { __insiderRadarPool?: Pool };
const g = globalThis as unknown as GlobalPg;

const connectionString = process.env.DATABASE_URL ?? process.env.POSTGRES_URL;
if (!connectionString) {
  throw new Error(
    "Missing DATABASE_URL (or POSTGRES_URL). Set it in apps/web/.env.local",
  );
}

export const pool: Pool =
  g.__insiderRadarPool ??
  new Pool({
    connectionString,
    max: 5,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 10_000,
  });

if (process.env.NODE_ENV !== "production") {
  g.__insiderRadarPool = pool;
}