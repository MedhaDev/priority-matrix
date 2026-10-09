const COLORS = ["#d4512f", "#3f6fc6", "#d8a03a", "#6b9a5e", "#1c1b19"];

// A small, quick burst of squares when a task is completed.
export function spawnConfetti(x, y) {
  const root = document.getElementById("confetti-root");
  if (!root || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  for (let i = 0; i < 10; i++) {
    const el = document.createElement("span");
    el.className = "confetti-piece";
    el.style.left = x + "px";
    el.style.top = y + "px";
    el.style.background = COLORS[i % COLORS.length];
    const angle = (i / 10) * Math.PI * 2 + Math.random() * 0.6;
    const dist = 22 + Math.random() * 26;
    el.style.setProperty("--tx", Math.cos(angle) * dist + "px");
    el.style.setProperty("--ty", Math.sin(angle) * dist + "px");
    root.appendChild(el);
    setTimeout(() => el.remove(), 750);
  }
}

export function confettiAt(el) {
  if (!el) return;
  const r = el.getBoundingClientRect();
  spawnConfetti(r.left + r.width / 2, r.top + r.height / 2);
}
