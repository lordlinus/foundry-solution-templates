// Card-servicing tools the voice agent calls as native functions. The relay runs them, bound to the
// signed-in user, so the model can never choose whose cards it touches. All data is synthetic.
//
// Every change is two steps: request_card_action stages it and returns an action_id; the change
// happens only in confirm_card_action, and only once per action_id.

import { randomUUID } from "node:crypto";

const SAMPLE_CARDS = [
  { last4: "4821", type: "Debit", status: "active", recent: "3 purchases this week, latest $42.10 at a grocery store" },
  { last4: "7310", type: "Credit", status: "active", recent: "1 purchase this week, $129.99 online" },
];

const ACTIONS = {
  freeze: { from: ["active"], to: "frozen", summary: (c) => `Freeze the ${c.type.toLowerCase()} card ending ${c.last4}. It can be unfrozen later.` },
  unfreeze: { from: ["frozen"], to: "active", summary: (c) => `Unfreeze the ${c.type.toLowerCase()} card ending ${c.last4}.` },
  replace: { from: ["active", "frozen"], to: "replacement_ordered", summary: (c) => `Order a replacement for the ${c.type.toLowerCase()} card ending ${c.last4}. The current card keeps working until the new one arrives.` },
  block_and_replace: { from: ["active", "frozen"], to: "blocked", summary: (c) => `Permanently block the ${c.type.toLowerCase()} card ending ${c.last4} and send a new card with a new number.` },
};

/** One customer's state. The relay keeps one per signed-in user for the life of the process. */
export class CustomerState {
  constructor(userId) {
    this.userId = userId;
    this.cards = SAMPLE_CARDS.map((card) => ({ ...card }));
    this.staged = new Map(); // action_id -> { card_last4, action, reason }
    this.executed = new Map(); // action_id -> result
    this.callbacks = [];
  }

  card(last4) {
    return this.cards.find((c) => c.last4 === String(last4 ?? "").replace(/\D/g, "").slice(-4));
  }
}

export const TOOL_NAMES = ["list_my_cards", "get_card_status", "request_card_action", "confirm_card_action", "request_human_callback"];

/** Run a tool for this customer. Never throws: errors come back as { error } for the agent to say. */
export function runTool(state, name, args = {}) {
  switch (name) {
    case "list_my_cards":
      return { cards: state.cards.map(({ last4, type, status }) => ({ last4, type, status })) };

    case "get_card_status": {
      const card = state.card(args.card_last4);
      return card ? { last4: card.last4, type: card.type, status: card.status, recent_activity: card.recent } : { error: "No card ends with those digits." };
    }

    case "request_card_action": {
      const card = state.card(args.card_last4);
      const rule = ACTIONS[args.action];
      if (!card) return { error: "No card ends with those digits." };
      if (!rule) return { error: `Unknown action ${args.action}.` };
      if (!rule.from.includes(card.status)) return { error: `The card ending ${card.last4} is ${card.status}, so it can't be changed that way.` };
      const actionId = `act-${randomUUID().slice(0, 8)}`;
      state.staged.set(actionId, { card_last4: card.last4, action: args.action, reason: String(args.reason ?? "").slice(0, 200) });
      return { action_id: actionId, status: "awaiting_confirmation", read_back: rule.summary(card), next_step: "Read this back and ask the customer to say yes to confirm." };
    }

    case "confirm_card_action": {
      const id = String(args.action_id ?? "");
      if (state.executed.has(id)) return { ...state.executed.get(id), note: "Already done; nothing was changed again." };
      const staged = state.staged.get(id);
      if (!staged) return { error: "There is no pending action with that id. Stage it with request_card_action first." };
      const card = state.card(staged.card_last4);
      const rule = ACTIONS[staged.action];
      if (!rule.from.includes(card.status)) return { error: `The card ending ${card.last4} is now ${card.status}; nothing was changed.` };
      card.status = rule.to;
      const result = { status: "executed", action: staged.action, card_last4: card.last4, card_status: card.status, reference: `REF-${id.slice(4).toUpperCase()}` };
      state.staged.delete(id);
      state.executed.set(id, result);
      return result;
    }

    case "request_human_callback": {
      if (state.callbacks.length >= 3) return { error: "A callback is already arranged." };
      const reference = `CB-${randomUUID().slice(0, 6).toUpperCase()}`;
      state.callbacks.push({ reference, topic: String(args.topic ?? "").slice(0, 200) });
      return { status: "arranged", reference, expected_within_minutes: 15 };
    }

    default:
      return { error: `Unknown tool ${name}.` };
  }
}
