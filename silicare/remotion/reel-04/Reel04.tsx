// Reels 4 «Почему рубец становится грубым» — hand-authored cross-section animation.
// Shots and timings follow silicare/reels/reel-04-why-scar-gets-rough.json; titles and
// the logo are burned in later by silicare/assemble.py, so this frame carries no text.
import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  interpolateColors,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  C,
  CENTER_X,
  CREASES,
  DERMIS_BOTTOM,
  Drop,
  Fiber,
  H,
  MAX_LIFT,
  NORMAL_FIBERS,
  PORES,
  RETURNING_DROPS,
  RISING_DROPS,
  SCAR_FIBERS,
  SURFACE_Y,
  W,
  bandPath,
  bump,
  epidermisBottomY,
  linePath,
  surfaceY,
} from "./geometry";

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const progress = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));
const inOut = Easing.inOut(Easing.sin);
const out = Easing.out(Easing.cubic);
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

/** Undirected line angle folded into (-π/2, π/2]. */
const fold = (a: number) => {
  let v = a;
  while (v > Math.PI / 2) v -= Math.PI;
  while (v <= -Math.PI / 2) v += Math.PI;
  return v;
};

const fiberPath = (cx: number, cy: number, angle: number, length: number, curve: number) => {
  const dx = (Math.cos(angle) * length) / 2;
  const dy = (Math.sin(angle) * length) / 2;
  const nx = -Math.sin(angle) * curve;
  const ny = Math.cos(angle) * curve;
  return `M ${(cx - dx).toFixed(1)} ${(cy - dy).toFixed(1)} Q ${(cx + nx).toFixed(1)} ${(cy + ny).toFixed(1)} ${(cx + dx).toFixed(1)} ${(cy + dy).toFixed(1)}`;
};

type State = {
  t: number;
  lift: number;
  thicken: number; // shot 4
  align: number; // shot 6
};

const NormalFiber: React.FC<{ f: Fiber; s: State }> = ({ f, s }) => {
  const reveal = out(progress(s.t, f.appear, f.appear + 1.1));
  if (reveal <= 0) return null;
  const top = epidermisBottomY(f.x, s.lift) + 14;
  const cy = lerp(top, DERMIS_BOTTOM - 40, f.depth);
  // Healthy collagen also calms in shot 6, but far less than the scar.
  const angle = lerp(f.angle, f.angle * 0.6, s.align);
  return (
    <path
      d={fiberPath(f.x, cy, angle, f.length, f.curve)}
      fill="none"
      stroke={C.graphite}
      strokeOpacity={0.24}
      strokeWidth={2}
      strokeLinecap="round"
      pathLength={1}
      strokeDasharray="1 1"
      strokeDashoffset={1 - reveal}
    />
  );
};

const ScarFiber: React.FC<{ f: Fiber; s: State; i: number }> = ({ f, s, i }) => {
  const reveal = out(progress(s.t, f.appear, f.appear + 0.9));
  if (reveal <= 0) return null;
  const k = s.thicken;
  const a = s.align;
  // Crowd toward the seam and rise with the ridge.
  const x = CENTER_X + (f.x - CENTER_X) * (1 - 0.22 * k);
  const rise = s.lift * bump(x) * 0.9;
  const loose = SURFACE_Y + f.depth - rise;
  // Shot 6: settle into even, parallel rows.
  const row = SURFACE_Y + 112 + Math.round((f.depth - 95) / 24) * 24 - rise;
  const y = lerp(loose, row, a);
  // Shot 4: concentric arcs around a nodule under the ridge (hypertrophic whorl);
  // shot 6: lie flat in even rows.
  const nodeY = SURFACE_Y + 170 - rise;
  const dx = x - CENTER_X;
  const dy = (y - nodeY) * 2.4; // a flat, wide nodule under the ridge
  const whorl = fold(Math.atan2(dy, dx) + Math.PI / 2);
  const radius = Math.max(40, Math.hypot(dx, dy));
  const towardNode = -Math.sin(whorl) * -dx + Math.cos(whorl) * -dy >= 0 ? 1 : -1;
  const arc = towardNode * Math.min(28, (f.length * f.length) / (8 * radius));
  const crowded = lerp(f.angle, whorl, k);
  const angle = lerp(crowded, (i % 5 - 2) * 0.025, a);
  const length = f.length * (1 + 0.15 * k + 0.45 * a);
  const curve = lerp(lerp(f.curve, arc, k), f.curve * 0.15, a);
  const width = 1.8 + 2.4 * k * (1 - 0.4 * a);
  const opacity = (0.32 + 0.22 * k - 0.04 * a) * reveal;
  const color = interpolateColors(a, [0, 1], ["#5A4B42", "#2E5A56"]);
  return (
    <path
      d={fiberPath(x, y, angle, length, curve)}
      fill="none"
      stroke={color}
      strokeOpacity={opacity}
      strokeWidth={width}
      strokeLinecap="round"
      pathLength={1}
      strokeDasharray="1 1"
      strokeDashoffset={1 - reveal}
    />
  );
};

