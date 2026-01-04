// apps/web/src/lib/db.ts
import "server-only";
import { Pool } from "pg";

declare global {
  // eslint-disable-next-line no-var
  var __insiderRadarPool: Pool | undefined;
}

function makePool(): Pool {
  const connectionString =
    process.env.DATABASE_URL || process.env.POSTGRES_URL;

  if (!connectionString) {
    throw new Error(
      "Missing DATABASE_URL (or POSTGRES_URL). Set it in apps/web/.env.local",
    );
  }

  return new Pool({
    connectionString,
    max: 5,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 10_000,
  });
}

export const pool: Pool = globalThis.__insiderRadarPool ?? makePool();

if (process.env.NODE_ENV !== "production") {
  globalThis.__insiderRadarPool = pool;
}