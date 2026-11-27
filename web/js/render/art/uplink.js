// Camera uplink symbol (NordicCiv v0.5): a brass spyglass on a short tripod, standing on a small round stone
// lookout — "a public viewpoint you can look through" — in the map's ink-outlined, top-left-lit style. It follows
// the wonder plinth's perspective (an ellipse seen from above at the same tilt) but stays smaller, grey stone instead
// of a gold-rimmed seal, and carries no building, so it reads as a modest geographical feature rather than a site.
// The symbol stands for the presence of a public viewpoint, never for the camera's installation, its direction or
// what it shows. Deliberately not a camera body, lens dot, pin or radar mark (no surveillance look).
//
//   drawUplink(ctx, x, y, size, {selected})          one camera uplink; (x, y) = its position (the lookout's centre)
//   drawUplinkGroup(ctx, x, y, size, n, o)            several uplinks drawn as one symbol, with a count tab
import { bucketPx, deviceScale, getSprite, drawSprite } from "./sprites.js";

const TAU = Math.PI * 2;
const BOX = { x0: -1.15, y0: -1.25, x1: 1.15, y1: 0.95 };
const INK = "rgba(24,18,10,.92)";
const GOLD = "#c9a45c";
const GOLD_HI = "#f2d27a";

/** A line width of wPx device px, but never wider than maxU art units (small sprites would otherwise be all ink). */
const lw = (upx, wPx, maxU) => Math.min(wPx / upx, maxU);

function ink(g, upx, wPx = 1.1, col = INK) {
  g.lineWidth = lw(upx, wPx, wPx * 0.045);
  g.strokeStyle = col;
  g.stroke();
}

/** The round stone lookout: a low drum seen from above, like the wonder plinth but plain stone. */
function lookout(g, upx, group) {
  g.fillStyle = "rgba(16,12,6,.32)";
  g.beginPath();
  g.ellipse(0.08, 0.62, 0.8, 0.22, 0, 0, TAU);
  g.fill();
  const rx = 0.78, ry = 0.27, top = 0.36, h = 0.13;
  g.beginPath(); // drum side
  g.ellipse(0, top + h, rx, ry, 0, 0, Math.PI);
  g.lineTo(-rx, top);
  g.ellipse(0, top, rx, ry, 0, Math.PI, 0, true);
  g.closePath();
  g.fillStyle = "#6a7276";
  g.fill();
  ink(g, upx, 1);
  g.beginPath(); // top
  g.ellipse(0, top, rx, ry, 0, 0, TAU);
  const t = g.createLinearGradient(-rx, top - ry, rx, top + ry);
  t.addColorStop(0, "#e3e2d6");
  t.addColorStop(1, "#a3aaa4");
  g.fillStyle = t;
  g.fill();
  g.lineWidth = lw(upx, 1.2, 0.05);
  g.strokeStyle = group ? GOLD : "rgba(201,164,92,.75)";
  g.stroke();
  ink(g, upx, 0.7, "rgba(40,30,16,.75)");
  // two paving joints, so the top reads as stone at larger sizes
  if (upx > 10) {
    g.beginPath();
    g.moveTo(-0.32, top - 0.2); g.lineTo(-0.22, top + 0.2);
    g.moveTo(0.3, top - 0.21); g.lineTo(0.38, top + 0.19);
    g.lineWidth = 0.6 / upx;
    g.strokeStyle = "rgba(60,52,40,.45)";
    g.stroke();
  }
}