const Droplet: React.FC<{ x: number; y: number; r: number; o: number }> = ({ x, y, r, o }) => (
  <g opacity={o}>
    <circle cx={x} cy={y} r={r} fill="#FFFFFF" fillOpacity={0.78} stroke={C.tealMist} strokeWidth={2.2} />
    <circle cx={x - r * 0.35} cy={y - r * 0.38} r={Math.max(1.2, r * 0.26)} fill="#FFFFFF" fillOpacity={0.95} />
  </g>
);

const risingDrop = (d: Drop, s: State) => {
  const age = s.t - d.birth;
  if (age < 0 || age > 2.4) return null;
  const p = out(age / 2.4);
  const x = d.x + d.sway * 14 * Math.sin(p * Math.PI * 1.5);
  const y = surfaceY(d.x, s.lift) - 6 - 310 * p;
  const r = d.r * (0.55 + 0.45 * clamp01(age / 0.4));
  const o = clamp01(age / 0.25) * (1 - progress(age, 1.6, 2.4));
  return <Droplet key={`r${d.birth}`} x={x} y={y} r={r} o={o} />;
};

const returningDrop = (d: Drop, s: State) => {
  const age = s.t - d.birth;
  if (age < 0) return null;
  const p = Easing.in(Easing.quad)(clamp01(age / 1.3));
  const landed = surfaceY(d.x, s.lift) - 5;
  const x = d.x + d.sway * 10 * Math.sin(p * Math.PI) * (1 - p);
  const y = lerp(landed - 290, landed, p);
  const r = p < 1 ? d.r : lerp(d.r, 3.6, clamp01((age - 1.3) / 0.5));
  const o = clamp01(age / 0.25) * 0.85;
  return <Droplet key={`d${d.birth}`} x={x} y={y} r={r} o={o} />;
};

/** Shot 1: macro skin surface; the camera glides along it, then dives in. */
const Surface: React.FC<{ t: number }> = ({ t }) => {
  const glide = -320 * Easing.out(Easing.sin)(progress(t, 0, 3.4));
  const dive = Easing.in(Easing.quad)(progress(t, 2.6, 3.4));
  const opacity = 1 - dive;
  if (opacity <= 0) return null;
  const scale = 1.12 + 1.1 * dive;
  return (
    <g opacity={opacity} transform={`translate(${W / 2} ${SURFACE_Y}) scale(${scale}) translate(${-W / 2 + glide} ${-SURFACE_Y})`}>
      <rect x={-80} y={-60} width={W + 520} height={H + 120} filter="url(#skin)" />
      {CREASES.map((c, i) => (
        <path key={i} d={c.d} fill="none" stroke={C.graphite} strokeOpacity={c.o} strokeWidth={2.2} strokeLinecap="round" />
      ))}
      {PORES.map((p, i) => (
        <ellipse key={i} cx={p.x} cy={p.y} rx={p.rx} ry={p.ry} fill="#6E5547" fillOpacity={p.o} />
      ))}
      <rect x={-80} y={-60} width={W + 520} height={H + 120} fill="url(#sideLight)" />
    </g>
  );
};

