// Browser side of the voice call: microphone -> relay -> Foundry voice agent -> speaker.
// The browser holds no Azure token; it talks only to this app's /realtime relay.

const STAGES = { $entrypoint: "Triage", card_services: "Card services", urgent_support: "Urgent support", end: "Ended" };
const $ = (id) => document.getElementById(id);

// Separate contexts: queued agent playback must never slow down microphone capture.
let ws, audio, capture, mic, micSource, worklet, sink;
let playhead = 0;
let playing = [];
let stage = "$entrypoint";
let speechStoppedAt = 0;
let awaitingFirstAudio = false;
const latencies = [];
// Recorded events for automated tests; transcripts stay in this page only.
window.voiceLog = [];

function setStatus(text) {
  $("status").textContent = text;
}

function addTurn(kind, text, who) {
  const div = document.createElement("div");
  div.className = `turn ${kind}`;
  div.dataset.stage = stage;
  div.innerHTML = `<div class="who"></div><div class="text"></div>`;
  div.querySelector(".who").textContent = who;
  div.querySelector(".text").textContent = text;
  $("transcript").append(div);
  $("transcript").scrollTop = $("transcript").scrollHeight;
}

function showStage(id) {
  stage = id;
  for (const li of document.querySelectorAll(".stages li")) li.classList.toggle("active", li.dataset.stage === id);
}

async function refreshCards() {
  const res = await fetch("/api/me");
  if (!res.ok) return;
  const { cards } = await res.json();
  $("cards").replaceChildren(...cards.map((c) => Object.assign(document.createElement("li"), { textContent: `${c.type} •••• ${c.last4}: ${c.status}` })));
}

function base64ToInt16(b64) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Int16Array(bytes.buffer);
}

