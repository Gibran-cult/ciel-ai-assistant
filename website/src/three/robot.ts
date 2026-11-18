import * as THREE from "three";
import { SVGLoader } from "three/examples/jsm/loaders/SVGLoader.js";

// The Ciel robot, built from code at runtime: an android head whose face (brow, almond eyes with
// lids, nose, cheekbones, lips, chin, the line of the jaw) is sculpted into one parametric surface,
// finished in teal lacquer. The face plate is cut from the skull by real grooves with a gold strip
// sunk in each, the skin carries printed gold dots and chips, the eyes are glossy black balls behind
// the lids with a glowing iris, the ears are dials with the Kepingan logo (extruded from its real
// SVG paths) on a turned steel hub, and the neck is a black armoured sleeve. A few KB of code
// instead of a GLB download.

export type EyeState = {
  // Where the eyes look, -1..1 (x right, y down).
  x: number;
  y: number;
  // Brightness of the irises: 0 off, 1 normal, a little above 1 when pleased.
  glow: number;
  // 1 is the normal iris; wider when curious.
  size: number;
  // 0 closed .. 1 open: drives the upper lids.
  open: number;
  // 0 blue .. 1 gold (the irises warm up when a source is found).
  gold: number;
};

export type Robot = {
  group: THREE.Group;
  // Turns and nods about the top of the neck.
  head: THREE.Group;
  // Sets the irises, the lids and the colour of the eyes' light.
  eyes: { set: (s: EyeState) => void };
  // The eyes' light on the cheeks and nose. Its strength is set by the stage, which knows the scale
  // (a point light's intensity does not shrink with its parent).
  eyeLight: THREE.PointLight;
  dispose: () => void;
};

const COL = { blue: 0x9db3e8, blueFill: 0x2b4886, gold: 0xe9d06a };
// The lacquer: a grey teal-green, close to the owner's reference.
const LACQUER = 0x2b4d49;

// Kepingan paths from assets/brand/ciel-mark.svg (32-unit viewBox, ring centre at 14.4, 16).
const RING = "M24.89 10.6A11.8 11.8 0 1 0 24.89 21.4H20.57A8.2 8.2 0 1 1 20.57 10.6Z";
const PIECE = "M28.39 10.6A11.8 11.8 0 0 1 28.39 21.4H24.07A8.2 8.2 0 0 0 24.07 10.6Z";

// The head as two silhouettes, radius by height: the face seen from the side (forehead, brow,
// cheek, jaw, chin) and the back of the skull down to the neck. Around the head one blends into the
// other; under the line of the jaw the head tucks in to the neck.
const FRONT: Array<[number, number]> = [
  [0.001, 1.24], [0.42, 1.16], [0.63, 1.02], [0.77, 0.82], [0.85, 0.58], [0.88, 0.38], [0.86, 0.2],
  [0.86, 0.0], [0.84, -0.2], [0.81, -0.42], [0.78, -0.6], [0.74, -0.76], [0.64, -0.9], [0.44, -1.0],
];
const BACK: Array<[number, number]> = [
  [0.001, 1.24], [0.45, 1.17], [0.7, 1.03], [0.87, 0.8], [0.93, 0.5], [0.93, 0.2], [0.88, -0.1],
  [0.76, -0.38], [0.62, -0.6], [0.5, -0.8], [0.44, -1.0],
];
const Y_TOP = 1.24;
const Y_BOTTOM = -1.0;
const TORSO: Array<[number, number]> = [
  [0.42, -1.86], [0.66, -1.9], [1.02, -1.98], [1.38, -2.12], [1.66, -2.36], [1.8, -2.7], [1.85, -3.3], [1.86, -4.2],
];

// The torso is a lathe flattened front to back.
const TORSO_DEPTH = 0.56;

// Heads are narrower than they are deep.
const SX = 0.86;
const SZ = 1.1;
// Head units per radian of phi, near enough, for distances drawn in (phi, y).
const ARC = 0.82;

