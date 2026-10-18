// Background sounds for focus sessions, generated in the browser (no audio
// files, works offline). Each sound is a few seconds of audio computed once,
// made seamless at the loop point, and played on repeat. A master volume fades
// in and out, so starting, pausing and switching never click.
export const SOUNDS = [
  { id: "white", label: "White" },
  { id: "brown", label: "Brown" },
  { id: "rain", label: "Rain" },
  { id: "ocean", label: "Ocean" },
];

const VOLUME = 0.5;
const SECONDS = 12;      // length of each loop
const SEAM = 0.5;        // seconds blended across the loop point

let ctx = null;
let master = null;
let current = null;      // { id, source, gain }
let suspendTimer = null;
const buffers = {};

// Low-pass / high-pass filters, one sample at a time.
const lowpass = (x, prev, k) => prev + k * (x - prev);

function generate(id, n, rate) {
  const out = new Float32Array(n);
  const rand = () => Math.random() * 2 - 1;

  if (id === "white") {
    let lp = 0;
    for (let i = 0; i < n; i++) out[i] = lp = lowpass(rand(), lp, 0.6); // take the edge off
  }

  if (id === "brown") {
    let b = 0;
    for (let i = 0; i < n; i++) out[i] = b = (b + 0.02 * rand()) / 1.02;
  }

  if (id === "rain") {
    // A soft hiss of steady rain, plus thousands of tiny droplets.
    let lp = 0, hp = 0;
    for (let i = 0; i < n; i++) {
      lp = lowpass(rand(), lp, 0.35);
      hp = lowpass(lp, hp, 0.02);
      out[i] = (lp - hp) * 0.6;
    }
    const drops = Math.round((n / rate) * 120);
    for (let d = 0; d < drops; d++) {
      const start = Math.floor(Math.random() * n);
      const len = Math.floor(rate * (0.004 + Math.random() * 0.012));
      const amp = 0.15 + Math.random() ** 3 * 0.9;
      let dp = 0;
      for (let j = 0; j < len && start + j < n; j++) {
        dp = lowpass(rand(), dp, 0.5);
        out[start + j] += dp * amp * Math.exp((-5 * j) / len);
      }
    }
  }

  if (id === "ocean") {
    // Brown noise that swells and recedes: three waves of uneven size per loop.
    let b = 0, lp = 0;
    const waves = [0.7, 1, 0.85];
    for (let i = 0; i < n; i++) {
      b = (b + 0.02 * rand()) / 1.02;
      lp = lowpass(rand(), lp, 0.08);
      const pos = (i / n) * waves.length;
      const swell = Math.sin(Math.PI * (pos % 1)) ** 2 * waves[Math.floor(pos)];
      out[i] = b * (0.35 + swell) + lp * 0.25 * swell;
    }
  }
  return out;
}

function buffer(id) {
  if (buffers[id]) return buffers[id];
  const rate = ctx.sampleRate;
  const n = SECONDS * rate;
  const fade = Math.floor(SEAM * rate);
  const raw = generate(id, n + fade, rate);

  // Blend the extra tail into the start so the loop has no seam.
  const data = raw.subarray(0, n);
  for (let i = 0; i < fade; i++) {
    const t = i / fade;
    data[i] = data[i] * Math.sqrt(t) + raw[n + i] * Math.sqrt(1 - t);
  }
  // Even out loudness between sounds.
  let sum = 0;
  for (let i = 0; i < n; i++) sum += data[i] * data[i];
  const scale = 0.2 / Math.sqrt(sum / n);
  for (let i = 0; i < n; i++) data[i] = Math.max(-1, Math.min(1, data[i] * scale));

  const buf = ctx.createBuffer(1, n, rate);
  buf.copyToChannel(data, 0);
  return (buffers[id] = buf);
}

function context() {
  if (ctx) return ctx;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;
  // iPhone: keep playing when the ring/silent switch is set to silent.
  if (navigator.audioSession) navigator.audioSession.type = "playback";
  ctx = new AudioCtx();
  master = ctx.createGain();
  master.gain.value = 0;
  master.connect(ctx.destination);
  return ctx;
}

function ramp(param, value, seconds) {
  const t = ctx.currentTime;
  param.cancelScheduledValues(t);
  param.setValueAtTime(param.value, t);
  param.linearRampToValueAtTime(value, t + seconds);
}

// Swap the looping sound, crossfading from the old one.
function switchTo(id) {
  if (current?.id === id) return;
  const old = current;
  if (old) {
    ramp(old.gain.gain, 0, 0.4);
    old.source.stop(ctx.currentTime + 0.45);
  }
  const source = ctx.createBufferSource();
  source.buffer = buffer(id);
  source.loop = true;
  const gain = ctx.createGain();
  gain.gain.value = old ? 0 : 1;
  source.connect(gain).connect(master);
  source.start();
  if (old) ramp(gain.gain, 1, 0.4);
  current = { id, source, gain };
}

// Browsers only allow sound to start from a tap or key press. Call this
// inside the click handler; playNoise() can then run from an effect.
export function unlockNoise() {
  const c = context();
  if (c && c.state !== "running") c.resume();
}

export function playNoise(id) {
  const c = context();
  if (!c) return;
  clearTimeout(suspendTimer);
  c.resume();
  switchTo(id);
  ramp(master.gain, VOLUME, 0.8);
}

export function stopNoise() {
  if (!ctx) return;
  ramp(master.gain, 0, 0.4);
  clearTimeout(suspendTimer);
  // Pause the audio engine after the fade, to save battery.
  suspendTimer = setTimeout(() => ctx.suspend(), 500);
}
