import assert from "node:assert/strict";
import test from "node:test";
import { signedInUser } from "../src/lib/user.ts";

const headers = (h: Record<string, string> = {}) => new Headers(h);

test("uses the built-in authentication principal", () => {
  assert.equal(signedInUser(headers({ "x-ms-client-principal-id": "abc" }), { NODE_ENV: "production" }), "abc");
});

test("fails closed in production without a principal", () => {
  assert.equal(signedInUser(headers(), { NODE_ENV: "production" }), undefined);
});

test("rejects a principal Foundry would not accept as a user identity", () => {
  assert.equal(signedInUser(headers({ "x-ms-client-principal-id": "a b" }), { NODE_ENV: "production" }), undefined);
});
