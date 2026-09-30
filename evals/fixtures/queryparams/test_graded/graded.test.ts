const assert = require("node:assert/strict");
const { test } = require("node:test");
const { parseQuery } = require("../dist/src/params.js");

test("ignores a leading question mark", () => {
  assert.deepEqual(parseQuery("?a=1&b=2"), { a: "1", b: "2" });
});

test("percent-decodes keys and values", () => {
  assert.deepEqual(parseQuery("greet%20hi=a%20b"), { "greet hi": "a b" });
});

test("duplicate keys keep the last value", () => {
  assert.deepEqual(parseQuery("a=1&a=2"), { a: "2" });
});

test("empty and bare params yield empty strings", () => {
  assert.deepEqual(parseQuery("k="), { k: "" });
  assert.deepEqual(parseQuery("k"), { k: "" });
  assert.deepEqual(parseQuery(""), {});
});

