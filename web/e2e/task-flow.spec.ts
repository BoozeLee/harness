import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";

const repoRoot = path.resolve(import.meta.dirname, "..", "..");
const ae = path.join(repoRoot, ".ai-engineering");

// The golden path must be deterministic: the claude reviewer is opt-in (HARNESS_E2E_REVIEW=1),
// otherwise we flip the contract's review flag before pressing Verify.
const withReviewer = process.env.HARNESS_E2E_REVIEW === "1";
const name = `e2e-${Date.now().toString(36)}`;

test("create task via dialog -> verify streams to PASS -> evidence recorded", async ({ page }) => {
  test.setTimeout(360_000);
  await page.goto("/tasks");

  await page.getByTestId("new-task-button").click();
  await expect(page.getByTestId("new-task-dialog")).toBeVisible();
  await page.getByTestId("task-name").fill(name);
  await page.getByTestId("task-goal").fill("e2e golden path: contract exists and gates pass");
  await page.getByTestId("task-allow").fill("src/**, tests/**");
  await page.getByTestId("task-risk").click();
  await page.getByRole("option", { name: "low", exact: true }).click();
  await page.getByTestId("task-submit").click();

  // dialog closes, card appears, contract file on disk
  await expect(page.getByTestId("new-task-dialog")).toBeHidden({ timeout: 30_000 });
  await expect(page.getByTestId(`verify-${name}`)).toBeVisible({ timeout: 30_000 });
  const cf = path.join(ae, "tasks", `${name}.json`);
  await expect.poll(() => existsSync(cf), { timeout: 30_000 }).toBe(true);
  if (!withReviewer) {
    const c = JSON.parse(readFileSync(cf, "utf8"));
    writeFileSync(cf, JSON.stringify({ ...c, review: false }, null, 2) + "\n");
  }

  await page.getByTestId(`verify-${name}`).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f]{16}$/, { timeout: 30_000 });
  await expect(page.getByTestId("gate-unit")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("run-status")).toHaveText("running", { timeout: 60_000 });
  await expect(page.getByTestId("run-status")).toHaveText("succeeded", { timeout: 300_000 });
  await expect(page.getByTestId("verdict")).toContainText("PASS");

  // run is listed and reachable from the Runs table
  await page.goto("/runs");
  await expect(page.getByRole("link", { name: "stream →" }).first()).toBeVisible();
  await page.goto("/evidence");
  await expect(page.getByText(name).first()).toBeVisible();
});

test.afterAll("remove e2e droppings from the dogfood repo", () => {
  const cf = path.join(ae, "tasks", `${name}.json`);
  if (existsSync(cf)) {
    const wt = JSON.parse(readFileSync(cf, "utf8")).worktree as string;
    try {
      execFileSync("git", ["-C", repoRoot, "worktree", "remove", "--force", wt], { stdio: "pipe" });
    } catch {
      /* worktree may never have been created */
    }
    rmSync(cf, { force: true });
  }
  try {
    execFileSync("git", ["-C", repoRoot, "branch", "-D", `harness/${name}`], { stdio: "pipe" });
  } catch {
    /* branch may be absent */
  }
  rmSync(path.join(ae, "evidence", `${name}.json`), { force: true });
  rmSync(path.join(ae, "evidence", `${name}.html`), { force: true });
});
