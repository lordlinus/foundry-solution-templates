// Server-side calls to the Foundry hosted agent: sessions, session files, and background runs.
// Each signed-in user gets one agent session (an isolated sandbox with its own $HOME). Calls carry
// the user's identity in x-ms-user-identity so Foundry scopes the session to that user.
import { AIProjectClient } from "@azure/ai-projects";
import { DefaultAzureCredential } from "@azure/identity";

const credential = new DefaultAzureCredential();
const endpoint = () => required("FOUNDRY_PROJECT_ENDPOINT").replace(/\/$/, "");
const agentName = () => required("FOUNDRY_AGENT_NAME");
let client: AIProjectClient | undefined;
const projects = () => (client ??= new AIProjectClient(endpoint(), credential));
const created = new Set<string>();

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set.`);
  return value;
}

export const sessionId = (user: string) => `u-${user.replace(/[^A-Za-z0-9-]/g, "-")}`.slice(0, 64);
const asUser = (user: string) => ({ requestOptions: { headers: { "x-ms-user-identity": user } } });

export async function ensureSession(user: string): Promise<string> {
  const sid = sessionId(user);
  if (created.has(sid)) return sid;
  const agent = await projects().agents.get(agentName());
  const version = String(agent.versions?.latest?.version ?? "");
  if (!version) throw new Error(`No deployed version of ${agentName()}.`);
  try {
    await projects().agents.createSession(
      agentName(),
      { type: "version_ref", agent_version: version },
      { agentSessionId: sid, ...asUser(user) },
    );
  } catch (err) {
    // 409: the session already exists (an earlier process or replica created it).
    if ((err as { statusCode?: number }).statusCode !== 409) throw err;
  }
  created.add(sid);
  return sid;
}

export async function putFile(user: string, path: string, data: Uint8Array | string): Promise<void> {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
  await projects().agents.uploadSessionFile(agentName(), sessionId(user), path, bytes, asUser(user));
}

export async function getFile(user: string, path: string): Promise<Buffer> {
  const res = await projects().agents.downloadSessionFile(agentName(), sessionId(user), path, asUser(user));
  const stream = (res as { readableStreamBody?: NodeJS.ReadableStream }).readableStreamBody;
  if (!stream) throw new Error(`No content for ${path}.`);
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk as Buffer));
  return Buffer.concat(chunks);
}

async function responses(user: string, path: string, init: RequestInit = {}): Promise<Record<string, unknown>> {
  const { token } = await credential.getToken("https://ai.azure.com/.default");
  const url = `${endpoint()}/agents/${agentName()}/endpoint/protocols/openai/responses${path}?api-version=v1`;
  const res = await fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "x-ms-user-identity": user,
    },
  });
  if (!res.ok) throw new Error(`Foundry responses ${res.status}: ${(await res.text()).slice(0, 300)}`);
  return (await res.json()) as Record<string, unknown>;
}

// A report takes minutes, so it runs in the background and survives the browser leaving.
export async function startRun(user: string, caseId: string): Promise<string> {
  const run = await responses(user, "", {
    method: "POST",
    body: JSON.stringify({
      input: `Underwrite case ${caseId}.`,
      agent_session_id: sessionId(user),
      background: true,
      store: true,
    }),
  });
  return String(run.id);
}

export type Step = { type: string; name: string };
export type RunState = { status: string; steps: Step[]; error?: string };

export async function getRun(user: string, responseId: string): Promise<RunState> {
  const run = await responses(user, `/${encodeURIComponent(responseId)}`);
  const output = (run.output as Array<Record<string, unknown>> | undefined) ?? [];
  const steps = output
    .filter((item) => item.type !== "message" && item.type !== "reasoning")
    .map((item) => ({ type: String(item.type), name: String(item.name ?? item.server_label ?? item.type) }));
  const error = (run.error as { message?: string } | null)?.message;
  return { status: String(run.status), steps, ...(error ? { error } : {}) };
}
