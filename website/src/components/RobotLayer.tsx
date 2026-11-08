"use client";

import dynamic from "next/dynamic";
import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { onCanvasReady, resetCanvasReady, robotState } from "@/lib/robotBus";

// three.js only loads after the page is interactive; the still bust is the LCP meanwhile.
const RobotStage = dynamic(() => import("./RobotStage"), { ssr: false });

type Mode = "off" | "desktop" | "mobile";

// Tailwind's lg breakpoint, in rem like Tailwind writes it, so the robot's mode always agrees with
// the layout (which bust box is shown) at any zoom or default font size.
const WIDE = "(min-width: 64rem)";

// three.js (r163 and later) renders with WebGL2 only. The answer is cached and the probe context
// released, so a resize or rotation never piles up contexts.
let webgl2: boolean | null = null;
function hasWebGL2() {
  if (webgl2 === null) {
    try {
      const gl = document.createElement("canvas").getContext("webgl2");
      webgl2 = Boolean(gl);
      gl?.getExtension("WEBGL_lose_context")?.loseContext();
    } catch {
      webgl2 = false;
    }
  }
  return webgl2;
}

// If the renderer fails anyway (a lost or refused context, a shader error), the page keeps its
// still busts instead of Next's error screen.
class Fallback extends Component<{ onError: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export default function RobotLayer() {
  const [mode, setMode] = useState<Mode>("off");
  const [live, setLive] = useState(false);
  const broken = useRef(false);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const wide = window.matchMedia(WIDE);
    const pick = () => {
      // Reduced motion, no WebGL2 or a failed renderer all keep the still busts, which already show the robot.
      if (broken.current || reduce.matches || !hasWebGL2()) return setMode("off");
      setMode(wide.matches ? "desktop" : "mobile");
    };
    // three.js is the heaviest part of the page. The busts already show the robot, so the 3D scene
    // loads on the visitor's first move (pointer, touch, scroll or key), then waits for an idle moment.
    // On phones the robot lives only in the hero's block, so it also waits until that block is on screen.
    const idle = window.requestIdleCallback ?? ((cb: () => void) => window.setTimeout(cb, 200));
    const wakeEvents = ["pointermove", "pointerdown", "wheel", "scroll", "keydown", "touchstart"] as const;
    let started = false;
    let observer: IntersectionObserver | undefined;
    const begin = () => {
      const box = !wide.matches ? document.querySelector('[data-robot-anchor="mobile"]') : null;
      if (!box || !("IntersectionObserver" in window)) return idle(pick);
      observer = new IntersectionObserver((entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        observer?.disconnect();
        idle(pick);
      });
      observer.observe(box);
    };
    const start = () => {
      if (started) return;
      started = true;
      wakeEvents.forEach((ev) => window.removeEventListener(ev, start));
      begin();
    };
    const change = () => {
      if (started) pick();
    };
    wakeEvents.forEach((ev) => window.addEventListener(ev, start, { passive: true }));
    reduce.addEventListener("change", change);
    wide.addEventListener("change", change);
    return () => {
      wakeEvents.forEach((ev) => window.removeEventListener(ev, start));
      observer?.disconnect();
      reduce.removeEventListener("change", change);
      wide.removeEventListener("change", change);
    };
  }, []);

  useEffect(() => {
    if (mode === "off") return;
    const move = (e: PointerEvent) => {
      robotState.pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
      robotState.pointer.y = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", move, { passive: true });
    const off = onCanvasReady(() => {
      setLive(true);
      document.documentElement.dataset.robot = "live";
    });
    return () => {
      window.removeEventListener("pointermove", move);
      off();
      // Bring the still busts back until a new canvas (if any) has drawn its first frame.
      setLive(false);
      delete document.documentElement.dataset.robot;
      resetCanvasReady();
    };
  }, [mode]);

  const fail = useCallback(() => {
    broken.current = true;
    setMode("off");
  }, []);

  if (mode === "off") return null;
  return (
    <div className="robot-layer" data-mode={mode} data-live={live ? "true" : "false"} aria-hidden="true">
      <Fallback onError={fail}>
        <RobotStage key={mode} mobile={mode === "mobile"} />
      </Fallback>
    </div>
  );
}
