// Draws the app icons as PNGs with no dependencies (just Node's zlib).
// Run from app/: node scripts/make-icons.mjs
import { deflateSync } from "node:zlib";
import { mkdirSync, writeFileSync } from "node:fs";

// Same mark as the in-app logo: Do first in vermilion, the rest in ink, Eliminate faded.
const BG = [0xfc, 0xfb, 0xf8];
const TILES = [[0xd4, 0x51, 0x2f], [0x1c, 0x1b, 0x19], [0x1c, 0x1b, 0x19], [0xc8, 0xc6, 0xc1]];

const CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
const crc32 = (buf) => {
  let c = 0xffffffff;
  for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
};
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}
function encodePNG(size, rgb) {
  const raw = Buffer.alloc((size * 3 + 1) * size);
  for (let y = 0; y < size; y++) rgb.copy(raw, y * (size * 3 + 1) + 1, y * size * 3, (y + 1) * size * 3);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 2; // 8-bit RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0)),
  ]);
}

// pad = empty margin around the 2×2 tiles (as a fraction of the icon).
// Maskable icons need a bigger margin because Android crops them into circles.
function draw(size, pad) {
  const gap = 0.05, radius = 0.055;
  const tile = (1 - 2 * pad - gap) / 2;
  const rects = [0, 1, 2, 3].map((i) => ({ x: pad + (i % 2) * (tile + gap), y: pad + Math.floor(i / 2) * (tile + gap), color: TILES[i] }));
  const inside = (px, py, r) => {
    const dx = Math.max(r.x + radius - px, 0, px - (r.x + tile - radius));
    const dy = Math.max(r.y + radius - py, 0, py - (r.y + tile - radius));
    return px >= r.x && px <= r.x + tile && py >= r.y && py <= r.y + tile && dx * dx + dy * dy <= radius * radius;
  };
  const SS = 4; // 4×4 supersampling for smooth corners
  const out = Buffer.alloc(size * size * 3);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const acc = [0, 0, 0];
    for (let sy = 0; sy < SS; sy++) for (let sx = 0; sx < SS; sx++) {
      const px = (x + (sx + 0.5) / SS) / size, py = (y + (sy + 0.5) / SS) / size;
      const c = rects.find((r) => inside(px, py, r))?.color ?? BG;
      acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2];
    }
    const o = (y * size + x) * 3;
    for (let k = 0; k < 3; k++) out[o + k] = Math.round(acc[k] / (SS * SS));
  }
  return encodePNG(size, out);
}

mkdirSync("public/icons", { recursive: true });
writeFileSync("public/icons/icon-192.png", draw(192, 0.2));
writeFileSync("public/icons/icon-512.png", draw(512, 0.2));
writeFileSync("public/icons/icon-maskable-512.png", draw(512, 0.27));
writeFileSync("public/icons/apple-touch-icon.png", draw(180, 0.2));
console.log("icons written to public/icons/");
