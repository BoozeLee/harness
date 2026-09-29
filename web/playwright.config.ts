import { execFileSync } from "node:child_process";
import { chmodSync, copyFileSync, existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { defineConfig } from "@playwright/test";

const ROOT = import.meta.dirname; // web/
const repoRoot = path.resolve(ROOT, "..");

function mainRepoRoot(): string {
  try {
    const common = execFileSync("git", ["-C", repoRoot, "rev-parse", "--git-common-dir"], { encoding: "utf8" }).trim();
    return path.resolve(repoRoot, common, "..");
  } catch {
    return repoRoot;
  }
}

// A task worktree lacks the gitignored serve.token and `harness serve` would mint a fresh
// one there; copy the main checkout's so the server and the vite bundle agree on one token.
function syncToken(): void {
  const local = path.join(repoRoot, ".ai-engineering", "serve.token");
  if (existsSync(local)) return;
  const main = path.join(mainRepoRoot(), ".ai-engineering", "serve.token");
  if (existsSync(main)) {
    copyFileSync(main, local);
    chmodSync(local, 0o600);
  }
}
syncToken();

// same token the live `harness serve` uses; the vite client bakes it in via import.meta.env
function serveToken(): string {
  if (process.env.VITE_HARNESS_TOKEN) return process.env.VITE_HARNESS_TOKEN;
  try {
    return readFileSync(path.join(repoRoot, ".ai-engineering", "serve.token"), "utf8").trim();
  } catch {
    return "";
  }
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1, // specs mutate the shared dogfood repo (contracts, worktrees) — serialize
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 360_000, // a full UI verify runs pytest+ruff+mypy (+ reviewer) inside a worktree
  use: {
    baseURL: "http://localhost:5173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run harness serve",
      cwd: repoRoot,
      url: "http://127.0.0.1:8766/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      cwd: ROOT,
      env: { VITE_HARNESS_TOKEN: serveToken() },
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
