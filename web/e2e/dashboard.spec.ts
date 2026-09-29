import { expect, test } from "@playwright/test";

const VIEWS: Array<[string, string]> = [
  ["readiness", "Agent-readiness"],
  ["tasks", "Tasks"],
  ["runs", "Runs"],
  ["evidence", "Evidence"],
  ["policy", "Policy"],
  ["audit", "Audit log"],
  ["health", "Health"],
];

for (const [route, heading] of VIEWS) {
  test(`${route} renders its heading without JS errors`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(`/${route}`);
    await expect(page.locator("h1").first()).toHaveText(heading);
    expect(errors).toEqual([]);
  });
}

test("sidebar navigation visits every view by click", async ({ page }) => {
  await page.goto("/readiness");
  for (const [route, heading, link] of [
    ["readiness", "Agent-readiness", "Readiness"],
    ["tasks", "Tasks", "Tasks"],
    ["runs", "Runs", "Runs"],
    ["evidence", "Evidence", "Evidence"],
    ["policy", "Policy", "Policy"],
    ["audit", "Audit log", "Audit"],
    ["health", "Health", "Health"],
  ] as const) {
    await page.getByRole("link", { name: link, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${route}$`));
    await expect(page.locator("h1").first()).toHaveText(heading);
  }
});

test("runs page renders table when populated or the empty state", async ({ page }) => {
  await page.goto("/runs");
  const empty = page.getByText(/No runs yet/);
  const rows = page.getByRole("link", { name: "stream →" });
  await expect(empty.or(rows.first())).toBeVisible({ timeout: 15_000 });
});