function int16ToBase64(samples) {
  const bytes = new Uint8Array(samples.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

function play(b64) {
  const pcm = base64ToInt16(b64);
  const buffer = audio.createBuffer(1, pcm.length, 24000);
  const channel = buffer.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 0x8000;
  const source = audio.createBufferSource();
  source.buffer = buffer;
  source.connect(audio.destination);
  playhead = Math.max(playhead, audio.currentTime + 0.02);
  source.start(playhead);
  playhead += buffer.duration;
  playing.push(source);
  source.onended = () => (playing = playing.filter((s) => s !== source));
}

// Barge-in: when the caller starts talking, stop what is queued to play.
function stopPlayback() {
  for (const source of playing) source.stop();
  playing = [];
  playhead = 0;
}

function send(event) {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(event));
}

function onEvent(event) {
  const entry = { type: event.type, t: Math.round(performance.now()) };
  switch (event.type) {
    case "session.created":
      setStatus("Connected");
      break;
    case "input_audio_buffer.speech_started":
      stopPlayback();
      setStatus("Listening…");
      break;
    case "input_audio_buffer.speech_stopped":
      speechStoppedAt = performance.now();
      awaitingFirstAudio = true;
      setStatus("Thinking…");
      break;
    case "response.output_audio.delta":
      if (awaitingFirstAudio && speechStoppedAt) {
        const ms = Math.round(performance.now() - speechStoppedAt);
        latencies.push(ms);
        entry.ttfa_ms = ms;
        const sorted = [...latencies].sort((a, b) => a - b);
        $("latency").textContent = `Time to first audio: last ${ms} ms, median ${sorted[Math.floor(sorted.length / 2)]} ms (${sorted.length} turns)`;
        awaitingFirstAudio = false;
      }
      setStatus("Speaking…");
      play(event.delta);
      break;
    case "conversation.item.input_audio_transcription.completed":
      entry.transcript = event.transcript;
      addTurn("user", event.transcript, "You");
      break;
    case "response.output_audio_transcript.done":
      entry.transcript = event.transcript;
      entry.stage = stage;
      addTurn("agent", event.transcript, STAGES[stage] ?? stage);
      break;
    case "session.handoff.completed":
      entry.from = event.from_node_id;
      entry.to = event.to_node_id;
      showStage(event.to_node_id);
      addTurn("system", `Transferred to ${STAGES[event.to_node_id] ?? event.to_node_id}`, "");
      break;
    case "relay.tool": {
      entry.name = event.name;
      entry.arguments = event.arguments;
      entry.result = event.result;
      if (event.name === "confirm_card_action" || event.name === "request_human_callback" || event.name === "request_card_action") {
        const r = event.result;
        const text = r.error ? `${event.name}: ${r.error}` : r.status === "awaiting_confirmation" ? `Awaiting your yes: ${r.read_back}` : `${r.action ?? "callback"} ${r.status} ${r.reference ?? ""}`;
        $("actions").append(Object.assign(document.createElement("li"), { textContent: text }));
      }
      refreshCards();
      break;
    }
    case "response.done":
      if (playing.length === 0) setStatus("Listening…");
      break;
    case "relay.closed":
      entry.message = `closed ${event.code} ${event.reason}`;
      break;
    case "error":
    case "relay.error":
    case "relay.rejected":
      entry.message = event.error?.message ?? event.message ?? event.rejected_type;
      addTurn("system", `Problem: ${entry.message}`, "");
      break;
    default:
      return;
  }
  window.voiceLog.push(entry);
}

async function start() {
  $("start").disabled = true;
  setStatus("Connecting…");
  audio = new AudioContext({ sampleRate: 24000 });
  capture = new AudioContext({ sampleRate: 24000 });
  await capture.audioWorklet.addModule("pcm-worklet.js");
  // The agent cancels echo and suppresses noise server-side; stacking the browser's versions on top
  // can mute the caller while the agent is speaking.
  mic = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: true } });
  worklet = new AudioWorkletNode(capture, "pcm-capture");
  // Keep references to every node in the capture graph and connect it to the output through a
  // muted gain. Otherwise Chrome may garbage-collect the source or stop pulling the worklet,
  // and the agent stops hearing the caller partway through a call.
  capture.onstatechange = () => window.voiceLog.push({ type: "audio.state", state: capture.state, t: Math.round(performance.now()) });
  for (const track of mic.getAudioTracks()) {
    for (const name of ["ended", "mute", "unmute"]) track.addEventListener(name, () => window.voiceLog.push({ type: `mic.${name}`, t: Math.round(performance.now()) }));
  }
  micSource = capture.createMediaStreamSource(mic);
  sink = capture.createGain();
  sink.gain.value = 0;
  micSource.connect(worklet).connect(sink).connect(capture.destination);
  worklet.port.onmessage = ({ data }) => {
    window.audioChunksSent = (window.audioChunksSent ?? 0) + 1;
    window.lastChunkAt = Math.round(performance.now());
    send({ type: "input_audio_buffer.append", audio: int16ToBase64(data) });
  };

  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/realtime`);
  ws.onmessage = ({ data }) => onEvent(JSON.parse(data));
  ws.onclose = (e) => {
    window.voiceLog.push({ type: "ws.close", code: e.code, t: Math.round(performance.now()) });
    setStatus("Call ended");
    stop();
  };
  ws.onerror = () => setStatus("Connection failed");
  $("stop").disabled = false;
  showStage("$entrypoint");
}

function stop() {
  ws?.close();
  mic?.getTracks().forEach((t) => t.stop());
  micSource?.disconnect();
  worklet?.disconnect();
  sink?.disconnect();
  capture?.close();
  stopPlayback();
  $("start").disabled = false;
  $("stop").disabled = true;
}

$("start").onclick = () => start().catch((err) => setStatus(`Could not start: ${err.message}`));
$("stop").onclick = stop;
$("say").onsubmit = (e) => {
  e.preventDefault();
  const text = $("text").value.trim();
  if (!text) return;
  addTurn("user", text, "You (typed)");
  send({ type: "conversation.item.create", item: { type: "message", role: "user", content: [{ type: "input_text", text }] } });
  send({ type: "response.create" });
  $("text").value = "";
};
refreshCards();
