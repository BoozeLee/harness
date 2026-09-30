const assert = require("node:assert/strict");
const { test } = require("node:test");
const { expandRanges } = require("../dist/src/ranges.js");

test("expands ranges and singles in order", () => {
  assert.deepEqual(expandRanges("1-3,7"), [1, 2, 3, 7]);
});

test("start greater than end throws", () => {
  assert.throws(() => expandRanges("5-2"), Error);
});

test("malformed segments throw", () => {
  assert.throws(() => expandRanges("a-b"), Error);
  assert.throws(() => expandRanges("1-2-3"), Error);
});

test("empty string yields empty array", () => {
  assert.deepEqual(expandRanges(""), []);
});

