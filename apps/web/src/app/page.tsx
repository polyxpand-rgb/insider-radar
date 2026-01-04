// apps/web/src/app/page.tsx
import Link from "next/link";
import { getTopMoves } from "@/lib/queries";
import { guessSideFromValue, secFilingIndexUrl } from "@/lib/sec";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type SearchParams = Record<string, string | string[] | undefined>;

function first(sp: SearchParams, key: string): string | undefined {
  const v = sp[key];
  return Array.isArray(v) ? v[0] : v;
}

function fmtMoneyCompact(value: string | null) {
  if (value == null) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";

  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";

  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(2)}K`;
  return `${sign}$${abs.toFixed(2)}`;
}

function fmtInt(value: string | null) {
  const n = value ? Number(value) : NaN;
  if (!Number.isFinite(n)) return "—";
  return Math.round(n).toLocaleString();
}

function fmtDate(value: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString();
}

function clampLimitUi(v: string | undefined): number {
  const n = Number(v ?? "");
  if (!Number.isFinite(n)) return 50;
  return Math.max(1, Math.min(200, Math.floor(n)));
}

export default async function HomePage({
  searchParams,
}: {
  // Next 16+ gives searchParams as a Promise in server components
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;

  const q = (first(sp, "q") ?? "").trim();
  const side = (first(sp, "side") ?? "all").toLowerCase();
  const limit = clampLimitUi(first(sp, "limit"));

  const rows = await getTopMoves(limit, { q, side });

  return (
    <main className="min-h-screen bg-white text-zinc-900">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Insider Radar</h1>
            <p className="mt-1 text-sm text-zinc-600">
              Today — Top moves by value
            </p>
          </div>

          <a
            href="/api/today"
            className="text-sm text-zinc-600 hover:text-zinc-900"
          >
            /api/today
          </a>
        </div>

        {/* Filters */}
        <form method="get" className="mt-6 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-zinc-600">Search (ticker/company/insider)</label>
            <input
              name="q"
              defaultValue={q}
              placeholder="e.g. AXON, Salesforce, Isner…"
              className="h-9 w-72 rounded-md border border-zinc-200 px-3 text-sm outline-none focus:border-zinc-400"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-zinc-600">Side</label>
            <select
              name="side"
              defaultValue={side}
              className="h-9 rounded-md border border-zinc-200 px-3 text-sm outline-none focus:border-zinc-400"
            >
              <option value="all">All</option>
              <option value="buy">Buys only</option>
              <option value="sell">Sells only</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-zinc-600">Limit</label>
            <input
              name="limit"
              type="number"
              min={1}
              max={200}
              defaultValue={limit}
              className="h-9 w-24 rounded-md border border-zinc-200 px-3 text-sm outline-none focus:border-zinc-400"
            />
          </div>

          <button
            type="submit"
            className="h-9 rounded-md border border-zinc-200 bg-zinc-50 px-4 text-sm hover:bg-zinc-100"
          >
            Apply
          </button>

          <Link
            href="/"
            className="h-9 rounded-md border border-transparent px-2 text-sm text-zinc-600 hover:text-zinc-900"
          >
            Reset
          </Link>

          <div className="ml-auto text-xs text-zinc-500">
            Showing {rows.length} row{rows.length === 1 ? "" : "s"}
          </div>
        </form>

        <div className="mt-6 overflow-hidden rounded-xl border border-zinc-200">
          <table className="w-full border-collapse">
            <thead className="bg-zinc-50">
              <tr className="text-left text-xs font-medium text-zinc-600">
                <th className="px-4 py-3">Ticker</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Insider</th>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Shares</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Value</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Filing</th>
              </tr>
            </thead>

            <tbody>
              {rows.map((r, idx) => {
                const filingUrl = secFilingIndexUrl(r.issuer_cik, r.accession_number);
                const sideGuess = guessSideFromValue(r.total_value);

                return (
                  <tr
                    key={`${r.accession_number}-${idx}`}
                    className="border-t border-zinc-200 text-sm hover:bg-zinc-50"
                  >
                    <td className="px-4 py-3">
                      {r.ticker ? (
                        <Link
                          href={`/company/${encodeURIComponent(r.ticker)}`}
                          className="font-medium hover:underline"
                        >
                          {r.ticker}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>

                    <td className="px-4 py-3">
                      {r.ticker ? (
                        <Link
                          href={`/company/${encodeURIComponent(r.ticker)}`}
                          className="hover:underline"
                        >
                          {r.company_name ?? "—"}
                        </Link>
                      ) : (
                        r.company_name ?? "—"
                      )}
                    </td>

                    <td className="px-4 py-3">{r.owner_name ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-2">
                        {r.transaction_code ?? "—"}
                        {sideGuess && (
                          <span
                            className={`rounded-full px-2 py-0.5 text-[11px] ${
                              sideGuess === "buy"
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-rose-50 text-rose-700"
                            }`}
                          >
                            {sideGuess === "buy" ? "BUY" : "SELL"}
                          </span>
                        )}
                      </span>
                    </td>

                    <td className="px-4 py-3">{fmtInt(r.shares)}</td>
                    <td className="px-4 py-3">{r.price ?? "—"}</td>
                    <td className="px-4 py-3">{fmtMoneyCompact(r.total_value)}</td>
                    <td className="px-4 py-3">{fmtDate(r.transaction_date)}</td>

                    <td className="px-4 py-3">
                      {filingUrl ? (
                        <a
                          href={filingUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-zinc-600 hover:text-zinc-900 hover:underline"
                        >
                          View
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}

              {rows.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-sm text-zinc-600" colSpan={9}>
                    No rows returned.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="mt-4 text-xs text-zinc-500">
          Tip: try <code className="rounded bg-zinc-50 px-1 py-0.5">?side=sell</code> or{" "}
          <code className="rounded bg-zinc-50 px-1 py-0.5">?q=AXON</code>
        </p>
      </div>
    </main>
  );
}