"use client";

import type { ReactNode } from "react";
import { robotState, wakeRobot } from "@/lib/robotBus";

// The primary action. Hovering it or reaching it with the keyboard turns the robot toward it,
// so mouse and keyboard users get the same reaction.
export default function CtaLink({ href, children, className = "btn-primary" }: { href: string; children: ReactNode; className?: string }) {
  const lookAt = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    robotState.focus = {
      x: ((r.left + r.width / 2) / window.innerWidth) * 2 - 1,
      y: ((r.top + r.height / 2) / window.innerHeight) * 2 - 1,
    };
    wakeRobot();
  };
  const release = () => {
    robotState.focus = null;
    wakeRobot();
  };
  return (
    <a
      href={href}
      className={className}
      onPointerEnter={(e) => lookAt(e.currentTarget)}
      onPointerLeave={release}
      onFocus={(e) => lookAt(e.currentTarget)}
      onBlur={release}
    >
      {children}
    </a>
  );
}
