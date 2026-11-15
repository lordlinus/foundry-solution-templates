import assert from "node:assert/strict";
import test from "node:test";
import { CustomerState, runTool } from "../tools.mjs";

test("a card change happens only after confirmation, and only once", () => {
  const state = new CustomerState("alice");
  const staged = runTool(state, "request_card_action", { card_last4: "4821", action: "freeze", reason: "misplaced" });
  assert.equal(staged.status, "awaiting_confirmation");
  assert.equal(state.card("4821").status, "active", "staging must not change the card");

  const done = runTool(state, "confirm_card_action", { action_id: staged.action_id });
  assert.equal(done.status, "executed");
  assert.equal(state.card("4821").status, "frozen");

  const again = runTool(state, "confirm_card_action", { action_id: staged.action_id });
  assert.equal(again.status, "executed");
  assert.match(again.note, /Already done/);
  assert.equal(state.executed.size, 1);
});

test("confirming an action that was never staged changes nothing", () => {
  const state = new CustomerState("alice");
  assert.ok(runTool(state, "confirm_card_action", { action_id: "act-made-up" }).error);
  assert.deepEqual(state.cards.map((c) => c.status), ["active", "active"]);
});

test("customers cannot confirm each other's actions", () => {
  const alice = new CustomerState("alice");
  const bob = new CustomerState("bob");
  const staged = runTool(alice, "request_card_action", { card_last4: "7310", action: "block_and_replace", reason: "stolen" });
  assert.ok(runTool(bob, "confirm_card_action", { action_id: staged.action_id }).error);
  assert.equal(alice.card("7310").status, "active");
});

test("invalid transitions and unknown cards are refused", () => {
  const state = new CustomerState("alice");
  assert.ok(runTool(state, "request_card_action", { card_last4: "4821", action: "unfreeze", reason: "x" }).error);
  assert.ok(runTool(state, "request_card_action", { card_last4: "0000", action: "freeze", reason: "x" }).error);
  assert.ok(runTool(state, "request_card_action", { card_last4: "4821", action: "close_account", reason: "x" }).error);
});

test("cards are referred to by last four digits even if a longer number is spoken", () => {
  const state = new CustomerState("alice");
  assert.equal(runTool(state, "get_card_status", { card_last4: "card ending 4 8 2 1" }).last4, "4821");
});
