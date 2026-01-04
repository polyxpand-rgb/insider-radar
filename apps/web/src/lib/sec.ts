// apps/web/src/lib/sec.ts

export function secFilingIndexUrl(
  issuerCik: string | null,
  accessionNumber: string | null,
): string | null {
  const cikRaw = (issuerCik ?? "").trim();
  const acc = (accessionNumber ?? "").trim();
  if (!cikRaw || !acc) return null;

  const cikInt = String(Number(cikRaw)); // strips leading zeros safely
  const accNoDashes = acc.replace(/-/g, "");

  if (!cikInt || !accNoDashes) return null;

  // Example:
  // https://www.sec.gov/Archives/edgar/data/1108524/000110852425000236/0001108524-25-000236-index.html
  return `https://www.sec.gov/Archives/edgar/data/${cikInt}/${accNoDashes}/${acc}-index.html`;
}

export function guessSideFromValue(totalValue: string | null): "buy" | "sell" | null {
  if (!totalValue) return null;
  const n = Number(totalValue);
  if (!Number.isFinite(n)) return null;
  if (n === 0) return null;
  return n > 0 ? "buy" : "sell";
}