// Geometry of the skin cross-section. Pure functions of x and the scar lift,
// so every frame is deterministic.
import { random } from "remotion";

export const W = 1080;
export const H = 1920;
export const FPS = 24;
export const DURATION = 600; // 25 s

export const CENTER_X = 540;
export const SURFACE_Y = 760;
export const DERMIS_BOTTOM = 1330;
export const MAX_LIFT = 95;

export const C = {
  linen: "#F3E9E1",
  linenLight: "#F8F1EB",
  graphite: "#2B2B2B",
  teal: "#1F6F6B",
  tealMist: "#9FBFBC",
  epidermis: "#E4C6B2",
  dermisTop: "#F0DDCD",
  amber: "#E2B27E",
};

const SIGMA = 150;

export const bump = (x: number) => Math.exp(-((x - CENTER_X) ** 2) / (2 * SIGMA * SIGMA));

/** Skin surface; `lift` raises the scar ridge around the centre. */
export const surfaceY = (x: number, lift: number) =>
  SURFACE_Y + 6 * Math.sin(x / 37) + 4 * Math.sin(x / 11 + 1.3) - lift * bump(x);

/** Bottom of the epidermis: rete ridges flatten and the layer thins over the scar. */
export const epidermisBottomY = (x: number, lift: number) => {
  const scar = bump(x) * (lift / MAX_LIFT);
  return surfaceY(x, lift) + 74 - 26 * scar + 9 * Math.sin(x / 23) * (1 - scar);
};

export const polyline = (fn: (x: number) => number, x0: number, x1: number, step = 8) => {
  const pts: string[] = [];
  for (let x = x0; x <= x1; x += step) pts.push(`${x.toFixed(1)},${fn(x).toFixed(1)}`);
  return pts;
};

export const linePath = (fn: (x: number) => number, x0 = -40, x1 = W + 40) =>
  `M ${polyline(fn, x0, x1).join(" L ")}`;

/** Closed band between two curves (top left→right, bottom right→left). */
export const bandPath = (top: (x: number) => number, bottom: (x: number) => number, x0 = -40, x1 = W + 40) => {
  const t = polyline(top, x0, x1);
  const b = polyline(bottom, x0, x1).reverse();
  return `M ${t.join(" L ")} L ${b.join(" L ")} Z`;
};

const rnd = (seed: string) => random(seed);
const between = (seed: string, a: number, b: number) => a + rnd(seed) * (b - a);

export type Fiber = {
  x: number;
  depth: number; // 0..1 inside the dermis (normal) or px below surface (scar)
  angle: number;
  length: number;
  curve: number;
  appear: number; // seconds
};

/** Healthy basket-weave collagen across the dermis. */
export const NORMAL_FIBERS: Fiber[] = Array.from({ length: 90 }, (_, i) => ({
  x: between(`nx${i}`, 30, W - 30),
  depth: between(`nd${i}`, 0.08, 0.92),
  angle: between(`na${i}`, -0.65, 0.65),
  length: between(`nl${i}`, 80, 170),
  curve: between(`nc${i}`, -18, 18),
  appear: 3.4 + between(`nt${i}`, 0, 3.0),
}));

/** Scar collagen: a few form while the wound heals, many more once moisture escapes. */
export const SCAR_FIBERS: Fiber[] = Array.from({ length: 52 }, (_, i) => {
  const spread = (rnd(`sx${i}`) + rnd(`sx2${i}`) - 1) * 230; // centre-weighted
  return {
    x: CENTER_X + spread,
    depth: between(`sd${i}`, 95, 340),
    angle: between(`sa${i}`, -1.1, 1.1),
    length: between(`sl${i}`, 60, 120),
    curve: between(`sc${i}`, -22, 22),
    appear: i < 12 ? 4.0 + i * 0.22 : 7.2 + (i - 12) * 0.115,
  };
});

export type Drop = { x: number; birth: number; r: number; sway: number };

export const RISING_DROPS: Drop[] = Array.from({ length: 26 }, (_, i) => ({
  x: between(`rx${i}`, 140, 940),
  birth: 7.0 + between(`rb${i}`, 0, 4.2),
  r: between(`rr${i}`, 9, 20),
  sway: between(`rs${i}`, -1, 1),
}));

export const RETURNING_DROPS: Drop[] = Array.from({ length: 22 }, (_, i) => ({
  x: between(`dx${i}`, 240, 840),
  birth: 17.1 + between(`db${i}`, 0, 2.6),
  r: between(`dr${i}`, 8, 16),
  sway: between(`ds${i}`, -1, 1),
}));

export type Pore = { x: number; y: number; rx: number; ry: number; o: number };

/** Macro surface for shot 1, laid out on a canvas wider than the frame for the glide. */
export const PORES: Pore[] = Array.from({ length: 520 }, (_, i) => ({
  x: between(`px${i}`, -60, W + 420),
  y: between(`py${i}`, -40, H + 40),
  rx: between(`prx${i}`, 1.6, 4.2),
  ry: between(`pry${i}`, 1.2, 3.0),
  o: between(`po${i}`, 0.12, 0.32),
}));

export const CREASES = Array.from({ length: 34 }, (_, i) => {
  const y = between(`cy${i}`, -40, H + 40);
  const x = between(`cx${i}`, -100, W + 300);
  const len = between(`cl${i}`, 220, 520);
  const tilt = between(`ct${i}`, -0.35, 0.35);
  const bend = between(`cb${i}`, -40, 40);
  const x1 = x + len * Math.cos(tilt);
  const y1 = y + len * Math.sin(tilt);
  return {
    d: `M ${x.toFixed(1)} ${y.toFixed(1)} Q ${((x + x1) / 2).toFixed(1)} ${((y + y1) / 2 + bend).toFixed(1)} ${x1.toFixed(1)} ${y1.toFixed(1)}`,
    o: between(`co${i}`, 0.05, 0.12),
  };
});
