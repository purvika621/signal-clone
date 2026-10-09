// Executes the same typed API utility used by the temporary page against live servers.
// Node does not enforce browser CORS, so verify the HTTP CORS contract separately.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const source = await readFile(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText;
const { getHealth } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);
const health = await getHealth(AbortSignal.timeout(10000));
assert.deepEqual(health, { status: "ok", database: "ok" });
console.log("PASS: frontend API utility reached the live backend.");

const frontendOrigin = process.env.FRONTEND_ORIGIN || "http://localhost:3000";
const page = await fetch(frontendOrigin, { signal: AbortSignal.timeout(10000) });
assert.equal(page.status, 200);
assert.match(await page.text(), /data-signal-application="true"/);
console.log("PASS: frontend serves the session-aware application over HTTP.");
const foundationPage = await fetch(`${frontendOrigin}/health-check`, { signal: AbortSignal.timeout(10000) });
assert.equal(foundationPage.status, 200);
assert.match(await foundationPage.text(), /Signal Desktop Clone foundation/);
console.log("PASS: the preserved foundation page is available at /health-check.");

const url = `${process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")}/health`;
const allowed = await fetch(url, { headers: { Origin: frontendOrigin }, signal: AbortSignal.timeout(10000) });
assert.equal(allowed.headers.get("access-control-allow-origin"), frontendOrigin);
assert.equal(allowed.headers.get("access-control-allow-credentials"), "true");
const preflight = await fetch(url, {
  method: "OPTIONS",
  headers: { Origin: frontendOrigin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "content-type" },
  signal: AbortSignal.timeout(10000),
});
assert.equal(preflight.status, 200);
assert.equal(preflight.headers.get("access-control-allow-origin"), frontendOrigin);
const denied = await fetch(url, {
  method: "OPTIONS",
  headers: { Origin: "http://untrusted.example", "Access-Control-Request-Method": "GET" },
  signal: AbortSignal.timeout(10000),
});
assert.equal(denied.status, 400);
assert.equal(denied.headers.get("access-control-allow-origin"), null);
console.log("PASS: live CORS allows the configured origin and rejects an unrelated origin.");
console.log("Browser rendering and browser-enforced fetch are separate checks; this command uses Node HTTP.");
