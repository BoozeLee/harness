import { readFileSync } from "node:fs";
import path from "node:path";
import { defineConfig } from "@playwright/test";

const ROOT = import.meta.dirname; // web/
const repoRoot = path.resolve(ROOT, "..");

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