/** Tripod and spyglass, pointing up and away to the right (towards the view, away from the light). */
function spyglass(g, upx, selected) {
  const apex = [-0.02, -0.12];
  // tripod legs: two in front, one behind (drawn first, darker)
  g.lineCap = "round";
  g.beginPath();
  g.moveTo(apex[0], apex[1]); g.lineTo(0.06, 0.24);
  g.lineWidth = lw(upx, 2.6, 0.1); g.strokeStyle = INK; g.stroke();
  g.lineWidth = lw(upx, 1.3, 0.05); g.strokeStyle = "#4a3a22"; g.stroke();
  for (const [lx, ly] of [[-0.4, 0.46], [0.36, 0.46]]) {
    g.beginPath();
    g.moveTo(apex[0], apex[1]); g.lineTo(lx, ly);
    g.lineWidth = lw(upx, 2.8, 0.11); g.strokeStyle = INK; g.stroke();
    g.lineWidth = lw(upx, 1.5, 0.06); g.strokeStyle = "#8c6a36"; g.stroke();
  }
  // tube: a tapered brass cylinder from the eyepiece (lower left) to the objective (upper right)
  const a = -0.9; // radians, ~52° above horizontal: an instrument raised to a view, not a barrel
  g.save();
  g.translate(apex[0] + 0.04, apex[1] - 0.12);
  g.rotate(a);
  const x0 = -0.52, x1 = 0.7, r0 = 0.09, r1 = 0.19;
  g.beginPath();
  g.moveTo(x0, -r0); g.lineTo(x1, -r1); g.lineTo(x1, r1); g.lineTo(x0, r0); g.closePath();
  const br = g.createLinearGradient(0, -r1, 0, r1);
  br.addColorStop(0, selected ? "#fff1bf" : "#f6dc95");
  br.addColorStop(0.45, "#d6a952");
  br.addColorStop(1, "#86622a");
  g.fillStyle = br;
  g.fill();
  ink(g, upx, 1.2);
  // draw-tube rings
  for (const rx of [-0.28, 0.16]) {
    const rr = r0 + ((rx - x0) / (x1 - x0)) * (r1 - r0);
    g.beginPath();
    g.moveTo(rx, -rr - 0.015); g.lineTo(rx, rr + 0.015);
    ink(g, upx, 0.9, "rgba(50,34,10,.85)");
  }
  // eyepiece: a small brass cap
  g.beginPath();
  g.ellipse(x0 - 0.03, 0, 0.05, 0.075, 0, 0, TAU);
  g.fillStyle = "#b48a3e";
  g.fill();
  ink(g, upx, 0.8);
  // objective rim and lens, catching the light
  g.beginPath();
  g.ellipse(x1, 0, 0.09, r1 + 0.035, 0, 0, TAU);
  g.fillStyle = "#a57a32";
  g.fill();
  ink(g, upx, 1);
  g.beginPath();
  g.ellipse(x1 + 0.03, 0, 0.06, r1 - 0.01, 0, 0, TAU);
  const ln = g.createLinearGradient(x1, -r1, x1, r1);
  ln.addColorStop(0, "#f4fbfc");
  ln.addColorStop(1, "#8fc3d1");
  g.fillStyle = ln;
  g.fill();
  g.beginPath();
  g.ellipse(x1 + 0.04, -0.07, 0.022, 0.06, 0, 0, TAU);
  g.fillStyle = "#ffffff";
  g.fill();
  // lit upper edge (light from the top left)
  g.beginPath();
  g.moveTo(x0 + 0.05, -r0 + 0.035); g.lineTo(x1 - 0.06, -r1 + 0.045);
  g.lineWidth = lw(upx, 0.8, 0.03);
  g.strokeStyle = "rgba(255,246,214,.75)";
  g.stroke();
  g.restore();
  // mount head
  g.beginPath();
  g.arc(apex[0], apex[1], 0.075, 0, TAU);
  g.fillStyle = "#3b2c18";
  g.fill();
  ink(g, upx, 0.8);
}

function paint(g, upx, { selected = false, group = false } = {}) {
  lookout(g, upx, group);
  if (group) {
    // a second, smaller spyglass behind and to the left: "more than one viewpoint here"
    g.save();
    g.translate(-0.42, 0.02);
    g.scale(0.72, 0.72);
    g.globalAlpha = 0.95;
    spyglass(g, upx * 0.72, false);
    g.restore();
  }
  spyglass(g, upx, selected);
}

function stamp(ctx, key, x, y, size, opts) {
  const k = size / 2;
  const upx = bucketPx(deviceScale(ctx) * k, { min: 3, max: 160 });
  const spr = getSprite(key, upx, BOX, (g, u) => paint(g, u, opts));
  drawSprite(ctx, spr, x, y, k);
}

/** One camera uplink at its position; the lookout's centre sits on the point. */
function ring(ctx, x, y, size) {
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(x, y + size * 0.2, size * 0.56, size * 0.22, 0, 0, TAU);
  ctx.lineWidth = size * 0.07;
  ctx.strokeStyle = "rgba(246,222,150,.95)";
  ctx.stroke();
  ctx.restore();
}

export function drawUplink(ctx, x, y, size, { selected = false } = {}) {
  if (selected) ring(ctx, x, y, size);
  stamp(ctx, `uplink:${selected ? 1 : 0}`, x, y, size, { selected });
}

/** Several uplinks drawn as one symbol with a count tab (text in screen px through o, like the shelter groups). */
export function drawUplinkGroup(ctx, x, y, size, n, o, { selected = false } = {}) {
  if (selected) ring(ctx, x, y, size);
  stamp(ctx, "uplink:g", x, y, size, { group: true });
  const [sx, sy] = o.toScreen(x, y);
  const px = size * o.s;
  o.screen();
  const label = String(n);
  const fs = Math.max(9, Math.min(11.5, px * 0.42));
  ctx.font = `700 ${fs.toFixed(1)}px -apple-system, system-ui, sans-serif`;
  const tw = ctx.measureText(label).width;
  const w = Math.max(fs + 4, tw + 7), h = fs + 4;
  const bx = sx + px * 0.24, by = sy - px * 0.66;
  const r = h / 2;
  ctx.beginPath();
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

export const UPLINK_BOX = BOX;
export { GOLD_HI };
