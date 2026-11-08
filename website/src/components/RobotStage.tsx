"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment, Lightformer, PerformanceMonitor } from "@react-three/drei";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { createRobot } from "@/three/robot";
import { anchored, BUST, emitCanvasReady, follow, poses, robotState, WAKE, type Pose, type PoseName } from "@/lib/robotBus";

const BASE_FOV = 24;

// The camera "contains" its reference frame exactly like `object-fit: contain` contains a poster:
// on screens narrower than the frame it widens the field of view, so the robot shrinks with the
// width instead of crowding the text in the sections where it stands in the viewport.
function ContainCamera({ refAspect }: { refAspect: number }) {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const aspect = size.width / size.height;
    const half = THREE.MathUtils.degToRad(BASE_FOV / 2);
    camera.fov = aspect < refAspect ? THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(half) * (refAspect / aspect))) : BASE_FOV;
    camera.aspect = aspect;
    camera.position.set(0, 0.1, 8.6);
    camera.lookAt(0, -0.2, 0);
    camera.updateProjectionMatrix();
    // lookAt leaves matrixWorld from the previous orientation until the next render; the anchored
    // poses unproject through it before that render.
    camera.updateMatrixWorld();
    invalidate();
  }, [camera, size, refAspect, invalidate]);
  return null;
}

// Where an anchored pose should stand: the bust box on the page, unprojected onto the robot's
// plane (z = 0), gives the bust frame's world rectangle, and from that its position and size.
const ray = new THREE.Raycaster();
const plane0 = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
const ndc = new THREE.Vector2();
const corner = new THREE.Vector3();