const gauss = (v: number, m: number, s: number) => Math.exp(-((v - m) ** 2) / (2 * s * s));
const smooth = (a: number, b: number, v: number) => {
  const t = Math.min(1, Math.max(0, (v - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// The eye opening: an almond whose upper lid arches higher than the lower one. w is the half-width,
// up/lo the height above/below the centre, in head units along the face (0.68 per radian of phi at
// the eyes); the outer corner sits `tilt` radians higher. `ball` is the eyeball's radius and `cut`
// how far the opening is pushed into the head, so the ball only shows through the almond.
const EYE = { phi: 0.44, y: 0.2, w: 0.13, up: 0.056, lo: 0.036, tilt: 0.09, ball: 0.135, cut: 0.2 };
const ARC_U = (EYE.w ** 2 + EYE.up ** 2) / (2 * EYE.up);
const ARC_L = (EYE.w ** 2 + EYE.lo ** 2) / (2 * EYE.lo);

// Signed distance to the edge of the eye opening, positive inside. Two circle arcs meet in sharp
// corners; the upper lid peaks toward the nose, the lower one dips toward the temple.
function almond(p: number, y: number): number {
  const u = (p - EYE.phi) * 0.68;
  const v = y - EYE.y;
  const c = Math.cos(EYE.tilt);
  const s = Math.sin(EYE.tilt);
  const x = u * c + v * s;
  const z = v * c - u * s;
  const du = ARC_U - Math.hypot(x + 0.015, z - (EYE.up - ARC_U));
  const dl = ARC_L - Math.hypot(x - 0.012, z + (EYE.lo - ARC_L));
  return Math.min(du, dl);
}

// 1 on the fold from beside the nose wing down past the corner of the mouth, fading at its ends.
function fold(p: number, y: number): number {
  const ax = 0.19 * 0.72;
  const ay = -0.21;
  const bx = 0.37 * 0.72;
  const by = -0.47;
  const px = p * 0.72;
  const t = Math.min(1, Math.max(0, ((px - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)));
  return gauss(Math.hypot(px - ax - t * (bx - ax), y - ay - t * (by - ay)), 0, 0.014) * (1 - (2 * t - 1) ** 4);
}

// The face, as a displacement over the head's angle around (phi, 0 = straight ahead) and height
// (y), mirrored left and right. Proportions: brow 0.34, eyes 0.2, nose tip -0.165, the base of the
// nose -0.255, the line between the lips -0.43, chin -0.72, so the face divides into even thirds.
function sculpt(phi: number, y: number): number {
  const p = Math.abs(phi);
  // The sides, outside the face: a hollow at the temple, the mass of the jaw angle.
  const d = -0.03 * gauss(p, 1.0, 0.16) * gauss(y, 0.45, 0.13) + 0.05 * gauss(p, 1.3, 0.28) * gauss(y, -0.52, 0.14);
  const front = 1 - smooth(0.55, 1.45, p);
  if (front <= 0) return d;
  const a = almond(p, y);
  let f = 0;
  // Brow: a ridge arching over each eye, dropping toward the temple, softer over the nose; the
  // saddle at the top of the nose under it.
  const browY = 0.34 + 0.022 * gauss(p, EYE.phi, 0.14) - 0.06 * smooth(0.62, 0.95, p);
  f += 0.034 * gauss(y, browY, 0.045) * gauss(p, 0.34, 0.32) * (0.55 + 0.45 * smooth(0.02, 0.2, p));
  f -= 0.016 * gauss(p, 0, 0.09) * gauss(y, 0.26, 0.03);
  // The orbit: a broad hollow round each eye, deepest at the inner upper corner under the brow.
  f -= 0.07 * gauss(p, EYE.phi, 0.2) * gauss(y, EYE.y + 0.01, 0.075);
  f -= 0.03 * gauss(p, 0.25, 0.06) * gauss(y, 0.25, 0.035);
  // Lids: a rounded margin all round the opening, the fold above the upper lid, a soft line under
  // the lower one.
  f += 0.034 * gauss(a, -0.011, 0.011);
  f -= 0.014 * gauss(a, -0.042, 0.009) * smooth(EYE.y, EYE.y + 0.04, y);
  f -= 0.008 * gauss(a, -0.04, 0.012) * smooth(EYE.y, EYE.y - 0.04, y);
  // Cheekbone high and wide, the cheek the lower lid rests on, the hollow under the cheekbone.
  f += 0.055 * gauss(p, 0.74, 0.19) * gauss(y, 0.02, 0.09);
  f += 0.02 * gauss(p, 0.42, 0.12) * gauss(y, 0.05, 0.05);
  f -= 0.045 * gauss(p, 0.62, 0.14) * gauss(y, -0.36, 0.13);
  // Nose: a flat-topped bridge widening and rising to the tip, an underside ending at the lip, the
  // wings with the crease that separates them from the cheek, and the nostrils.
  const nw = 0.042 + 0.03 * smooth(0.2, -0.15, y);
  f += (0.035 + 0.15 * smooth(0.24, -0.14, y)) * smooth(0.3, 0.22, y) * smooth(-0.255, -0.19, y) * Math.exp(-0.5 * (p / nw) ** 4);
  f += 0.055 * gauss(p, 0, 0.06) * gauss(y, -0.165, 0.04);
  f += 0.05 * gauss(p, 0.12, 0.04) * gauss(y, -0.205, 0.035);
  f -= 0.018 * gauss(p, 0.175, 0.018) * gauss(y, -0.19, 0.04);
  f -= 0.05 * gauss(p, 0.055, 0.022) * gauss(y, -0.228, 0.012);
  // The muzzle over the teeth, and the fold from the nose wing to the corner of the mouth.
  f += 0.045 * gauss(p, 0, 0.34) * gauss(y, -0.38, 0.16);
  f -= 0.016 * fold(p, y);
  // Philtrum: a groove between two ridges from under the nose to the cupid's bow.
  const phil = smooth(-0.25, -0.27, y) * smooth(-0.385, -0.365, y);
  f -= 0.012 * gauss(p, 0, 0.022) * phil;
  f += 0.008 * gauss(p, 0.05, 0.018) * phil;
  // Lips, corners at phi 0.31: ys is the line between them (corners turned down a touch), yb the
  // top of the upper lip with the cupid's bow, yl the bottom of the lower lip.
  const q = Math.min(1, p / 0.31);
  const mw = smooth(0.34, 0.25, p);
  const ys = -0.43 - 0.016 * q * q;
  const yb = -0.378 + 0.007 * gauss(p, 0.05, 0.02) - 0.006 * gauss(p, 0, 0.016) - 0.058 * q * q;
  const yl = -0.5 + 0.05 * q * q;
  // Each lip a soft roll between its edges, the line between them a crease.
  f += 0.03 * mw * gauss(y, (ys + yb) / 2, Math.max(0.008, (yb - ys) / 3.2));
  f += 0.034 * mw * gauss(y, (ys + yl) / 2, Math.max(0.008, (ys - yl) / 3));
  f -= 0.018 * mw * gauss(y, ys, 0.008);
  f -= 0.014 * gauss(p, 0.32, 0.025) * gauss(y, -0.446, 0.015);
  // The groove under the lower lip, then a square chin.
  f -= 0.022 * gauss(p, 0, 0.2) * gauss(y, -0.56, 0.028);
  f += 0.07 * gauss(p, 0, 0.16) * gauss(y, -0.72, 0.07);
  f += 0.02 * gauss(p, 0.15, 0.06) * gauss(y, -0.78, 0.05);
  // The opening itself, at full depth, so the eyeball shows only through the almond.
  return d + f * front - EYE.cut * smooth(-0.002, 0.01, a);
}

// Where the shell is cut into plates, in (phi, y) for one side (mirrored): w is the groove's width,
// d its depth, both in head units. Each groove carries a gold strip at its floor.
const SEAMS: Array<{ w: number; d: number; pts: Array<[number, number]> }> = [
  // The edge of the face plate: temple, outer cheekbone, round the jaw to the chin.
  { w: 0.042, d: 0.017, pts: [[0.8, 0.78], [0.86, 0.45], [0.84, 0.05], [0.76, -0.3], [0.64, -0.58], [0.44, -0.77], [0.1, -0.84]] },
  // Under the eye, across the cheekbone to the edge of the plate.
  { w: 0.028, d: 0.012, pts: [[0.54, 0.06], [0.68, 0.03], [0.84, 0.05]] },
  // From the edge of the plate back to the ear.
  { w: 0.036, d: 0.015, pts: [[0.84, 0.05], [1.03, 0.08], [1.22, 0.09]] },
  // The skull cap over the top of the head.
  { w: 0.042, d: 0.017, pts: [[0.8, 0.78], [1.0, 0.96], [1.4, 1.06], [2.2, 1.04]] },
  // The jaw hinge, back toward the ear.
  { w: 0.03, d: 0.013, pts: [[0.76, -0.3], [1.06, -0.34], [1.3, -0.25]] },
  // The rear plate, from the crown down behind the ear.
  { w: 0.042, d: 0.017, pts: [[2.2, 1.04], [2.22, 0.7], [2.2, 0.3], [2.24, -0.1], [2.16, -0.5], [2.0, -0.88]] },
  // Across the back of the skull, meeting its mirror.
  { w: 0.036, d: 0.015, pts: [[2.2, 0.42], [2.65, 0.4], [Math.PI, 0.38]] },
  // From under the ear down to the neck.
  { w: 0.03, d: 0.013, pts: [[1.52, -0.32], [1.58, -0.55], [1.5, -0.9]] },
];
// The ear dial: where it sits and the radius of the groove ring round it.
const EAR = { phi: 1.62, y: 0.08, groove: 0.4 };

// The seams sampled into short segments, each with a bounding box for a quick reject.
const SEAM_LINES = SEAMS.map((s) => {
  const pts = new THREE.SplineCurve(s.pts.map(([p, y]) => new THREE.Vector2(p, y))).getPoints(s.pts.length * 14);
  const pad = s.w;
  return {
    ...s,
    pts,
    box: [
      Math.min(...pts.map((v) => v.x)) - pad / ARC,
      Math.max(...pts.map((v) => v.x)) + pad / ARC,
      Math.min(...pts.map((v) => v.y)) - pad,
      Math.max(...pts.map((v) => v.y)) + pad,
    ],
  };
});

// Distance from (p, y) to a sampled line, in head units.
function lineDistance(pts: THREE.Vector2[], p: number, y: number): number {
  let d2 = Infinity;
  const px = p * ARC;
  for (let i = 0; i < pts.length - 1; i++) {
    const ax = pts[i].x * ARC;
    const ay = pts[i].y;
    const dx = pts[i + 1].x * ARC - ax;
    const dy = pts[i + 1].y - ay;
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy || 1)));
    const ex = px - ax - t * dx;
    const ey = y - ay - t * dy;
    d2 = Math.min(d2, ex * ex + ey * ey);
  }
  return Math.sqrt(d2);
}

// How deep the grooves cut at (|phi|, y): a flat floor with bevelled walls.
function groove(p: number, y: number): number {
  let g = 0;
  for (const s of SEAM_LINES) {
    if (p < s.box[0] || p > s.box[1] || y < s.box[2] || y > s.box[3]) continue;
    const half = s.w / 2;
    g = Math.max(g, s.d * (1 - smooth(half * 0.45, half, lineDistance(s.pts, p, y))));
  }
  const de = Math.abs(Math.hypot((p - EAR.phi) * ARC, y - EAR.y) - EAR.groove);
  return Math.max(g, 0.015 * (1 - smooth(0.008, 0.018, de)));
}

// Distance to the nearest seam, for keeping printed detail out of the grooves.
function seamDistance(p: number, y: number, within = Infinity): number {
  let d = Infinity;
  for (const s of SEAM_LINES) {
    if (p < s.box[0] - within || p > s.box[1] + within || y < s.box[2] - within || y > s.box[3] + within) continue;
    d = Math.min(d, lineDistance(s.pts, p, y));
  }
  return d;
}

// n + 1 positions from a to b, packed where density() is high.
function spaced(n: number, a: number, b: number, density: (v: number) => number): number[] {
  const steps = 4096;
  const acc = new Float64Array(steps + 1);
  for (let i = 1; i <= steps; i++) acc[i] = acc[i - 1] + density(a + ((b - a) * (i - 0.5)) / steps);
  const out: number[] = [];
  let j = 0;
  for (let k = 0; k <= n; k++) {
    const goal = (acc[steps] * k) / n;
    while (j < steps - 1 && acc[j + 1] < goal) j++;
    const f = Math.min(1, (goal - acc[j]) / (acc[j + 1] - acc[j] || 1));
    out.push(a + ((b - a) * (j + f)) / steps);
  }
  return out;
}

// A silhouette (listed top to bottom) as a lookup table over y, so a radius is one interpolation
// away.
function profile(points: Array<[number, number]>): (y: number) => number {
  const top = points[0][1];
  const span = top - points[points.length - 1][1];
  const samples = new THREE.SplineCurve(points.map(([x, y]) => new THREE.Vector2(x, y))).getPoints(600);
  const search = (y: number) => {
    for (let i = 0; i < samples.length - 1; i++) {
      const a = samples[i];
      const b = samples[i + 1];
      if ((y <= a.y && y >= b.y) || (y >= a.y && y <= b.y)) return a.x + (b.x - a.x) * ((y - a.y) / (b.y - a.y || 1e-6));
    }
    return samples[samples.length - 1].x;
  };
  const n = 1024;
  const lut = Float32Array.from({ length: n + 1 }, (_, i) => search(top - (span * i) / n));
  return (y) => {
    const f = Math.min(n, Math.max(0, ((top - y) / span) * n));
    const i = Math.min(n - 1, Math.floor(f));
    return lut[i] + (lut[i + 1] - lut[i]) * (f - i);
  };
}

// The iris: a lens aperture in light. A black pupil, a bright ring round it, blades curling out to
// a darker rim with fine ticks. White, so the material's colour tints it.
function irisTexture(): THREE.CanvasTexture {
  const c = Object.assign(document.createElement("canvas"), { width: 128, height: 128 });
  const g = c.getContext("2d")!;
  const o = 64;
  const grad = g.createRadialGradient(o, o, 0, o, o, 64);
  grad.addColorStop(0, "#000");
  grad.addColorStop(0.3, "#000");
  grad.addColorStop(0.33, "#fff");
  grad.addColorStop(0.5, "#e6e6e6");
  grad.addColorStop(0.78, "#7a7a7a");
  grad.addColorStop(0.94, "#2a2a2a");
  grad.addColorStop(1, "#000");
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  g.lineCap = "round";
  g.strokeStyle = "rgba(0,0,0,0.55)";
  g.lineWidth = 2.2;
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    g.beginPath();
    g.moveTo(o + Math.cos(a) * 22, o + Math.sin(a) * 22);
    g.quadraticCurveTo(o + Math.cos(a + 0.45) * 40, o + Math.sin(a + 0.45) * 40, o + Math.cos(a + 0.8) * 54, o + Math.sin(a + 0.8) * 54);
    g.stroke();
  }
  g.lineWidth = 1.2;
  for (let i = 0; i < 60; i++) {
    const a = (i / 60) * Math.PI * 2;
    g.beginPath();
    g.moveTo(o + Math.cos(a) * 55, o + Math.sin(a) * 55);
    g.lineTo(o + Math.cos(a) * 61, o + Math.sin(a) * 61);
    g.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// A small seeded random source, so the printed detail lands in the same places on every load.
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Ringed nodes where seams meet, (phi, y, radius).
const NODES: Array<[number, number, number]> = [
  [0.84, 0.05, 0.026], [0.76, -0.3, 0.022], [0.8, 0.78, 0.02], [2.2, 1.04, 0.02], [2.2, 0.42, 0.02], [2.24, -0.1, 0.018], [1.18, -0.56, 0.034],
];
// Gold chips, (phi, y, width, height).
const CHIPS: Array<[number, number, number, number]> = [
  [0.95, 0.42, 0.045, 0.022], [0.7, -0.17, 0.03, 0.045], [1.06, 0.82, 0.05, 0.026], [0.64, 0.64, 0.026, 0.026], [1.2, 0.52, 0.04, 0.018],
  [1.3, -0.4, 0.03, 0.03], [1.8, 0.62, 0.05, 0.022], [2.4, 0.15, 0.036, 0.022], [1.0, -0.62, 0.022, 0.04],
];

// `clip` cuts away everything below a world-space plane, so the hero can show the robot as a bust
// standing behind the map sheet without its torso running out below the sheet.
export function createRobot(clip?: THREE.Plane): Robot {
  const disposables: Array<{ dispose: () => void }> = [];
  const track = <T extends { dispose: () => void }>(x: T): T => {
    disposables.push(x);
    return x;
  };
  const Y = new THREE.Vector3(0, 1, 0);
  const Z = new THREE.Vector3(0, 0, 1);

  // Lacquer: a broad soft sheen in the base coat under a glossy clear coat, so the studio cards
  // glide across the face as soft gradients.
  const lacquer = track(new THREE.MeshPhysicalMaterial({ color: LACQUER, roughness: 0.36, metalness: 0.06, clearcoat: 1, clearcoatRoughness: 0.1, envMapIntensity: 1, dithering: true }));
  const graphite = track(new THREE.MeshPhysicalMaterial({ color: 0x0b0d0e, roughness: 0.22, metalness: 0.6, clearcoat: 1, clearcoatRoughness: 0.06 }));
  const core = track(new THREE.MeshStandardMaterial({ color: 0x080707, roughness: 0.8, metalness: 0.2, envMapIntensity: 0.3 }));
  const eyeball = track(new THREE.MeshPhysicalMaterial({ color: 0x020203, roughness: 0.05, metalness: 0.2, clearcoat: 1, clearcoatRoughness: 0.02, envMapIntensity: 1.6 }));
  const navy = track(new THREE.MeshPhysicalMaterial({ color: COL.blueFill, roughness: 0.3, metalness: 0.35, clearcoat: 0.9, clearcoatRoughness: 0.08, envMapIntensity: 0.9 }));
  // Polished gold: dark where it faces nothing, bright where it catches a card; only a faint warm
  // floor so traces on the shadow side do not vanish.
  const gold = track(new THREE.MeshPhysicalMaterial({ color: 0xeccb6e, metalness: 1, roughness: 0.18, emissive: 0x2e2208, emissiveIntensity: 1, envMapIntensity: 1.2 }));
  const silver = track(new THREE.MeshPhysicalMaterial({ color: 0xd4d6d8, roughness: 0.16, metalness: 1, envMapIntensity: 1.3 }));
  // Turned steel for the ear hubs. Anisotropy would add a radial highlight, but its shader alone
  // took about 2 s to compile on a laptop GPU, so the hub is plain polished steel.
  const turned = track(new THREE.MeshPhysicalMaterial({ color: 0xc9ccd0, metalness: 1, roughness: 0.3, envMapIntensity: 1.4 }));
  const lit = [lacquer, graphite, core, eyeball, navy, gold, silver, turned];
  if (clip) for (const m of lit) m.clippingPlanes = [clip];

  const front = profile(FRONT);
  const back = profile(BACK);

  // The head's radius at (phi, y): the two silhouettes blended around the head, the face sculpted
  // in, the grooves cut, and under the line of the jaw (y -0.86 at the chin rising to -0.66 at the
  // side) the head tucked in to the neck, so the chin and the angle of the jaw read as edges.
  const radiusAt = (phi: number, y: number, g = groove(Math.abs(phi), y)): number => {
    const p = Math.abs(phi);
    const w = smooth(-0.4, 0.95, Math.cos(phi));
    const r = back(y) + (front(y) - back(y)) * w + sculpt(phi, y) - g;
    const jaw = -0.86 + 0.2 * smooth(0, 1.5, p);
    const tuck = smooth(jaw + 0.01, jaw - 0.09, y) * (1 - smooth(1.7, 2.5, p));
    return r + (front(Y_BOTTOM) - r) * tuck;
  };
  const place = (phi: number, y: number, r: number): THREE.Vector3 => {
    const x = r * Math.sin(phi) * SX;
    let z = r * Math.cos(phi) * SZ;
    // The face is flatter across than the skull.
    if (z > 0) z *= 1 - 0.1 * Math.min(1, z / 0.9);
    return new THREE.Vector3(x, y, z);
  };
  const surf = (phi: number, y: number): THREE.Vector3 => place(phi, y, radiusAt(phi, y));
  const normalAt = (phi: number, y: number): THREE.Vector3 => {
    const e = 0.004;
    const dPhi = surf(phi + e, y).sub(surf(phi - e, y));
    const dY = surf(phi, y + e).sub(surf(phi, y - e));
    return dPhi.cross(dY).normalize();
  };
  const onSurface = (phi: number, y: number, lift: number) => surf(phi, y).add(normalAt(phi, y).multiplyScalar(lift));

  // The head mesh. Rows bunch up over the face (2.6 times tighter), columns over the front half of
  // the head (3.2 times), so the lids, nostrils, lip line and grooves have the resolution they need
  // and the back of the skull does not. Each row closes on itself, so there is no seam at the back.
  const ROWS = 330;
  const COLS = 340;
  const rowY = spaced(ROWS, Y_TOP, Y_BOTTOM, (y) => 1 + 1.6 * smooth(0.62, 0.48, y) * smooth(-0.98, -0.88, y));
  const colPhi = spaced(COLS, -Math.PI, Math.PI, (p) => 1 + 2.2 * (1 - smooth(1.1, 1.6, Math.abs(p)))).slice(0, COLS);
  const rad = new Float32Array((ROWS + 1) * COLS);
  const cut = new Float32Array((ROWS + 1) * COLS);
  const headGeo = (() => {
    const pos = new Float32Array((ROWS + 1) * COLS * 3);
    const idx: number[] = [];
    for (let r = 0; r <= ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const i = r * COLS + c;
        cut[i] = groove(Math.abs(colPhi[c]), rowY[r]);
        const rr = radiusAt(colPhi[c], rowY[r], cut[i]);
        rad[i] = rr;
        const v = place(colPhi[c], rowY[r], rr);
        pos.set([v.x, v.y, v.z], i * 3);
      }
    }
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const a = r * COLS + c;
        const b = r * COLS + ((c + 1) % COLS);
        // Counter-clockwise seen from outside, so the outside is the front face.
        idx.push(a, a + COLS, b, b, a + COLS, b + COLS);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setIndex(idx);
    geo.computeVertexNormals();
    return track(geo);
  })();

  // Light that cannot reach into a hollow, baked per vertex (there are no shadow maps): a point
  // lower than its neighbours gets less, the floors of the grooves go dark round their gold strips,
  // and the eye openings go almost black, so the corners the ball does not fill read as depth.
  const K = 6;
  const ao = new Float32Array(rad.length);
  for (let r = 0; r <= ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const i = r * COLS + c;
      const mean = (rad[Math.max(0, r - K) * COLS + c] + rad[Math.min(ROWS, r + K) * COLS + c] + rad[r * COLS + ((c - K + COLS) % COLS)] + rad[r * COLS + ((c + K) % COLS)]) / 4;
      const open = smooth(-0.006, 0.008, almond(Math.abs(colPhi[c]), rowY[r]));
      const cavity = Math.min(1, Math.max(0.25, 1 - 7 * (mean - rad[i])));
      ao[i] = cavity * (1 - 0.88 * open) * (1 - 0.8 * Math.min(1, cut[i] / 0.012));
    }
  }
  headGeo.setAttribute("ao", new THREE.BufferAttribute(ao, 1));
  const skin = track(lacquer.clone());
  skin.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nattribute float ao;\nvarying float vAo;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvAo = ao;");
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nvarying float vAo;").replace(
      "#include <aomap_fragment>",
      `#include <aomap_fragment>
      reflectedLight.indirectDiffuse *= vAo;
      reflectedLight.indirectSpecular *= vAo;
      reflectedLight.directDiffuse *= mix(1.0, vAo, 0.7);
      reflectedLight.directSpecular *= mix(1.0, vAo, 0.7);
      #ifdef USE_CLEARCOAT
        clearcoatSpecularIndirect *= vAo;
        clearcoatSpecularDirect *= mix(1.0, vAo, 0.7);
      #endif`,
    );
  };
  skin.customProgramCacheKey = () => "ciel-skin-ao";
  // clone() copies the plane; the head has to follow the stage's own.
  if (clip) skin.clippingPlanes = [clip];

  const group = new THREE.Group();
  // The head turns and nods about the top of the neck, so looking down brings the face forward and
  // down over the map instead of rolling the chin back into the neck.
  const pivot = new THREE.Group();
  pivot.position.set(0, -0.92, -0.06);
  group.add(pivot);
  const head = new THREE.Group();
  head.position.set(0, 0.92, 0.06);
  pivot.add(head);
  const mesh = (geo: THREE.BufferGeometry, mat: THREE.Material) => new THREE.Mesh(geo, mat);
  head.add(mesh(headGeo, skin));
  // The underside of the jaw, closed around the top of the neck.
  const cap = mesh(track(new THREE.CircleGeometry(front(Y_BOTTOM), 64)), core);
  cap.rotation.x = Math.PI / 2;
  cap.position.y = Y_BOTTOM;
  cap.scale.set(SX, SZ, 1);
  head.add(cap);

  // A gold strip at the floor of every groove, a little below the lacquer on either side.
  for (const s of [-1, 1]) {
    for (const seam of SEAM_LINES) {
      const pts = seam.pts.flatMap((v, i) => {
        const next = seam.pts[i + 1];
        if (!next) return [onSurface(s * v.x, v.y, 0.0045)];
        return [0, 0.5].map((t) => onSurface(s * (v.x + (next.x - v.x) * t), v.y + (next.y - v.y) * t, 0.0045));
      });
      head.add(mesh(track(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), pts.length * 2, 0.0075, 10)), gold));
    }
  }

  // Printed detail, as instances: gold dots dusted mostly along the traces, short rows of vias
  // beside them, dark nodes ringed in gold where seams meet, and small gold chips.
  const padGeo = track(new THREE.CylinderGeometry(1, 1, 1, 24));
  const ringGeo = track(new THREE.TorusGeometry(1, 0.22, 8, 32));
  const chipGeo = track(new THREE.BoxGeometry(1, 1, 1));
  const domeGeo = track(new THREE.SphereGeometry(1, 8, 4, 0, Math.PI * 2, 0, Math.PI / 2));
  type Item = { phi: number; y: number; s: [number, number, number]; lift: number };
  const scatter = (geo: THREE.BufferGeometry, mat: THREE.Material, up: THREE.Vector3, items: Item[]) => {
    const im = track(new THREE.InstancedMesh(geo, mat, items.length));
    const m4 = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const sc = new THREE.Vector3();
    items.forEach((it, i) => {
      q.setFromUnitVectors(up, normalAt(it.phi, it.y));
      im.setMatrixAt(i, m4.compose(onSurface(it.phi, it.y, it.lift), q, sc.set(...it.s)));
    });
    im.computeBoundingSphere();
    head.add(im);
  };
  const blocked = (phi: number, y: number) => {
    const p = Math.abs(phi);
    return (
      y < -0.84 ||
      y > 1.14 ||
      p > 2.7 ||
      (p < 0.6 && y > -0.95 && y < 0.5) ||
      Math.hypot((p - EYE.phi) * ARC, y - EYE.y) < 0.2 ||
      Math.hypot((p - EAR.phi) * ARC, y - EAR.y) < 0.44 ||
      seamDistance(p, y, 0.05) < 0.034
    );
  };
  const rand = mulberry32(1189);
  const dots: Item[] = [];
  const dot = (phi: number, y: number, r: number) => dots.push({ phi, y, s: [r, r * 0.55, r], lift: 0 });
  for (let guard = 0, n = 0; n < 200 && guard < 20000; guard++) {
    const phi = (rand() * 2 - 1) * 2.7;
    const y = -0.84 + rand() * 1.98;
    if (blocked(phi, y)) continue;
    const d = seamDistance(Math.abs(phi), y, 0.3);
    if (rand() > 0.12 + 0.88 * gauss(d, 0.05, 0.045)) continue;
    dot(phi, y, 0.0045 + 0.0045 * rand() ** 2);
    n++;
  }
  const seamPts = SEAM_LINES.flatMap((s) => s.pts.slice(0, -1).map((v, i) => [v.x, v.y, s.pts[i + 1].x - v.x, s.pts[i + 1].y - v.y]));
  for (let k = 0; k < 18; k++) {
    const [p, q, tp, tq] = seamPts[Math.floor(rand() * seamPts.length)];
    const side = rand() < 0.5 ? -1 : 1;
    const l = Math.hypot(tp * ARC, tq) || 1;
    const ux = (tp * ARC) / l;
    const uy = tq / l;
    const off = rand() < 0.5 ? 0.05 : -0.05;
    for (let i = 0, count = 4 + Math.floor(rand() * 3); i < count; i++) {
      const phi = p + (-uy * off + ux * 0.024 * i) / ARC;
      const y = q + ux * off + uy * 0.024 * i;
      if (!blocked(phi, y)) dot(side * phi, y, 0.005);
    }
  }
  const discs: Item[] = [];
  const rings: Item[] = [];
  for (const s of [-1, 1]) {
    for (const [p, y, r] of NODES) {
      // Nodes sit on the lacquer over a junction of grooves, so they stand proud of the floor.
      const lift = groove(p, y);
      discs.push({ phi: s * p, y, s: [r, 0.012, r], lift: lift + 0.004 });
      rings.push({ phi: s * p, y, s: [r, r, r], lift: lift + 0.01 });
      dots.push({ phi: s * p, y, s: [r * 0.35, r * 0.2, r * 0.35], lift: lift + 0.009 });
    }
  }
  scatter(domeGeo, gold, Y, dots);
  scatter(padGeo, graphite, Y, discs);
  scatter(ringGeo, gold, Z, rings);
  scatter(chipGeo, gold, Z, [-1, 1].flatMap((s) => CHIPS.map(([p, y, w, h]): Item => ({ phi: s * p, y, s: [w, h, 0.012], lift: 0.004 }))));

  // The eyes: a large glossy ball just behind the lids of each almond, an iris of light curved onto
  // the ball with a glassy cornea over it, and an upper lid (a lacquer shell round the ball) that
  // blinks, squints and follows the gaze down.
  const R = EYE.ball;
  const cap0 = (r0: number, r1: number, lift: number) => {
    const t0 = Math.asin(r0 / R);
    const g = new THREE.SphereGeometry(R + lift, 48, 4, 0, Math.PI * 2, t0, Math.asin(r1 / R) - t0);
    // The cap's pole from +y to +z, where the eye looks.
    g.rotateX(Math.PI / 2);
    // Planar UVs across the cap, so the round iris texture lands flat on it.
    const p = g.attributes.position;
    const uv = new Float32Array(p.count * 2);
    for (let i = 0; i < p.count; i++) uv.set([p.getX(i) / (2 * r1) + 0.5, p.getY(i) / (2 * r1) + 0.5], i * 2);
    g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    return track(g);
  };
  const ballGeo = track(new THREE.SphereGeometry(R, 48, 32));
  const irisGeo = cap0(0, 0.046, 0.0015);
  const haloGeo = cap0(0.044, 0.075, 0.003);
  const corneaGeo = track(new THREE.SphereGeometry(0.075, 32, 8, 0, Math.PI * 2, 0, 0.75).rotateX(Math.PI / 2));
  // Covers the top of the ball over the front +-77 degrees; open, its edge sits behind the upper lid.
  const lidGeo = track(new THREE.SphereGeometry(R + 0.006, 40, 14, Math.PI / 2 - 1.35, 2.7, 0, 1.05));
  const irisMat = track(new THREE.MeshBasicMaterial({ color: COL.blue, map: track(irisTexture()), toneMapped: false }));
  const haloMat = track(new THREE.MeshBasicMaterial({ color: COL.blue, toneMapped: false, transparent: true, opacity: 0.18, blending: THREE.AdditiveBlending, depthWrite: false }));
  // Black and additive: only the studio's highlights land on the eye, like glass over the iris.
  const corneaMat = track(new THREE.MeshPhysicalMaterial({ color: 0x000000, roughness: 0.03, metalness: 0, envMapIntensity: 2.6, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  if (clip) for (const m of [irisMat, haloMat, corneaMat]) m.clippingPlanes = [clip];
  const eyeRigs: Array<{ rig: THREE.Group; iris: THREE.Mesh; halo: THREE.Mesh; lid: THREE.Mesh }> = [];
  for (const s of [-1, 1]) {
    const phi = s * EYE.phi;
    const n = normalAt(phi, EYE.y);
    const holder = new THREE.Group();
    // radiusAt() at the centre is the floor of the opening; adding the cut back gives the lids'
    // level. The front of the ball sits 0.008 above it, so the lid margins overlap its top and bottom.
    const lids = place(phi, EYE.y, radiusAt(phi, EYE.y) + EYE.cut);
    holder.position.copy(lids).addScaledVector(n, 0.008 - R);
    // Look out of the socket, a touch toward the middle like real eyes.
    holder.lookAt(holder.position.clone().add(new THREE.Vector3(n.x * 0.5, n.y, Math.abs(n.z) + 0.4)));
    const rig = new THREE.Group();
    holder.add(rig);
    rig.add(mesh(ballGeo, eyeball));
    const iris = mesh(irisGeo, irisMat);
    rig.add(iris);
    const halo = mesh(haloGeo, haloMat);
    rig.add(halo);
    const cornea = mesh(corneaGeo, corneaMat);
    cornea.position.z = R + 0.004 - 0.075;
    rig.add(cornea);
    // The lid shares the almond's tilt (outer corner up), then closes about its own x axis.
    const tilt = new THREE.Group();
    tilt.rotation.z = s * EYE.tilt;
    holder.add(tilt);
    const lid = mesh(lidGeo, lacquer);
    tilt.add(lid);
    head.add(holder);
    eyeRigs.push({ rig, iris, halo, lid });
  }
  // Just in front of the eyes, so the glow falls on the sockets and the bridge of the nose.
  const eyeLight = new THREE.PointLight(COL.blue, 0, 1, 2);
  eyeLight.position.set(0, EYE.y, 1.12);
  head.add(eyeLight);
  const blue = new THREE.Color(COL.blue);
  const warm = new THREE.Color(COL.gold);
  const tint = new THREE.Color();
  const eyes = {
    set: (s: EyeState) => {
      tint.copy(blue).lerp(warm, s.gold);
      irisMat.color.copy(tint).multiplyScalar(0.15 + 0.85 * s.glow);
      haloMat.color.copy(tint);
      haloMat.opacity = (0.16 + 0.2 * s.gold) * Math.min(1, s.glow);
      eyeLight.color.copy(tint);
      for (const e of eyeRigs) {
        e.rig.rotation.set(s.y * 0.32, s.x * 0.42, 0);
        e.iris.scale.set(s.size, s.size, 1);
        e.halo.scale.set(s.size, s.size, 1);
        // 0 open (its edge behind the upper lid) .. 0.82 shut on the lower lid; lowers as the eyes
        // look down.
        e.lid.rotation.x = THREE.MathUtils.clamp(0.82 * (1 - s.open) + 0.22 * s.y, -0.06, 0.82);
      }
    },
  };

  // The ears: recessed dials. A lacquer boss, a dark cup, two bevelled gold collars, a turned steel
  // hub carrying the Kepingan logo, and a steel lever leaning out from it.
  const extrude = (d: string, depth: number) => {
    const data = new SVGLoader().parse(`<svg xmlns="http://www.w3.org/2000/svg"><path d="${d}"/></svg>`);
    const shapes = data.paths.flatMap((p) => p.toShapes());
    const geo = new THREE.ExtrudeGeometry(shapes, { depth, bevelEnabled: true, bevelThickness: 0.5, bevelSize: 0.3, bevelSegments: 6, curveSegments: 56 });
    geo.translate(-14.4, -16, 0);
    // SVG y runs down. The mirror flips every triangle's winding, so swap two corners of each back.
    geo.scale(1, -1, 1);
    for (const name of ["position", "normal", "uv"]) {
      const a = geo.getAttribute(name) as THREE.BufferAttribute;
      const n = a.itemSize;
      for (let t = 0; t < a.count; t += 3) {
        for (let k = 0; k < n; k++) {
          const i = (t + 1) * n + k;
          const j = (t + 2) * n + k;
          const v = a.array[i];
          a.array[i] = a.array[j];
          a.array[j] = v;
        }
      }
    }
    return track(geo);
  };
  const markRingGeo = extrude(RING, 1.6);
  const markPieceGeo = extrude(PIECE, 1.6);
  // Profiles are (radius, height above the skull's tangent plane), outer to inner, so normals face
  // out. Doubling a point gives the lathe a crisp edge there.
  const lathe = (pts: Array<[number, number]>, seg = 96, hard = false) => {
    const v = pts.map(([r, h]) => new THREE.Vector2(r, h));
    const all = hard ? v.flatMap((p, i) => (i === 0 || i === v.length - 1 ? [p] : [p, p.clone()])) : v;
    return track(new THREE.LatheGeometry(all, seg));
  };
  const bossGeo = lathe([[0.37, -0.11], [0.37, -0.01], [0.355, 0.025], [0.33, 0.038]]);
  const cupGeo = lathe([[0.272, 0.05], [0.262, 0.0], [0.24, -0.03], [0.17, -0.042]], 96, true);
  const collarGeo = lathe([[0.33, 0.036], [0.338, 0.058], [0.328, 0.074], [0.306, 0.079], [0.29, 0.07], [0.284, 0.052], [0.27, 0.05]]);
  const innerGeo = lathe([[0.214, -0.04], [0.222, -0.002], [0.214, 0.017], [0.197, 0.02], [0.188, 0.004]]);
  const hubGeo = lathe([[0.168, -0.045], [0.168, 0.0], [0.15, 0.006], [0.14, 0.006], [0.135, 0.015], [0.108, 0.015], [0.103, 0.024], [0.074, 0.024], [0.07, 0.032], [0.0, 0.034]], 72, true);
  const leverGeo = track(new THREE.CapsuleGeometry(0.016, 0.28, 4, 12));
  const knobGeo = track(new THREE.SphereGeometry(0.03, 16, 12));
  for (const side of [-1, 1]) {
    const n = normalAt(side * EAR.phi, EAR.y);
    // Up along the skull, and toward the face.
    const u = Y.clone().addScaledVector(n, -n.dot(Y)).normalize();
    const f = new THREE.Vector3().crossVectors(n, u).multiplyScalar(side);
    const m = new THREE.Group();
    m.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(u, n, new THREE.Vector3().crossVectors(u, n)));
    m.position.copy(surf(side * EAR.phi, EAR.y)).addScaledVector(n, -0.01);
    m.add(mesh(bossGeo, lacquer), mesh(cupGeo, core), mesh(collarGeo, gold), mesh(innerGeo, gold), mesh(hubGeo, turned));
    const emblem = new THREE.Group();
    emblem.add(mesh(markRingGeo, navy));
    const piece = mesh(markPieceGeo, gold);
    piece.position.z = 0.7;
    emblem.add(piece);
    emblem.scale.setScalar(0.0105);
    // Facing out along the hub's axis, the gold piece toward the face on both sides.
    emblem.rotation.set(-Math.PI / 2, (side * Math.PI) / 2, 0, "YXZ");
    emblem.position.y = 0.036;
    m.add(emblem);
    head.add(m);
    // The lever pivots on the hub's lower back edge and leans out, down and back over the collar.
    const at = m.position.clone().addScaledVector(n, 0.05).addScaledVector(u, -0.11).addScaledVector(f, -0.11);
    const dir = new THREE.Vector3().addScaledVector(n, 0.45).addScaledVector(u, -0.75).addScaledVector(f, -0.5).normalize();
    const knob = mesh(knobGeo, silver);
    knob.position.copy(at);
    head.add(knob);
    const lever = mesh(leverGeo, silver);
    lever.quaternion.setFromUnitVectors(Y, dir);
    lever.position.copy(at).addScaledVector(dir, 0.15);
    head.add(lever);
  }

  // Neck: a black armoured sleeve. Overlapping throat plates, a spine at the back, and two columns
  // leaning from behind the ears down to the collar, each carrying a gold line.
  const neck = new THREE.Group();
  neck.add(mesh(track(new THREE.CylinderGeometry(0.29, 0.33, 1.0, 48)), graphite));
  const nm = new THREE.Matrix4();
  const ribs = track(new THREE.InstancedMesh(track(new THREE.CylinderGeometry(0.33, 0.345, 0.06, 48, 1, false, -1.75, 3.5)), graphite, 9));
  for (let i = 0; i < 9; i++) ribs.setMatrixAt(i, nm.makeTranslation(0, 0.38 - i * 0.085, 0));
  ribs.computeBoundingSphere();
  neck.add(ribs);
  const spine = track(new THREE.InstancedMesh(track(new THREE.BoxGeometry(0.2, 0.07, 0.12)), graphite, 8));
  for (let i = 0; i < 8; i++) spine.setMatrixAt(i, nm.makeTranslation(0, 0.4 - i * 0.11, -0.3));
  spine.computeBoundingSphere();
  neck.add(spine);
  const tendonGeo = track(new THREE.CylinderGeometry(0.048, 0.06, 1.0, 20));
  const stripGeo = track(new THREE.BoxGeometry(0.013, 0.98, 0.013));
  for (const s of [-1, 1]) {
    const t = mesh(tendonGeo, graphite);
    t.position.set(s * 0.26, -0.04, 0.02);
    t.rotation.set(-0.2, 0, -s * 0.14);
    const strip = mesh(stripGeo, gold);
    strip.position.x = s * 0.05;
    t.add(strip);
    neck.add(t);
  }
  neck.position.y = -1.42;
  group.add(neck);
  for (const [sx, sz, bow] of [[-0.26, -0.26, 0.1], [0.26, -0.26, 0.1], [-0.38, -0.04, 0.06], [0.38, -0.04, 0.06]]) {
    const cable = new THREE.CatmullRomCurve3([
      new THREE.Vector3(sx * 0.8, -0.98, sz),
      new THREE.Vector3(sx * 1.2, -1.4, sz - bow),
      new THREE.Vector3(sx * 1.3, -1.88, sz + 0.02),
    ]);
    group.add(mesh(track(new THREE.TubeGeometry(cable, 32, 0.026, 10)), graphite));
  }
  const torsoCurve = new THREE.SplineCurve(TORSO.map(([x, y]) => new THREE.Vector2(x, y)));
  const torso = mesh(track(new THREE.LatheGeometry(torsoCurve.getPoints(72).sort((a, b) => a.y - b.y), 128)), lacquer);
  torso.scale.z = TORSO_DEPTH;
  group.add(torso);
  // Gold seams on the shoulders: a collarbone line on each side from the collar out over the
  // shoulder, with a ringed node where it bends, pressed onto the torso like the face's inlay.
  const torsoRadius = profile(TORSO);
  const onTorso = (theta: number, y: number, lift: number) => {
    const at = (t: number, yy: number) => new THREE.Vector3(torsoRadius(yy) * Math.sin(t), yy, torsoRadius(yy) * Math.cos(t) * TORSO_DEPTH);
    const e = 0.004;
    const n = at(theta + e, y).sub(at(theta - e, y)).cross(at(theta, y + e).sub(at(theta, y - e))).normalize();
    return { p: at(theta, y).add(n.clone().multiplyScalar(lift)), n };
  };
  for (const s of [-1, 1]) {
    const seam = new THREE.SplineCurve([[0.42, -1.97], [0.72, -2.05], [1.05, -2.2], [1.36, -2.5]].map(([t, y]) => new THREE.Vector2(s * t, y)));
    const pts = seam.getPoints(96).map((v) => onTorso(v.x, v.y, 0.006).p);
    group.add(mesh(track(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 192, 0.013, 12)), gold));
    const node = onTorso(s * 0.72, -2.05, 0.006);
    const disc = mesh(padGeo, graphite);
    disc.position.copy(node.p);
    disc.quaternion.setFromUnitVectors(Y, node.n);
    disc.scale.set(0.03, 0.014, 0.03);
    group.add(disc);
    const rim = mesh(ringGeo, gold);
    rim.position.copy(onTorso(s * 0.72, -2.05, 0.014).p);
    rim.quaternion.setFromUnitVectors(Z, node.n);
    rim.scale.setScalar(0.03);
    group.add(rim);
  }
  const collar = mesh(track(new THREE.TorusGeometry(0.44, 0.055, 20, 72)), graphite);
  collar.rotation.x = Math.PI / 2;
  collar.position.y = -1.9;
  collar.scale.y = 0.7;
  group.add(collar);
  for (const [ry, rr] of [[-2.25, 1.52], [-2.9, 1.83]]) {
    const s = mesh(track(new THREE.TorusGeometry(rr, 0.01, 6, 160)), gold);
    s.rotation.x = Math.PI / 2;
    s.position.y = ry;
    s.scale.y = 0.56;
    group.add(s);
  }
  const sternum = mesh(track(new THREE.BoxGeometry(0.014, 2.4, 0.02)), gold);
  sternum.position.set(0, -3.1, 1.05);
  group.add(sternum);

  return {
    group,
    head: pivot,
    eyes,
    eyeLight,
    dispose: () => disposables.forEach((d) => d.dispose()),
  };
}
