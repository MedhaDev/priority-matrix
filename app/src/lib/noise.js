// Soft white noise for focus sessions, generated in the browser (no audio
// file, works offline). One looping noise buffer runs through a gentle
// low-pass filter (raw white noise is harsh) and a volume control that fades
// in and out, so starting and pausing never clicks.
const VOLUME = 0.22;

let ctx = null;
let gain = null;
let suspendTimer = null;

function context() {
  if (ctx) return ctx;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;
  // iPhone: keep playing when the ring/silent switch is set to silent.
  if (navigator.audioSession) navigator.audioSession.type = "playback";

  ctx = new AudioCtx();
  const buffer = ctx.createBuffer(1, ctx.sampleRate * 4, ctx.sampleRate);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < samples.length; i++) samples[i] = Math.random() * 2 - 1;

  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.loop = true;
  const soften = ctx.createBiquadFilter();
  soften.type = "lowpass";
  soften.frequency.value = 7000;
  gain = ctx.createGain();
  gain.gain.value = 0;
  source.connect(soften).connect(gain).connect(ctx.destination);
  source.start();
  return ctx;
}

function fadeTo(value, seconds) {
  const t = ctx.currentTime;
  gain.gain.cancelScheduledValues(t);
  gain.gain.setValueAtTime(gain.gain.value, t);
  gain.gain.linearRampToValueAtTime(value, t + seconds);
}

// Browsers only allow sound to start from a tap or key press. Call this
// inside the click handler; playNoise() can then run from an effect.
export function unlockNoise() {
  const c = context();
  if (c && c.state !== "running") c.resume();
}

export function playNoise() {
  const c = context();
  if (!c) return;
  clearTimeout(suspendTimer);
  c.resume();
  fadeTo(VOLUME, 0.8);
}

export function stopNoise() {
  if (!ctx) return;
  fadeTo(0, 0.4);
  clearTimeout(suspendTimer);
  // Pause the audio engine after the fade, to save battery.
  suspendTimer = setTimeout(() => ctx.suspend(), 500);
}