function anchorTarget(name: string, canvas: HTMLCanvasElement, camera: THREE.Camera): { x: number; y: number; scale: number } | null {
  const box = document.querySelector<HTMLElement>(`[data-robot-anchor="${name}"]`)?.getBoundingClientRect();
  if (!box || !box.width || !box.height) return null;
  const c = canvas.getBoundingClientRect();
  camera.updateMatrixWorld();
  const toWorld = (px: number, py: number) => {
    ndc.set(((px - c.left) / c.width) * 2 - 1, -((py - c.top) / c.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    return ray.ray.intersectPlane(plane0, corner) ? { x: corner.x, y: corner.y } : null;
  };
  const tl = toWorld(box.left, box.top);
  const br = toWorld(box.right, box.bottom);
  if (!tl || !br) return null;
  const scale = (tl.y - br.y) / (BUST.top - BUST.bottom);
  return { x: (tl.x + br.x) / 2, y: tl.y - BUST.top * scale, scale };
}

const EPS = 1e-3;
const headNdc = new THREE.Vector3();
const clamp = THREE.MathUtils.clamp;

// The scene draws on demand: a frame is requested by a pointer move, a scroll, a resize, a focus
// change or a robot event (robotBus WAKE), and the robot keeps requesting frames only while it is
// still moving toward its pose. On phones nothing is drawn while the block is off screen.
function Robot({ mobile, onMoving }: { mobile: boolean; onMoving: (moving: boolean) => void }) {
  // Cuts the torso off below the bust frame in the anchored poses; out of the way otherwise.
  const clip = useMemo(() => new THREE.Plane(new THREE.Vector3(0, 1, 0), 1000), []);
  const robot = useMemo(() => createRobot(clip), [clip]);
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  // The robot's shaders compile in parallel off the main thread before it is first drawn; until
  // then the still bust stays on the page, so a slow compile shows as nothing at all.
  const [compiled, setCompiled] = useState(false);
  const ready = useRef(false);
  const rake = useRef<THREE.SpotLight>(null);
  const invalidate = useThree((s) => s.invalidate);
  const camera = useThree((s) => s.camera);
  const canvas = useThree((s) => s.gl.domElement);
  const cur = useRef<Pose>({ ...(mobile ? poses.mobile : poses.hero) });
  const look = useRef({ yaw: 0, pitch: 0, boost: 0 });
  // The head's part in a reaction: it scans with the eyes, nods once for "found", droops for "missing".
  const moodHead = useRef({ yaw: 0, pitch: 0, roll: 0 });
  // The eyes: where they look, how wide and bright the irises are, how warm (blue to gold), when
  // they last blinked and when the robot woke.
  const eyes = useRef({ x: 0, y: 0, size: 1, glow: 1, gold: 0, blinkAt: -1, wokeAt: -1, shookFor: -1, tilt: 0 });
  // True while the pointer rests on (or a finger has just tapped) the robot's head.
  const greet = useRef(false);
  const frames = useRef(0);
  const moving = useRef(false);
  const parked = useRef(false);
  // When the current pose began, so an anchored pose can arrive with weight and then hold on.
  const since = useRef<{ name: PoseName | ""; at: number }>({ name: "", at: 0 });

  useEffect(() => () => robot.dispose(), [robot]);
  useEffect(() => {
    let alive = true;
    gl.compileAsync(robot.group, camera, scene)
      .catch(() => undefined)
      .then(() => {
        if (!alive) return;
        ready.current = true;
        setCompiled(true);
        invalidate();
      });
    return () => {
      alive = false;
    };
  }, [gl, robot, camera, scene, invalidate]);
  useEffect(() => {
    if (rake.current) rake.current.target = robot.group;
  }, [robot]);

  useEffect(() => {
    const onScreen = () => {
      const r = canvas.getBoundingClientRect();
      return r.bottom > 0 && r.top < window.innerHeight;
    };
    const wake = (e: Event) => {
      // Parked off to the side, only a new pose can bring the robot back.
      if (parked.current && e.type !== WAKE) return;
      if (mobile && !onScreen()) return;
      invalidate();
    };
    const events = ["pointermove", "scroll", "resize", "focusin", "focusout", WAKE];
    events.forEach((ev) => window.addEventListener(ev, wake, { passive: true }));

    // The robot notices you: a pointer on its head (the upper half of its bust box, the part that
    // shows above the sheet) or a tap there brightens and warms its eyes and tilts its head.
    const notice = (e: PointerEvent) => {
      const anchor = anchored[mobile ? "mobile" : robotState.pose];
      const box = anchor ? document.querySelector(`[data-robot-anchor="${anchor}"]`)?.getBoundingClientRect() : null;
      const onHead =
        !!box &&
        box.width > 0 &&
        e.clientX > box.left + box.width * 0.22 &&
        e.clientX < box.right - box.width * 0.22 &&
        e.clientY > box.top &&
        e.clientY < box.top + box.height * 0.55;
      if (onHead !== greet.current) {
        greet.current = onHead;
        if (onHead) eyes.current.blinkAt = performance.now();
        invalidate();
      }
    };
    window.addEventListener("pointermove", notice, { passive: true });
    window.addEventListener("pointerdown", notice, { passive: true });
    return () => {
      events.forEach((ev) => window.removeEventListener(ev, wake));
      window.removeEventListener("pointermove", notice);
      window.removeEventListener("pointerdown", notice);
    };
  }, [canvas, invalidate, mobile]);

  useFrame((_, rawDt) => {
    if (!ready.current) return;
    const dt = Math.min(rawDt, 0.05);
    const name: PoseName = mobile ? "mobile" : robotState.pose;
    const now = performance.now();
    const first = since.current.name === "";
    if (since.current.name !== name) since.current = { name, at: now };
    const anchor = anchored[name];
    const fit = anchor ? anchorTarget(anchor, canvas, camera) : null;
    const target: Pose = fit ? { ...poses[name], ...fit } : poses[name];
    const c = cur.current;
    const ease = (from: number, to: number) => THREE.MathUtils.damp(from, to, 2.1, dt);

    // Section poses move with weight. An anchored pose arrives the same way, then holds its box
    // exactly, so the robot travels with the sheet while the page scrolls and the cut through its
    // chest stays hidden. The very first frame starts where the still already shows the robot.
    // From 1.2 s the placement blends over 0.3 s from the eased value to the box, so it never snaps.
    const hold = fit !== null ? THREE.MathUtils.smoothstep((now - since.current.at) / 1000, 1.2, 1.5) : 0;
    (Object.keys(c) as Array<keyof Pose>).forEach((k) => {
      const placement = k === "x" || k === "y" || k === "scale";
      const eased = ease(c[k], target[k]);
      c[k] = first ? target[k] : placement ? eased + (target[k] - eased) * hold : eased;
    });

    // The head turns toward the pointer as seen from where the head is on screen, within its pose's
    // limits, so a pointer on the map below the head makes it look down at the map, and outside the
    // closing section it never turns to face the viewer.
    const f = follow[name];
    headNdc.set(c.x, c.y, 0).project(camera);
    // The pointer is measured across the window, the head across the canvas: bring the head over.
    const cr = canvas.getBoundingClientRect();
    headNdc.x = ((cr.left + ((headNdc.x + 1) / 2) * cr.width) / window.innerWidth) * 2 - 1;
    headNdc.y = 1 - ((cr.top + ((1 - headNdc.y) / 2) * cr.height) / window.innerHeight) * 2;
    const tx = robotState.focus ? robotState.focus.x : robotState.pointer.x;
    const ty = robotState.focus ? robotState.focus.y : robotState.pointer.y;
    const dx = tx - headNdc.x;
    const dy = ty + headNdc.y;
    let wantYaw = clamp(dx * f.yaw, f.minYaw, f.maxYaw);
    let wantPitch = clamp(dy * f.pitch, f.minPitch, f.maxPitch);
    let wantBoost = 0;
    if (robotState.focus) {
      wantYaw = clamp(dx * 0.7, -0.55, 0.2);
      wantPitch = clamp(dy * 0.3, -0.15, 0.2);
      wantBoost = 0.6;
    }
    const l = look.current;
    l.yaw = THREE.MathUtils.damp(l.yaw, wantYaw, 3.2, dt);
    l.pitch = THREE.MathUtils.damp(l.pitch, wantPitch, 3.2, dt);
    l.boost = THREE.MathUtils.damp(l.boost, wantBoost, 4, dt);

    // The eyes lead and the head follows: the gaze moves fast, the head with weight.
    const e = eyes.current;
    if (first) e.wokeAt = now;
    else if (since.current.at === now) e.blinkAt = now;

    // Reactions. First the eyes search, sweeping side to side with the irises pulsing; then they
    // warm to gold ("found") or dim while the head shakes ("missing").
    const mood = robotState.mood;
    const tm = mood.at > 0 ? (now - mood.at) / 1000 : Infinity;
    let open = 1;
    let sweep: number | null = null;
    let wantGlow = 1;
    let wantGold = 0;
    let mYaw = 0;
    let mPitch = 0;
    let mRoll = 0;
    if (mood.name !== "idle" && tm < 2.9) {
      if (tm < 1.1) {
        sweep = Math.sin((tm / 1.1) * Math.PI * 2) * 0.9;
        wantGlow = 0.75 + 0.25 * Math.cos(tm * 17);
        open = 0.75;
        mYaw = sweep * 0.16;
      } else if (mood.name === "found") {
        wantGlow = 1.25;
        wantGold = 1;
        const k = (tm - 1.1) / 0.55;
        if (k < 1) mPitch = Math.sin(k * Math.PI) * 0.16;
      } else {
        wantGlow = 0.3;
        open = 0.6;
        const k = Math.min(1, (tm - 1.1) / 0.35) * Math.min(1, (2.9 - tm) / 0.5);
        mPitch = 0.1 * k;
        mRoll = -0.07 * k;
        if (e.shookFor !== mood.at) {
          e.shookFor = mood.at;
          robotState.shakeAt = now;
        }
      }
    }
    // A pointer resting on its head warms the eyes a little and tilts the head.
    if (greet.current && sweep === null && wantGold === 0 && wantGlow === 1) {
      wantGlow = 1.2;
      wantGold = 0.35;
    }

    // The gaze, measured the same way as the head's turn; over the map the eyes and lids look down.
    const gx = sweep ?? clamp(dx * f.eyes, -1, f.eyeMax);
    const gy = sweep !== null ? 0.25 + f.down * 0.5 : clamp(dy * f.eyes + f.down, -0.4, 0.8);
    e.x = THREE.MathUtils.damp(e.x, gx, sweep !== null ? 14 : 9, dt);
    e.y = THREE.MathUtils.damp(e.y, gy, 9, dt);
    e.size = THREE.MathUtils.damp(e.size, robotState.focus ? 1.16 : 1, 6, dt);
    e.glow = THREE.MathUtils.damp(e.glow, wantGlow, 8, dt);
    e.gold = THREE.MathUtils.damp(e.gold, wantGold, 5, dt);
    e.tilt = THREE.MathUtils.damp(e.tilt, greet.current ? 0.14 : 0, 5, dt);

    // Waking: the eyes match the still for a moment, go dark, then flicker on.
    const tw = (now - e.wokeAt) / 1000;
    const wake = tw < 0.35 ? 1 : tw < 0.5 ? 0 : tw < 0.58 ? 0.6 : tw < 0.66 ? 0.12 : tw < 0.9 ? Math.min(1, (tw - 0.66) / 0.2) : 1;
    const tb = (now - e.blinkAt) / 1000;
    if (tb >= 0 && tb < 0.18) open *= Math.abs(tb / 0.09 - 1);
    robot.eyes.set({ x: e.x, y: e.y, glow: e.glow * wake, size: e.size, open, gold: e.gold });
    // A point light's strength does not shrink with the robot, so it is scaled here: a small glow on
    // the sockets and the bridge of the nose, which turns warm and stronger when a source is found.
    robot.eyeLight.intensity = 0.02 * (1 + 1.5 * e.gold) * e.glow * wake * c.scale * c.scale;
    robot.eyeLight.distance = 0.9 * c.scale;
    const mh = moodHead.current;
    mh.yaw = THREE.MathUtils.damp(mh.yaw, mYaw, 10, dt);
    mh.pitch = THREE.MathUtils.damp(mh.pitch, mPitch, 10, dt);
    mh.roll = THREE.MathUtils.damp(mh.roll, mRoll, 10, dt);

    let shake = 0;
    const shakeT = (now - robotState.shakeAt) / 1000;
    const shaking = robotState.shakeAt > 0 && shakeT < 1.3;
    if (shaking) shake = Math.sin(shakeT * 13) * 0.2 * (1 - shakeT / 1.3);

    const g = robot.group;
    g.position.set(c.x, c.y, 0);
    g.scale.setScalar(c.scale);
    g.rotation.set(c.pitch, c.yaw, 0);
    robot.head.rotation.set(c.hpitch + l.pitch + mh.pitch, c.hyaw + l.yaw + mh.yaw + shake, e.tilt + mh.roll);
    clip.constant = -(c.y + c.cut * c.scale);
    // A warm fill from the map below, not the key: the studio cards in the environment model the face.
    if (rake.current) {
      rake.current.position.set(c.x - 5.5, c.y - 3.0, 2.8);
      rake.current.intensity = 30 * c.light * (1 + l.boost);
    }

    frames.current += 1;
    if (frames.current === 2) emitCanvasReady();

    const settled =
      (Object.keys(c) as Array<keyof Pose>).every((k) => Math.abs(c[k] - target[k]) < EPS) &&
      Math.abs(l.yaw - wantYaw) < EPS &&
      Math.abs(l.pitch - wantPitch) < EPS &&
      Math.abs(l.boost - wantBoost) < EPS &&
      Math.abs(e.x - gx) < EPS &&
      Math.abs(e.y - gy) < EPS &&
      Math.abs(e.size - (robotState.focus ? 1.16 : 1)) < EPS &&
      Math.abs(e.tilt - (greet.current ? 0.14 : 0)) < EPS &&
      Math.abs(e.glow - wantGlow) < EPS &&
      Math.abs(e.gold - wantGold) < EPS &&
      Math.abs(mh.yaw - mYaw) + Math.abs(mh.pitch - mPitch) + Math.abs(mh.roll - mRoll) < EPS &&
      tw > 0.9 &&
      !(tm < 2.9) &&
      !(tb >= 0 && tb < 0.18) &&
      !shaking;
    parked.current = settled && name === "away";
    if (!settled || frames.current < 3) invalidate();
    if (moving.current === settled) {
      moving.current = !settled;
      onMoving(!settled);
    }
  });

  return (
    <>
      {compiled && <primitive object={robot.group} />}
      <spotLight ref={rake} color={0xe9c66a} intensity={30} distance={16} angle={0.5} penumbra={0.9} decay={2} />
    </>
  );
}

export default function RobotStage({ mobile }: { mobile: boolean }) {
  const maxDpr = Math.min(2, window.devicePixelRatio || 1);
  const [dpr, setDpr] = useState(() => Math.min(1.5, maxDpr));
  // The monitor only samples while the robot is animating; idle gaps between on-demand frames
  // would otherwise read as a slow device.
  const [moving, setMoving] = useState(false);
  return (
    <Canvas
      dpr={dpr}
      frameloop="demand"
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance", toneMapping: THREE.NeutralToneMapping }}
      camera={{ fov: BASE_FOV, near: 0.1, far: 100, position: [0, 0.1, 8.6] }}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
        // Neutral keeps the teal and the brand gold on hue and rolls the brightest reflections to white.
        gl.toneMapping = THREE.NeutralToneMapping;
        gl.toneMappingExposure = 1.0;
        gl.localClippingEnabled = true;
      }}
      style={{ pointerEvents: "none" }}
    >
      {moving && <PerformanceMonitor onDecline={() => setDpr(1)} onIncline={() => setDpr(maxDpr)} />}
      <ContainCamera refAspect={mobile ? 0 : 1440 / 900} />
      <hemisphereLight args={[0x8aa3a3, 0x2a2214, 0.05]} />
      <directionalLight color={0xfff2e2} intensity={0.35} position={[-5, 4, 5]} />
      <directionalLight color={0xbfcde0} intensity={1.1} position={[4, 3, -6]} />
      <Studio />
      <Robot mobile={mobile} onMoving={setMoving} />
    </Canvas>
  );
}

