// apps/web/src/app/api/today/route.ts
import { NextResponse } from "next/server";
import { getTopMoves } from "@/lib/queries";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function clamp(limit: number): number {
  const DEFAULT = 10;
  const MIN = 1;
  const MAX = 200;
  if (!Number.isFinite(limit)) return DEFAULT;
  const i = Math.floor(limit);
  if (!Number.isFinite(i)) return DEFAULT;
  return Math.max(MIN, Math.min(MAX, i));
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = clamp(Number(url.searchParams.get("limit") ?? "10"));
  const q = url.searchParams.get("q") ?? "";
  const side = url.searchParams.get("side") ?? "all";

  const rows = await getTopMoves(limit, { q, side });

  return NextResponse.json({
    ok: true,
    limit,
    count: rows.length,
    q: q || null,
    side,
    rows,
  });
}