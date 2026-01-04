import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// repo root (where docker-compose.yml lives)
const repoRoot = path.resolve(__dirname, "..", "..");
const sqlDir = path.resolve(__dirname, "sql");

function runDockerPsql(args, input = "") {
  const base = [
    "compose",
    "exec",
    "-T",
    "db",
    "psql",
    "-U",
    "postgres",
    "-d",
    "insider_radar",
    "-v",
    "ON_ERROR_STOP=1",
    ...args,
  ];

  const r = spawnSync("docker", base, {
    cwd: repoRoot,
    encoding: "utf8",
    input,
  });

  if (r.error) throw r.error;
  if (r.status !== 0) {
    const msg = (r.stderr || r.stdout || "").trim();
    throw new Error(`psql failed (exit ${r.status}): ${msg}`);
  }

  return (r.stdout || "").trim();
}

function psqlQuery(sql) {
  // -tA = tuples only, unaligned (easy to parse)
  return runDockerPsql(["-tA", "-c", sql]);
}

async function main() {
  // ensure migrations table exists
  runDockerPsql([
    "-c",
    `
    create table if not exists _migrations (
      id bigserial primary key,
      filename text not null unique,
      applied_at timestamptz not null default now()
    );
    `,
  ]);

  const files = fs
    .readdirSync(sqlDir)
    .filter((f) => f.endsWith(".sql"))
    .sort();

  for (const f of files) {
    const safeName = f.replaceAll("'", "''");
    const already = psqlQuery(
      `select 1 from _migrations where filename='${safeName}' limit 1;`
    );

    if (already === "1") {
      console.log("Skipping", f, "(already applied)");
      continue;
    }

    const fullPath = path.join(sqlDir, f);
    let sql = fs.readFileSync(fullPath, "utf8");
    sql = sql.replace(/^\uFEFF/, ""); // strip UTF-8 BOM if present

    console.log("Applying", f);

    // Apply in a transaction and record the migration
    const script = `
begin;
${sql}
insert into _migrations(filename) values ('${safeName}');
commit;
`;

    // Feed script via stdin: psql -f -
    runDockerPsql(["-f", "-"], script);

    console.log("Applied", f);
  }

  console.log("Migrations complete.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