// The environment, kept out of the stage's re-renders so it is baked exactly once.
const Studio = memo(function Studio() {
  return (
    <>
        {/* A small studio, baked once: the lacquer is glossy, so these cards are what model the face.
            Each card faces the robot. */}
        <Environment resolution={256} frames={1}>
          {/* Key window front-left above the face: a dim wide card round a bright core, one soft falloff. */}
          <Lightformer form="rect" color="#f2efe9" intensity={2.5} position={[-5, 3, 6]} scale={[7, 9, 1]} />
          <Lightformer form="rect" color="#f6f3ee" intensity={11} position={[-4.4, 2.6, 5.3]} scale={[2.4, 5.2, 1]} />
          {/* Overhead strip: the long highlight over the crown and the brow. */}
          <Lightformer form="rect" color="#ffffff" intensity={5} position={[0, 9, 1.5]} scale={[12, 2.4, 1]} />
          {/* A narrow cool card front-right: a streak down the far cheek and jaw. */}
          <Lightformer form="rect" color="#dbe6ec" intensity={3.5} position={[6.5, 0.5, 4.5]} scale={[1.4, 8, 1]} />
          {/* Rims behind, cool right and warm left, so the silhouette separates from the page. */}
          <Lightformer form="rect" color="#c9d6e2" intensity={7} position={[5, 2, -7]} scale={[2, 10, 1]} />
          <Lightformer form="rect" color="#e9c46a" intensity={4} position={[-6.5, 0, -5]} scale={[1.2, 9, 1]} />
          {/* The map: a broad warm glow below and in front, caught by the chin, lips and jaw. */}
          <Lightformer form="rect" color="#c9b27a" intensity={1.1} position={[-2, -7, 2.5]} scale={[14, 6, 1]} />
        </Environment>
    </>
  );
});
