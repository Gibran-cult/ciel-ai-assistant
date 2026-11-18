// Shared, non-React state the 3D robot reads every frame. Sections, the map and the CTA write
// to it; keeping it outside React means a pointer move never re-renders the page.

export type Pose = {
  x: number;
  y: number;
  scale: number;
  yaw: number;
  pitch: number;
  hyaw: number;
  hpitch: number;
  light: number;
  // Height of the clipping cut in the robot's own units. Below the torso (-4.2) nothing is cut.
  cut: number;
};

// The bust frame in the robot's own units: from just above the head to a cut through the chest,
// wide enough for the shoulders at any turn. The poster image is exactly this frame, and the
// anchored poses fit this frame to the poster's box on the page.
export const BUST = { top: 1.34, bottom: -2.9, half: 1.95 };

// World units at the robot's plane, for the poses that stand in the viewport (palsu, away); they
// match the 1440 x 900 frame. "hero", "mobile", "story" and "closing" are anchored: the robot's
// position and size come from a bust box on the page ([data-robot-anchor]), so its chest cut always
// sits behind something (the map sheet, the route strip, the bottom edge of the screen, the footer)
// at every screen size. Their x, y and scale are only a fallback for when the box is missing.
// The head turns and nods about the top of the neck (hyaw, hpitch). Outside the closing section it
// stays between three-quarter and profile, the angle the sculpted face reads best at.
export const poses = {
  hero: { x: 1.79, y: 0.62, scale: 0.5, yaw: -0.45, pitch: 0.05, hyaw: -0.4, hpitch: 0.45, light: 1, cut: BUST.bottom },
  story: { x: 2.3, y: -0.75, scale: 0.34, yaw: -0.55, pitch: 0.04, hyaw: -0.45, hpitch: 0.22, light: 1, cut: BUST.bottom },
  palsu: { x: 1.62, y: 0.1, scale: 0.88, yaw: -0.5, pitch: 0.03, hyaw: -0.3, hpitch: 0.2, light: 0.55, cut: -5 },
  // Far enough right to leave the frame at every desktop aspect ratio, shoulders included.
  away: { x: 8, y: 0.7, scale: 0.8, yaw: -0.95, pitch: 0.1, hyaw: -0.2, hpitch: 0.1, light: 0, cut: -5 },
  closing: { x: 1.6, y: 0.2, scale: 0.7, yaw: -0.35, pitch: 0.02, hyaw: -0.3, hpitch: 0.1, light: 1.3, cut: BUST.bottom },
  mobile: { x: 0.55, y: 0.35, scale: 0.5, yaw: -0.4, pitch: 0.05, hyaw: -0.4, hpitch: 0.42, light: 1, cut: BUST.bottom },
} satisfies Record<string, Pose>;

export type PoseName = keyof typeof poses;

// How far the head turns toward the pointer in each pose, measured from the head's own place on
// screen, and the limits that keep it from facing the viewer outside the closing section. eyes is
// the gaze gain, eyeMax how far the irises may turn toward the viewer, down a downward bias for
// the poses where the robot reads the map.
export type Follow = { yaw: number; pitch: number; minYaw: number; maxYaw: number; minPitch: number; maxPitch: number; eyes: number; eyeMax: number; down: number };
export const follow: Record<PoseName, Follow> = {
  hero: { yaw: 0.55, pitch: 0.22, minYaw: -0.25, maxYaw: 0.15, minPitch: -0.12, maxPitch: 0.14, eyes: 0.8, eyeMax: 0.3, down: 0.45 },
  mobile: { yaw: 0.3, pitch: 0.12, minYaw: -0.2, maxYaw: 0.08, minPitch: -0.08, maxPitch: 0.1, eyes: 0.6, eyeMax: 0.25, down: 0.45 },
  story: { yaw: 0.4, pitch: 0.15, minYaw: -0.3, maxYaw: 0.05, minPitch: -0.1, maxPitch: 0.1, eyes: 0.8, eyeMax: 0.3, down: 0 },
  palsu: { yaw: 0.3, pitch: 0.12, minYaw: -0.25, maxYaw: 0.08, minPitch: -0.08, maxPitch: 0.1, eyes: 0.7, eyeMax: 0.3, down: 0 },
  closing: { yaw: 0.5, pitch: 0.2, minYaw: -0.4, maxYaw: 0.1, minPitch: -0.12, maxPitch: 0.12, eyes: 1, eyeMax: 1, down: 0 },
  away: { yaw: 0, pitch: 0, minYaw: 0, maxYaw: 0, minPitch: 0, maxPitch: 0, eyes: 0, eyeMax: 0, down: 0 },
};

// Poses whose position comes from a box on the page, keyed by the box's data-robot-anchor value.
export const anchored: Partial<Record<PoseName, string>> = { hero: "hero", mobile: "mobile", story: "story", closing: "closing" };

export const robotState = {
  pose: "hero" as PoseName,
  // Pointer in normalised device coordinates (-1..1), y down.
  pointer: { x: 0, y: 0 },
  // When the primary button is hovered or focused, the robot looks at it (NDC, y down).
  focus: null as null | { x: number; y: number },
  // A one-off head shake ("no") starts at this performance.now() time.
  shakeAt: -1,
  // A short reaction the eyes play once (RobotStage): both start by sweeping side to side, then
  // "found" warms the irises to gold and "missing" dims them while the head shakes. "at" is its
  // performance.now() start.
  mood: { name: "idle" as Mood, at: -1 },
};

export type Mood = "idle" | "found" | "missing";

// The robot only draws when something changes (RobotStage). Anything that changes robotState
// without a pointer move, scroll or focus change announces it with this event.
export const WAKE = "ciel:robot";

export function wakeRobot() {
  window.dispatchEvent(new Event(WAKE));
}

type Listener = () => void;
const listeners = new Set<Listener>();
let ready = false;

export function onCanvasReady(fn: Listener) {
  if (ready) fn();
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function emitCanvasReady() {
  if (ready) return;
  ready = true;
  listeners.forEach((fn) => fn());
}

// A new canvas (after a breakpoint or settings change) has to draw its own first frame before the
// still bust may fade out again.
export function resetCanvasReady() {
  ready = false;
}

export function setPose(name: PoseName) {
  robotState.pose = name;
  wakeRobot();
}

export function setMood(name: Mood) {
  robotState.mood = { name, at: performance.now() };
  wakeRobot();
}
