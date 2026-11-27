// Public shelter symbol (NordicCiv v0.4): a small heater shield with an arched doorway — "a protected room for the
// public" — in the map's ink-outlined, top-left-lit style: dark-blue field, muted-gold rim, warm stone doorway.
// It stands for the facility *category* (a public shelter in DSB's register), never for how the facility looks, its
// entrance or its layout. Deliberately unlike the other sites: no ring (wonders), no wall or star (forts), no cross
// (health), no pin. Group symbols are the same shield with a count tab.
//
//   drawShelter(ctx, x, y, size, {selected})          one shelter (size in user units across)
//   drawShelterGroup(ctx, x, y, size, n, {region})    a group symbol with its count; text in screen px via o
import { bucketPx, deviceScale, getSprite, drawSprite } from "./sprites.js";

const BOX = { x0: -1.2, y0: -1.2, x1: 1.2, y1: 1.25 };
const INK = "rgba(24,18,10,.92)";
const GOLD = "#c9a45c";
const GOLD_HI = "#e8cf8e";

function shieldPath(g, s = 1) {
  g.beginPath();
  g.moveTo(-0.78 * s, -0.78 * s);
  g.quadraticCurveTo(0, -0.95 * s, 0.78 * s, -0.78 * s);
  g.lineTo(0.78 * s, 0.05 * s);
  g.quadraticCurveTo(0.72 * s, 0.62 * s, 0, 1.0 * s);
  g.quadraticCurveTo(-0.72 * s, 0.62 * s, -0.78 * s, 0.05 * s);
  g.closePath();
}

function paint(g, upx, { selected = false, group = false } = {}) {
  // ground shadow, offset down-right like the other sites (light from the top left)
  g.fillStyle = "rgba(16,12,6,.34)";
  g.beginPath();
  g.ellipse(0.1, 0.98, 0.62, 0.16, 0, 0, Math.PI * 2);
  g.fill();
  if (group) {
    // a second shield behind, so a group reads as "more than one" before the count is read
    g.save();
    g.translate(0.2, -0.12);
    shieldPath(g, 0.92);
    g.fillStyle = "#22344f";
    g.fill();
    g.lineWidth = 1 / upx;
    g.strokeStyle = INK;
    g.stroke();
    g.restore();
  }
  shieldPath(g);
  const grad = g.createLinearGradient(-0.6, -0.9, 0.6, 0.9);
  grad.addColorStop(0, "#5a80ad");
  grad.addColorStop(0.5, "#33547e");
  grad.addColorStop(1, "#1d3352");
  g.fillStyle = grad;
  g.fill();
  // rim: ink outside, gold inside
  g.lineJoin = "round";
  g.lineWidth = Math.max(2.4 / upx, 0.16);
  g.strokeStyle = INK;
  g.stroke();
  g.lineWidth = Math.max(1.7 / upx, 0.1);
  g.strokeStyle = selected ? GOLD_HI : GOLD;
  g.stroke();
  // lit upper-left edge
  g.beginPath();
  g.moveTo(-0.66, 0.0);
  g.lineTo(-0.66, -0.66);
  g.quadraticCurveTo(-0.2, -0.76, 0.3, -0.72);
  g.lineWidth = Math.max(1 / upx, 0.05);
  g.strokeStyle = "rgba(255,238,200,.32)";
  g.stroke();
  // doorway: an arched opening with a threshold, warm stone with a dark recess
  const dw = 0.3, top = -0.3, base = 0.52;
  g.beginPath();
  g.moveTo(-dw, base);
  g.lineTo(-dw, top + dw);
  g.arc(0, top + dw, dw, Math.PI, 0);
  g.lineTo(dw, base);
  g.closePath();
  g.fillStyle = "#e6d3a3";
  g.fill();
  g.lineWidth = Math.max(1 / upx, 0.06);
  g.strokeStyle = INK;
  g.stroke();
  const iw = 0.17;
  g.beginPath();
  g.moveTo(-iw, base);
  g.lineTo(-iw, top + dw + 0.06);
  g.arc(0, top + dw + 0.06, iw, Math.PI, 0);
  g.lineTo(iw, base);
  g.closePath();
  g.fillStyle = "#2a2116";
  g.fill();
  // threshold step
  g.fillStyle = "#b99b62";
  g.fillRect(-0.4, base - 0.02, 0.8, 0.1);
  g.lineWidth = Math.max(0.8 / upx, 0.04);
  g.strokeStyle = INK;
  g.strokeRect(-0.4, base - 0.02, 0.8, 0.1);
}

function stamp(ctx, key, x, y, size, opts) {
  const k = size / 2;
  const upx = bucketPx(deviceScale(ctx) * k, { min: 3, max: 160 });
  const spr = getSprite(key, upx, BOX, (g, u) => paint(g, u, opts));
  drawSprite(ctx, spr, x, y, k);
}

/** One public shelter; (x, y) is the record's true position (the shield's point sits just above it). */
export function drawShelter(ctx, x, y, size, { selected = false } = {}) {
  if (selected) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, size * 0.78, 0, Math.PI * 2);
    ctx.lineWidth = size * 0.09;
    ctx.strokeStyle = "rgba(246,222,150,.9)";
    ctx.stroke();
    ctx.restore();
  }
  stamp(ctx, `shelter:${selected ? 1 : 0}`, x, y, size, { selected });
}

/** A group of n shelters drawn as one symbol, with its count on a small tab (screen-space text through o). */
export function drawShelterGroup(ctx, x, y, size, n, o) {
  stamp(ctx, "shelter:g", x, y, size, { group: true });
  const [sx, sy] = o.toScreen(x, y);
  const px = size * o.s; // css px across
  o.screen();
  const label = n >= 1000 ? `${Math.round(n / 100) / 10}k` : String(n);
  const fs = Math.max(9, Math.min(12, px * 0.42));
  ctx.font = `700 ${fs.toFixed(1)}px -apple-system, system-ui, sans-serif`;
  const tw = ctx.measureText(label).width;
  const w = Math.max(fs + 4, tw + 7), h = fs + 4;
  const bx = sx + px * 0.22, by = sy - px * 0.62;
  ctx.beginPath();
  const r = h / 2;
  ctx.moveTo(bx + r, by); ctx.lineTo(bx + w - r, by); ctx.arc(bx + w - r, by + r, r, -Math.PI / 2, Math.PI / 2);
  ctx.lineTo(bx + r, by + h); ctx.arc(bx + r, by + r, r, Math.PI / 2, -Math.PI / 2);
  ctx.closePath();
  ctx.fillStyle = "rgba(28,20,10,.94)";
  ctx.fill();
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = GOLD;
  ctx.stroke();
  ctx.fillStyle = "#f6e7bf";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, bx + w / 2, by + h / 2 + 0.5);
  o.world();
}
