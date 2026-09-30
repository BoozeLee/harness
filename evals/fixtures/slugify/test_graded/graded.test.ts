const assert = require("node:assert/strict");
const { test } = require("node:test");
const { slugify } = require("../dist/src/slugify.js");

test("lowercases and hyphenates", () => {
  assert.equal(slugify("Hello Big World"), "hello-big-world");
});

test("drops characters outside a-z0-9-", () => {
  assert.equal(slugify("Café & Co., 2024!"), "caf-co-2024");
});

test("collapses runs and strips edge hyphens", () => {
  assert.equal(slugify("  --a--b--  "), "a-b");
});

test("empty or symbol-only input yields empty string", () => {
  assert.equal(slugify(""), "");
  assert.equal(slugify("!!! ???"), "");
});

