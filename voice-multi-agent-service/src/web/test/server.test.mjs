import assert from "node:assert/strict";
import test from "node:test";
import { signedInUser, voiceUrl } from "../server.mjs";

test("uses the built-in authentication principal and rejects malformed ones", () => {
  assert.equal(signedInUser({ "x-ms-client-principal-id": "6f1c2a3b-0000-4000-8000-000000000001" }, { NODE_ENV: "production" }), "6f1c2a3b-0000-4000-8000-000000000001");
  assert.equal(signedInUser({ "x-ms-client-principal-id": "../../etc" }, { NODE_ENV: "production" }), undefined);
});

test("fails closed in production without a principal; local runs use a fixed user", () => {
  assert.equal(signedInUser({}, { NODE_ENV: "production" }), undefined);
  assert.equal(signedInUser({}, {}), "local-user");
});

test("builds the voice endpoint from the project endpoint", () => {
  assert.equal(
    voiceUrl({ FOUNDRY_PROJECT_ENDPOINT: "https://acct.services.ai.azure.com/api/projects/p/", VOICE_AGENT_NAME: "card-service-voice" }),
    "wss://acct.services.ai.azure.com/api/projects/p/agents/card-service-voice/endpoint/protocols/voice?api-version=v1",
  );
  assert.throws(() => voiceUrl({ FOUNDRY_PROJECT_ENDPOINT: "http://insecure" }));
});
