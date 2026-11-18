"use client";

import { useEffect } from "react";
import { setMood, setPose, type PoseName } from "@/lib/robotBus";

// Smooth scroll and the robot's section poses, on wide screens only (Tailwind's lg, in rem). Phones
// and tablets keep the robot in its own block under the nav and scroll natively, and reduced motion
// turns all of it off, so GSAP and Lenis are only downloaded where they do something. The query is
// watched, so a tablet rotated into a wide layout gets the poses too.
const QUERY = "(min-width: 64rem) and (prefers-reduced-motion: no-preference)";
// Below Tailwind's xl a section can name a different pose (data-pose-narrow): the story map needs
// the robot's room there.
const NARROW_DESKTOP = "(max-width: 79.99rem)";

const FOCUSABLE = "a[href], button, input, select, textarea, summary, [tabindex]";

export default function Motion() {
  useEffect(() => {
    const mq = window.matchMedia(QUERY);
    const narrow = window.matchMedia(NARROW_DESKTOP);
    let teardown = () => {};
    let generation = 0;

    const setup = () => {
      const mine = ++generation;
      Promise.all([import("gsap"), import("gsap/ScrollTrigger"), import("lenis")]).then(([{ default: gsap }, { ScrollTrigger }, { default: Lenis }]) => {
        if (mine !== generation || !mq.matches) return;
        gsap.registerPlugin(ScrollTrigger);

        // Lenis makes the story read as one continuous journey along the route.
        const lenis = new Lenis({ lerp: 0.12, smoothWheel: true });
        lenis.on("scroll", ScrollTrigger.update);
        const tick = (time: number) => lenis.raf(time * 1000);
        gsap.ticker.add(tick);
        gsap.ticker.lagSmoothing(0);

        const sections = Array.from(document.querySelectorAll<HTMLElement>("[data-pose]"));
        const poseOf = (el: HTMLElement) => ((narrow.matches && el.dataset.poseNarrow) || el.dataset.pose) as PoseName;
        const triggers = sections.map((el, i) =>
          ScrollTrigger.create({
            trigger: el,
            start: "top 55%",
            end: "bottom 45%",
            onToggle: (self) => {
              if (!self.isActive) return;
              const name = poseOf(el);
              setPose(name);
              if (name === "palsu") setMood("missing");
            },
            // A jump straight to the end of the page (End key, a footer link) skips the last
            // section's toggle; past it, the robot still belongs to that section.
            onLeave: i === sections.length - 1 ? () => setPose(poseOf(el)) : undefined,
          }),
        );
        // The story's pin may already exist; sorting keeps every position measured after it.
        ScrollTrigger.sort();
        ScrollTrigger.refresh();

        // In-page links scroll through Lenis, so the browser's own jump (which moves focus) is
        // cancelled; focus moves to the target here instead, for keyboard and screen reader users.
        const onClick = (e: MouseEvent) => {
          const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a[href^="#"]');
          if (!a) return;
          const id = a.getAttribute("href");
          if (!id || id === "#") return;
          const target = document.querySelector<HTMLElement>(id);
          if (!target) return;
          e.preventDefault();
          lenis.scrollTo(target, { offset: -8 });
          history.replaceState(null, "", id);
          if (!target.matches(FOCUSABLE)) target.setAttribute("tabindex", "-1");
          target.focus({ preventScroll: true });
        };
        document.addEventListener("click", onClick);

        // Opening or closing an FAQ answer changes the page height; refresh so the closing
        // section's trigger fires when the section actually arrives.
        const refresh = () => ScrollTrigger.refresh();
        document.addEventListener("toggle", refresh, true);

        teardown = () => {
          document.removeEventListener("toggle", refresh, true);
          document.removeEventListener("click", onClick);
          triggers.forEach((t) => t.kill());
          gsap.ticker.remove(tick);
          lenis.destroy();
          setPose("hero");
        };
      });
    };

    const change = () => {
      generation++;
      teardown();
      teardown = () => {};
      if (mq.matches) setup();
    };

    if (mq.matches) setup();
    mq.addEventListener("change", change);
    return () => {
      mq.removeEventListener("change", change);
      generation++;
      teardown();
    };
  }, []);

  return null;
}