export const Reel04: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const lift =
    t < 12 ? 0 : t < 21 ? MAX_LIFT * inOut(progress(t, 12, 16)) : MAX_LIFT - 33 * inOut(progress(t, 21, 24.5));
  const s: State = { t, lift, thicken: inOut(progress(t, 12, 16)), align: inOut(progress(t, 21, 24.2)) };

  // Shot 2 entry: from deep inside the surface back out to the whole section.
  const enter = out(progress(t, 2.8, 4.6));
  const sectionOpacity = out(progress(t, 2.8, 4.0));
  const drift = 1 + 0.03 * progress(t, 4.6, 21);
  // Shot 6: the section steps back a little; the logo goes into the empty air above it.
  const settle = spring({ frame: frame - 21 * fps, fps, config: { damping: 200 }, durationInFrames: 40 });
  const scale = lerp(1.6, 1, enter) * drift * (1 - 0.05 * settle);
  const sectionTransform =
    `translate(0 ${(40 * settle).toFixed(1)}) ` +
    `translate(${CENTER_X} ${SURFACE_Y}) scale(${scale.toFixed(4)}) translate(${-CENTER_X} ${-SURFACE_Y})`;

  const draw = out(progress(t, 3.0, 4.8));
  const seam = out(progress(t, 3.6, 4.6)) * lerp(0.55, 0.28, progress(t, 7, 10));
  const warm = (0.22 * inOut(progress(t, 7, 12)) + 0.05 * s.thicken) * (1 - inOut(progress(t, 16.5, 20)));
  const teal = 0.08 * inOut(progress(t, 16.5, 20.5));

  // Shot 5: the silicone sheet settles from above and conforms to the ridge.
  const sheetIn = spring({ frame: frame - 16 * fps, fps, config: { damping: 200 }, durationInFrames: 44 });
  const sheetVisible = t >= 16;
  const off = 430 * (1 - sheetIn);
  const conform = clamp01(1 - off / 140);
  const flat = surfaceY(CENTER_X, lift) - 2;
  const sheetBottom = (x: number) => lerp(flat, surfaceY(x, lift) - 2, conform) - off;
  const sheetTop = (x: number) => sheetBottom(x) - 34;
  const sheen = progress(t, 18.4, 20.8);
  const sheenX = lerp(160, 920, inOut(sheen));

  const surface = (x: number) => surfaceY(x, lift);
  const epiBottom = (x: number) => epidermisBottomY(x, lift);
  const floor = () => DERMIS_BOTTOM + 40;

  return (
    <AbsoluteFill style={{ backgroundColor: C.linen }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        <defs>
          <radialGradient id="window" cx="0.15" cy="0.12" r="1.1">
            <stop offset="0" stopColor={C.linenLight} />
            <stop offset="0.6" stopColor={C.linen} />
            <stop offset="1" stopColor="#EADCD1" />
          </radialGradient>
          <linearGradient id="dermis" x1="0" y1={SURFACE_Y} x2="0" y2={DERMIS_BOTTOM + 40} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor={C.dermisTop} />
            <stop offset="0.7" stopColor="#F1E2D5" />
            <stop offset="1" stopColor={C.linen} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="fadeDown" x1="0" y1={DERMIS_BOTTOM - 260} x2="0" y2={DERMIS_BOTTOM + 20} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="1" stopColor="#000000" />
          </linearGradient>
          <mask id="fade" maskUnits="userSpaceOnUse" x={-200} y={-200} width={W + 400} height={H + 400}>
            <rect x={-200} y={-200} width={W + 400} height={H + 400} fill="url(#fadeDown)" />
          </mask>
          <linearGradient id="sheet" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#FFFFFF" stopOpacity={0.72} />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity={0.4} />
          </linearGradient>
          <linearGradient id="sheen" gradientUnits="userSpaceOnUse" x1={sheenX - 110} y1="0" x2={sheenX + 110} y2="0">
            <stop offset="0" stopColor="#FFFFFF" stopOpacity={0} />
            <stop offset="0.5" stopColor="#FFFFFF" stopOpacity={0.85} />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity={0} />
          </linearGradient>
          <filter id="skin" x="-5%" y="-5%" width="110%" height="110%">
            <feTurbulence type="fractalNoise" baseFrequency="0.028 0.04" numOctaves={4} seed={11} result="noise" />
            <feDiffuseLighting in="noise" surfaceScale={3.2} diffuseConstant={1.05} lightingColor="#FFF7F0" result="light">
              <feDistantLight azimuth={215} elevation={52} />
            </feDiffuseLighting>
            <feFlood floodColor="#EACFBC" result="tone" />
            <feBlend in="light" in2="tone" mode="multiply" />
          </filter>
          <linearGradient id="sideLight" x1="0" y1="0" x2="1" y2="0.3">
            <stop offset="0" stopColor="#FFF8F2" stopOpacity={0.35} />
            <stop offset="0.55" stopColor="#FFF8F2" stopOpacity={0} />
            <stop offset="1" stopColor={C.graphite} stopOpacity={0.12} />
          </linearGradient>
          <radialGradient id="vignette" cx="0.5" cy="0.45" r="0.75">
            <stop offset="0.55" stopColor={C.graphite} stopOpacity={0} />
            <stop offset="1" stopColor={C.graphite} stopOpacity={0.22} />
          </radialGradient>
        </defs>

        <rect width={W} height={H} fill="url(#window)" />

        <g opacity={sectionOpacity} transform={sectionTransform}>
          <path d={bandPath(epiBottom, floor)} fill="url(#dermis)" />
          <g mask="url(#fade)">
            {NORMAL_FIBERS.map((f, i) => (
              <NormalFiber key={i} f={f} s={s} />
            ))}
            {SCAR_FIBERS.map((f, i) => (
              <ScarFiber key={i} f={f} s={s} i={i} />
            ))}
          </g>
          <path d={bandPath(surface, epiBottom)} fill={C.epidermis} />
          <line
            x1={CENTER_X}
            y1={surface(CENTER_X) + 4}
            x2={CENTER_X}
            y2={surface(CENTER_X) + 4 + 150 * out(progress(t, 3.6, 4.6))}
            stroke={C.graphite}
            strokeOpacity={seam}
            strokeWidth={2}
            strokeLinecap="round"
          />
          <g mask="url(#fade)">
            <path d={bandPath(surface, floor)} fill={C.amber} fillOpacity={warm} />
            <path d={bandPath(surface, floor)} fill={C.teal} fillOpacity={teal} />
          </g>
          <path
            d={linePath(epiBottom)}
            fill="none"
            stroke={C.graphite}
            strokeOpacity={0.3}
            strokeWidth={1.6}
            pathLength={1}
            strokeDasharray="1 1"
            strokeDashoffset={1 - draw}
          />
          <path
            d={linePath(surface)}
            fill="none"
            stroke={C.graphite}
            strokeOpacity={0.6}
            strokeWidth={3.5}
            pathLength={1}
            strokeDasharray="1 1"
            strokeDashoffset={1 - draw}
          />
          {RISING_DROPS.map((d) => risingDrop(d, s))}
          {RETURNING_DROPS.map((d) => returningDrop(d, s))}
          {sheetVisible ? (
            <g opacity={out(progress(t, 16, 16.6))}>
              <path d={bandPath(sheetTop, sheetBottom, 200, 880)} fill="url(#sheet)" stroke="#FFFFFF" strokeOpacity={0.7} strokeWidth={1.5} strokeLinejoin="round" />
              <path d={bandPath(sheetTop, sheetBottom, 200, 880)} fill="url(#sheen)" opacity={Math.sin(Math.PI * sheen)} />
              <path d={linePath(sheetTop, 200, 880)} fill="none" stroke={C.teal} strokeOpacity={0.85} strokeWidth={4} strokeLinecap="round" />
              <path d={linePath(sheetBottom, 200, 880)} fill="none" stroke={C.teal} strokeOpacity={0.3} strokeWidth={1.5} />
            </g>
          ) : null}
        </g>

        <Surface t={t} />
        <rect width={W} height={H} fill="url(#vignette)" opacity={1 - 0.6 * progress(t, 2.8, 4.0)} />
      </svg>
    </AbsoluteFill>
  );
};
