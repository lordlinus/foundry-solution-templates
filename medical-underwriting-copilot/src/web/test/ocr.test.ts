import assert from "node:assert/strict";
import test from "node:test";
import { CASE_ID, caseRecord, lowConfidenceNumbers, newCaseId, tagPages } from "../src/lib/ocr.ts";

test("numbers every page", () => {
  assert.equal(tagPages("one\n<!-- PageBreak -->\ntwo"), "<!-- page 1 -->\none\n\n<!-- page 2 -->\ntwo");
});

test("flags only low-confidence tokens that contain a digit, keeping the worst instance", () => {
  const flags = lowConfidenceNumbers({
    pages: [
      {
        pageNumber: 2,
        words: [
          { content: "glucose", confidence: 0.5 },
          { content: "7.9", confidence: 0.6 },
          { content: "7.9", confidence: 0.4 },
          { content: "146/92", confidence: 0.95 },
        ],
      },
    ],
  });
  assert.deepEqual(flags, [{ text: "7.9", confidence: 0.4, page: 2 }]);
});

test("puts OCR notes before the paged record", () => {
  const record = caseRecord("a", [{ text: "7.9", confidence: 0.4, page: 1 }]);
  assert.match(record, /^OCR notes:[\s\S]*"7.9" on page 1[\s\S]*<!-- page 1 -->\na$/);
});

test("case IDs are safe path segments", () => {
  assert.ok(CASE_ID.test(newCaseId()));
  assert.ok(!CASE_ID.test("../x"));
});
