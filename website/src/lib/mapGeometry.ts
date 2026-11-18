// Map geometry for the investigation map. Seeded, so the server render and the browser render
// draw the same coastlines and hydration matches. Units are the SVG viewBox (900 x 500).

export type Pt = [number, number];

export type Island = {
  id: string;
  label: string;
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  seed: number;
  labelAt: Pt;
};

export const VIEW = { w: 900, h: 500 };

export const islands: Island[] = [
  { id: "arxiv", label: "arxiv.org", cx: 430, cy: 170, rx: 120, ry: 72, seed: 11, labelAt: [430, 268] },
  { id: "neurips", label: "proceedings.neurips.cc", cx: 690, cy: 108, rx: 92, ry: 54, seed: 23, labelAt: [690, 38] },
  { id: "acl", label: "aclanthology.org", cx: 486, cy: 380, rx: 150, ry: 52, seed: 37, labelAt: [486, 462] },
  { id: "doi", label: "doi.org", cx: 792, cy: 240, rx: 52, ry: 36, seed: 41, labelAt: [792, 298] },
  { id: "scikit", label: "scikit-learn.org", cx: 182, cy: 112, rx: 62, ry: 36, seed: 53, labelAt: [182, 170] },
  { id: "openstax", label: "openstax.org", cx: 262, cy: 300, rx: 48, ry: 30, seed: 67, labelAt: [262, 350] },
];

export const start: Pt = [70, 255];
export const fakeSpot: Pt = [92, 396];
// The trail toward the fake journal: from the question into open water, where it is struck out.
// When that question is the one on the map (its own case), it starts at the main ring.
export const fakeTrail: Pt[] = [start, [56, 322], fakeSpot];
// Beside another case it was a separate question in the test, so it starts at a ring of its own.
export const fakeAside: Pt[] = [[44, 334], [58, 368], fakeSpot];

// Where each real case's numbered sources sit, in the order of the answer's source list.
export const casePins: Record<"vaswani" | "koto", Pt[]> = {
  vaswani: [[380, 146], [432, 205], [486, 138], [690, 103]],
  koto: [[378, 384], [452, 214], [540, 380], [792, 238]],
};
export const storyPins: Pt[] = [[182, 110], [262, 298]];

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const r1 = (n: number) => Math.round(n);

export function outline(island: Island, scale = 1, shift: Pt = [0, 0], n = 40): Pt[] {
  const rnd = mulberry32(island.seed);
  const harmonics = [2, 3, 4, 5, 7].map((k) => ({ k, a: (0.25 + rnd() * 0.5) * (0.24 / k) * 2, p: rnd() * Math.PI * 2 }));
  const pts: Pt[] = [];
  for (let j = 0; j < n; j++) {
    const t = (j / n) * Math.PI * 2;
    let r = 1;
    for (const h of harmonics) r += h.a * Math.sin(h.k * t + h.p);
    pts.push([r1(island.cx + shift[0] + Math.cos(t) * island.rx * r * scale), r1(island.cy + shift[1] + Math.sin(t) * island.ry * r * scale)]);
  }
  return pts;
}

// Contour rings drift a little toward one side, the way real elevation lines do.
export function contours(island: Island): Pt[][] {
  const rnd = mulberry32(island.seed * 7 + 3);
  return [0.7, 0.4].map((s) => outline(island, s, [r1((rnd() - 0.5) * island.rx * 0.18), r1((rnd() - 0.5) * island.ry * 0.18)]));
}

// Catmull-Rom through the points, written as cubic Beziers.
export function smoothPath(pts: Pt[], closed = false): string {
  if (pts.length < 2) return "";
  const get = (i: number): Pt => {
    if (closed) return pts[(i + pts.length) % pts.length];
    return pts[Math.max(0, Math.min(pts.length - 1, i))];
  };
  const count = closed ? pts.length : pts.length - 1;
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < count; i++) {
    const p0 = get(i - 1);
    const p1 = get(i);
    const p2 = get(i + 1);
    const p3 = get(i + 2);
    const c1: Pt = [r1(p1[0] + (p2[0] - p0[0]) / 6), r1(p1[1] + (p2[1] - p0[1]) / 6)];
    const c2: Pt = [r1(p2[0] - (p3[0] - p1[0]) / 6), r1(p2[1] - (p3[1] - p1[1]) / 6)];
    d += ` C${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${p2[0]} ${p2[1]}`;
  }
  return closed ? `${d} Z` : d;
}

// Depth lines: open contours that cross the whole sheet, edge to edge, the way soundings run on a
// chart. They start and end outside the neatline and are clipped to it.
export const isobaths: string[] = [
  { y: 58, amp: 16, seed: 5 },
  { y: 236, amp: 22, seed: 9 },
  { y: 470, amp: 12, seed: 13 },
].map(({ y, amp, seed }) => {
  const rnd = mulberry32(seed);
  const phase = rnd() * Math.PI * 2;
  const pts: Pt[] = [];
  for (let x = -30; x <= VIEW.w + 30; x += 60) {
    pts.push([x, r1(y + Math.sin(x / 130 + phase) * amp + (rnd() - 0.5) * amp * 0.6)]);
  }
  return smoothPath(pts);
});

// A gentle curve beside the island for its name, so the lettering follows the land instead of
// sitting on a ruler. Below the island the curve smiles, above it frowns. `size` is the font size
// in viewBox units; the curve clears the island's real outline, not just its ellipse.
export function labelCurve(island: Island, size: number): string {
  const pts = outline(island);
  const above = island.labelAt[1] < island.cy;
  const half = Math.max(island.label.length * size * 0.3, island.rx * 0.7);
  const sag = Math.min(14, island.ry * 0.28);
  if (above) {
    const top = Math.min(...pts.map((p) => p[1]));
    const y = top - 10;
    return `M${r1(island.cx - half)} ${r1(y + sag)} Q${island.cx} ${r1(y - sag)} ${r1(island.cx + half)} ${r1(y + sag)}`;
  }
  const bottom = Math.max(...pts.map((p) => p[1]));
  const y = bottom + size * 1.05;
  return `M${r1(island.cx - half)} ${r1(y - sag)} Q${island.cx} ${r1(y + sag)} ${r1(island.cx + half)} ${r1(y - sag)}`;
}

// A rough length for a route, enough to set a dash offset before the browser can measure it.
export function approxLength(pts: Pt[]): number {
  let len = 0;
  for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return Math.ceil(len * 1.12);
}
