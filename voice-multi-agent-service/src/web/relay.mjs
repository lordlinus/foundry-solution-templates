// Relays one browser voice session to the Foundry voice agent.
//
// Why a relay: browsers cannot set an Authorization header on a WebSocket, and Foundry voice
// sessions need an Entra token. The web app holds that token, so the browser never sees one.
// The relay is also where the card tools run, bound to the signed-in user.

import { TOOL_NAMES, runTool } from "./tools.mjs";

// What a browser may send. Everything else (session.update, tool results, response overrides)
// is dropped, so a modified client cannot change the agent's instructions or fake a tool result.
const AUDIO_EVENTS = new Set([
  "input_audio_buffer.append",
  "input_audio_buffer.commit",
  "input_audio_buffer.clear",
  "response.cancel",
  "conversation.item.truncate",
]);

/** Returns the event to forward upstream, or null to drop it. */
export function filterClientEvent(event) {
  if (!event || typeof event.type !== "string") return null;
  if (AUDIO_EVENTS.has(event.type)) return event;
  if (event.type === "conversation.item.create") {
    const item = event.item ?? {};
    const textOnly =
      item.type === "message" &&
      item.role === "user" &&
      Array.isArray(item.content) &&
      item.content.length > 0 &&
      item.content.every((part) => part?.type === "input_text" && typeof part.text === "string" && part.text.length <= 2000);
    return textOnly ? { type: event.type, item: { type: "message", role: "user", content: item.content.map(({ type, text }) => ({ type, text })) } } : null;
  }
  // A typed message needs a response; strip any overrides the client attached.
  if (event.type === "response.create") return { type: "response.create" };
  return null;
}

/**
 * Bridge a browser socket to an upstream Foundry socket.
 * @param {{ send(data: string): void, close(): void, on(event: string, fn: Function): void }} client
 * @param {{ send(data: string): void, close(): void, on(event: string, fn: Function): void }} upstream
 * @param {import("./tools.mjs").CustomerState} state
 * @param {(entry: object) => void} log
 */
export function bridge(client, upstream, state, log = () => {}) {
  const pending = new Map(); // response_id -> [{ call_id, name, arguments }]
  const queued = [];
  let open = false;

  const toClient = (event) => client.send(typeof event === "string" ? event : JSON.stringify(event));
  const toUpstream = (event) => (open ? upstream.send(JSON.stringify(event)) : queued.push(event));

  upstream.on("open", () => {
    open = true;
    for (const event of queued.splice(0)) upstream.send(JSON.stringify(event));
  });

  upstream.on("message", (data) => {
    const text = data.toString();
    toClient(text);
    let event;
    try {
      event = JSON.parse(text);
    } catch {
      return;
    }
    if (event.type === "response.function_call_arguments.done" && TOOL_NAMES.includes(event.name)) {
      // Handoffs and end_conversation also arrive as function calls; the service runs those.
      const calls = pending.get(event.response_id) ?? [];
      calls.push({ call_id: event.call_id, name: event.name, arguments: event.arguments });
      pending.set(event.response_id, calls);
    } else if (event.type === "response.done") {
      const id = event.response?.id;
      const calls = pending.get(id) ?? [];
      pending.delete(id);
      // Run tools only for a response that completed; a cancelled or failed one never acts.
      if (!calls.length || event.response?.status !== "completed") return;
      for (const call of calls) {
        let args = {};
        try {
          args = JSON.parse(call.arguments || "{}");
        } catch {
          args = {};
        }
        const result = runTool(state, call.name, args);
        log({ user: state.userId, tool: call.name, args, result });
        toClient({ type: "relay.tool", name: call.name, arguments: args, result });
        toUpstream({ type: "conversation.item.create", item: { type: "function_call_output", call_id: call.call_id, output: JSON.stringify(result) } });
      }
      toUpstream({ type: "response.create" });
    }
  });

  client.on("message", (data) => {
    let event;
    try {
      event = JSON.parse(data.toString());
    } catch {
      return;
    }
    const allowed = filterClientEvent(event);
    if (allowed) toUpstream(allowed);
    else toClient({ type: "relay.rejected", rejected_type: String(event?.type ?? "") });
  });

  upstream.on("close", (code, reason) => {
    log({ user: state.userId, upstream_closed: code, reason: String(reason ?? "").slice(0, 200) });
    toClient({ type: "relay.closed", code, reason: String(reason ?? "").slice(0, 200) });
    client.close();
  });
  upstream.on("error", (err) => {
    toClient({ type: "relay.error", message: "The voice service connection failed." });
    log({ user: state.userId, error: String(err?.message ?? err) });
    client.close();
  });
  client.on("close", () => upstream.close());
}
