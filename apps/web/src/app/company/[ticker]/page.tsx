// apps/web/src/app/company/[ticker]/page.tsx
import Link from "next/link";
import { getCompanyTransactions } from "@/lib/queries";
import { secFilingIndexUrl } from "@/lib/sec";

export const dynamic = "force-dynamic";
export const revalidate = 0;

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

function fmtPrice(value: string | null) {
  if (!value) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return `$${n.toFixed(2)}`;
}

function fmtDate(value: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString();
}

export default async function CompanyPage({
  params,
}: {
  params: { ticker: string };
}) {
  const ticker = (params.ticker || "").trim().toUpperCase();
  const rows = await getCompanyTransactions(ticker, 200);
  const companyName = rows[0]?.company_name ?? "—";

  return (
    <main className="min-h-screen bg-white text-zinc-900">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex items-center justify-between">
          <div>
            <Link href="/" className="text-sm text-zinc-600 hover:text-zinc-900">
              ← Back
            </Link>

            <h1 className="mt-2 text-2xl font-semibold tracking-tight">
              {ticker} <span className="text-zinc-500">— {companyName}</span>
            </h1>

            <p className="mt-1 text-sm text-zinc-600">
              Latest transactions (max 200)
            </p>
          </div>
        </div>

        <div className="mt-6 overflow-hidden rounded-xl border border-zinc-200">
          <table className="w-full border-collapse">
            <thead className="bg-zinc-50">
              <tr className="text-left text-xs font-medium text-zinc-600">
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Insider</th>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Shares</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Value</th>
                <th className="px-4 py-3">Direct?</th>
                <th className="px-4 py-3">Security</th>
                <th className="px-4 py-3">Filing</th>
              </tr>
            </thead>

            <tbody>
              {rows.map((r, idx) => {
                const filingUrl = secFilingIndexUrl(r.issuer_cik, r.accession_number);

                return (
                  <tr
                    key={`${r.accession_number}-${idx}`}
                    className="border-t border-zinc-200 text-sm hover:bg-zinc-50"
                  >
                    <td className="px-4 py-3">{fmtDate(r.transaction_date)}</td>
                    <td className="px-4 py-3">{r.owner_name ?? "—"}</td>
                    <td className="px-4 py-3">{r.transaction_code ?? "—"}</td>
                    <td className="px-4 py-3">{fmtInt(r.shares)}</td>
                    <td className="px-4 py-3">{fmtPrice(r.price)}</td>
                    <td className="px-4 py-3">{fmtMoneyCompact(r.total_value)}</td>
                    <td className="px-4 py-3">
                      {r.is_direct == null ? "—" : r.is_direct ? "Yes" : "No"}
                    </td>
                    <td className="px-4 py-3">{r.security_title ?? "—"}</td>
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
                    No transactions found for {ticker}.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}