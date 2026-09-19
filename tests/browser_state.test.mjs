import test from "node:test";
import assert from "node:assert/strict";

import { createReadGeneration, clearSubmittedDraft } from "../web/request-state.js";

test("only the newest read generation may publish", () => {
  const reads = createReadGeneration();
  const slowOlderRead = reads.begin();
  const newerRead = reads.begin();

  assert.equal(reads.isCurrent(slowOlderRead), false);
  assert.equal(reads.isCurrent(newerRead), true);
});

test("a completed save clears only fields that still contain the submitted draft", () => {
  const fields = {
    title: { value: "Submitted title" },
    body: { value: "A newer draft typed while saving" },
    tags: { value: "research" },
  };
  const submitted = {
    title: "Submitted title",
    body: "Original body",
    tags: "research",
  };

  clearSubmittedDraft(fields, submitted);

  assert.equal(fields.title.value, "");
  assert.equal(fields.body.value, "A newer draft typed while saving");
  assert.equal(fields.tags.value, "");
});
