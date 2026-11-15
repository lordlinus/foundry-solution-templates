// Web app: serves the voice UI and relays /realtime WebSocket sessions to the Foundry voice agent.
// Container Apps built-in authentication signs users in before any request reaches this process.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { DefaultAzureCredential } from "@azure/identity";
import { WebSocket, WebSocketServer } from "ws";
import { bridge } from "./relay.mjs";
import { CustomerState } from "./tools.mjs";

const PUBLIC = join(fileURLToPath(new URL(".", import.meta.url)), "public");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml" };
const credential = new DefaultAzureCredential();
const customers = new Map(); // signed-in user -> CustomerState (synthetic data, per process)

// Built-in authentication injects this header and replaces any value a client sends. Local runs
// (no NODE_ENV=production) have no sign-in, so they use a fixed user.
export function signedInUser(headers, env = process.env) {
  const principal = String(headers["x-ms-client-principal-id"] ?? "").trim();
  if (principal) return /^[A-Za-z0-9-]{1,64}$/.test(principal) ? principal : undefined;
  return env.NODE_ENV === "production" ? undefined : env.LOCAL_USER_ID || "local-user";
}

export function voiceUrl(env = process.env) {
  const endpoint = (env.FOUNDRY_PROJECT_ENDPOINT || "").replace(/\/$/, "");
  const agent = env.VOICE_AGENT_NAME || "card-service-voice";
  if (!endpoint.startsWith("https://")) throw new Error("FOUNDRY_PROJECT_ENDPOINT must be an https:// project endpoint.");
  return `wss://${endpoint.slice("https://".length)}/agents/${encodeURIComponent(agent)}/endpoint/protocols/voice?api-version=v1`;
}

async function serveStatic(req, res) {
  const path = new URL(req.url, "http://x").pathname;
  const file = path === "/" ? "index.html" : path.slice(1);
  if (!/^[a-z0-9-]+\.(html|js|css|svg)$/.test(file)) return false;
  try {
    const body = await readFile(join(PUBLIC, file));
    res.writeHead(200, { "Content-Type": TYPES[extname(file)], "Cache-Control": "no-store" });
    res.end(body);
    return true;
  } catch {
    return false;
  }
}

const server = createServer(async (req, res) => {
  const path = new URL(req.url, "http://x").pathname;
  if (path === "/api/health") return res.writeHead(200, { "Content-Type": "application/json" }).end('{"status":"ok"}');
  const user = signedInUser(req.headers);
  if (!user) return res.writeHead(401, { "Content-Type": "application/json" }).end('{"error":"Sign-in required."}');
  if (path === "/api/me") {
    const cards = (customers.get(user)?.cards ?? new CustomerState(user).cards).map(({ last4, type, status }) => ({ last4, type, status }));
    return res.writeHead(200, { "Content-Type": "application/json" }).end(JSON.stringify({ cards }));
  }
  if (await serveStatic(req, res)) return;
  res.writeHead(404).end();
});

const sockets = new WebSocketServer({ noServer: true });

server.on("upgrade", async (req, socket, head) => {
  const user = signedInUser(req.headers);
  if (new URL(req.url, "http://x").pathname !== "/realtime" || !user) {
    socket.write("HTTP/1.1 401 Unauthorized\r\n\r\n");
    return socket.destroy();
  }
  let token;
  try {
    token = (await credential.getToken("https://ai.azure.com/.default")).token;
  } catch (err) {
    console.error(JSON.stringify({ user, error: `token: ${err.message}` }));
    socket.write("HTTP/1.1 503 Service Unavailable\r\n\r\n");
    return socket.destroy();
  }
  sockets.handleUpgrade(req, socket, head, (client) => {
    const state = customers.get(user) ?? new CustomerState(user);
    customers.set(user, state);
    const upstream = new WebSocket(voiceUrl(), {
      headers: { Authorization: `Bearer ${token}`, "Foundry-Features": "VoiceAgents=V1Preview" },
    });
    // Log tool calls without transcripts or audio: voice content is sensitive.
    bridge(client, upstream, state, (entry) => console.log(JSON.stringify(entry)));
  });
});

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 8080);
  server.listen(port, () => console.log(`voice web app listening on ${port}`));
}
