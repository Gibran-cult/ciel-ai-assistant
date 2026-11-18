"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import MapArt from "@/components/MapArt";
import RobotBust from "@/components/RobotBust";
import { cases, hero, type Case } from "@/content/site";
import { casePins, fakeAside, fakeTrail, islands, start, VIEW, type Pt } from "@/lib/mapGeometry";
import { setMood } from "@/lib/robotBus";

type Phase = "idle" | "reset" | "drawing";

// Where the light rests before the visitor moves: over the middle of the route.
const LIGHT_HOME: Pt = [470, 190];
// How far the light reaches, in viewBox units. Pins inside it brighten.
const LIGHT_REACH = 260;

// The hero's live thing. The lede and the case chips sit in the left column, the chart sheet in the
// right. A chip redraws that case's real result from the 20 Oktober test. The trail to the fake
// journal stays on the sheet in every case, struck out in open water; beside another case it starts
// at its own ring, named for the test it came from, because in the test it was a separate question.
// The same pointer that turns the robot's head moves a pool of light across the sheet, and the route
// and pins brighten under it (held still under reduced motion).
export default function ResearchMap({ intro }: { intro: ReactNode }) {
  const [active, setActive] = useState<Case["id"]>("vaswani");
  const [phase, setPhase] = useState<Phase>("idle");
  const rootRef = useRef<HTMLDivElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const relight = useRef<() => void>(() => {});
  const current = cases.find((c) => c.id === active) ?? cases[0];

  const select = (id: Case["id"]) => {
    if (id === active) return;
    setActive(id);
    setPhase("reset");
    requestAnimationFrame(() => requestAnimationFrame(() => setPhase("drawing")));
    setMood(id === "palsu" ? "missing" : "found");
  };

  const shown = phase !== "reset";
  const pins = current.found ? casePins[current.id as "vaswani" | "koto"] : [];
  const route: Pt[] | undefined = current.found ? [start, ...pins] : undefined;

  useEffect(() => {
    const sheet = sheetRef.current;
    const area = rootRef.current?.closest("section") ?? rootRef.current;
    if (!sheet || !area) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pos = { x: LIGHT_HOME[0], y: LIGHT_HOME[1] };
    const target = { ...pos };
    let raf = 0;
    let last = 0;

    const paint = () => {
      sheet.querySelectorAll<SVGRadialGradientElement>("[data-light]").forEach((g) => {
        g.setAttribute("cx", pos.x.toFixed(1));
        g.setAttribute("cy", pos.y.toFixed(1));
      });
      sheet.querySelectorAll<SVGGElement>("[data-pin]").forEach((g) => {
        const [px, py] = (g.dataset.pin ?? "").split(",").map(Number);
        const lit = Math.max(0, Math.min(1, 1 - Math.hypot(px - pos.x, py - pos.y) / LIGHT_REACH));
        g.style.setProperty("--lit", lit.toFixed(2));
      });
    };
    relight.current = paint;

    // The light eases toward the pointer and stops drawing once it has arrived.
    const step = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const k = 1 - Math.exp(-7 * dt);
      pos.x += (target.x - pos.x) * k;
      pos.y += (target.y - pos.y) * k;
      paint();
      raf = Math.hypot(target.x - pos.x, target.y - pos.y) > 0.5 ? requestAnimationFrame(step) : 0;
    };

    const move = (e: PointerEvent) => {
      // Reduced motion keeps the light where it rests: nothing on the sheet follows the pointer.
      if (reduce.matches) return;
      const r = sheet.getBoundingClientRect();
      if (!r.width) return;
      // Anywhere in the hero counts; past the sheet the light parks just beyond its edge.
      target.x = Math.max(-80, Math.min(VIEW.w + 80, ((e.clientX - r.left) / r.width) * VIEW.w));
      target.y = Math.max(-80, Math.min(VIEW.h + 80, ((e.clientY - r.top) / r.height) * VIEW.h));
      if (!raf) {
        last = performance.now();
        raf = requestAnimationFrame(step);
      }
    };
    const settle = () => {
      if (!reduce.matches) return;
      cancelAnimationFrame(raf);
      raf = 0;
      pos.x = target.x = LIGHT_HOME[0];
      pos.y = target.y = LIGHT_HOME[1];
      paint();
    };

    paint();
    area.addEventListener("pointermove", move, { passive: true });
    reduce.addEventListener("change", settle);
    return () => {
      area.removeEventListener("pointermove", move);
      reduce.removeEventListener("change", settle);
      cancelAnimationFrame(raf);
    };
  }, []);

  // New pins render without a light value; give them the current one.
  useEffect(() => relight.current(), [active]);

  return (
    <div ref={rootRef} className="grid grid-cols-1 gap-y-10 lg:grid-cols-[minmax(17rem,23rem)_minmax(0,1fr)] lg:gap-x-[clamp(32px,3.5vw,56px)]">
      <div>
        {intro}
        <div className="mt-10 lg:mt-14">
          <p id="peta-pilih" className="font-display text-[1.1875rem] italic text-muted">
            {hero.mapPrompt}
          </p>
          <div role="group" aria-labelledby="peta-pilih" className="mt-3 flex flex-wrap gap-2 lg:flex-col lg:items-start">
            {cases.map((c) => {
              const on = c.id === active;
              return (
                <button
                  key={c.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => select(c.id)}
                  className={`inline-flex min-h-[44px] items-center gap-2 rounded-full px-4 text-[1rem] font-medium transition-[background-color,transform] duration-150 active:translate-y-px ${
                    on ? "bg-blue text-ink" : "bg-surface text-ink hover:bg-surface-2"
                  }`}
                >
                  {on && (
                    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                      <circle cx="5" cy="5" r="4" fill="var(--text)" />
                    </svg>
                  )}
                  {c.chip}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="min-w-0">
        {/* On wide screens the sheet keeps to the right edge and, on short screens, gives up width so
            the whole route stays in the first screen. It never drops below 30rem, so zooming in or a
            larger default font never makes the map smaller. The answer below keeps the full column. */}
        <div ref={sheetRef} className="relative touch-pan-y touch-pinch-zoom lg:ml-auto lg:max-w-[max(30rem,calc((100svh_-_24rem)_*_1.8))]">
          {/* From 1024px the robot stands behind the sheet's right end: the sheet's top edge cuts
              the bust frame at 63.4% of its height, just under the chin (27.57% = 0.634 of a box
              40% wide at the frame's 780:848 ratio, as a margin of the sheet's width). */}
          <RobotBust anchor="hero" className="absolute right-[3%] top-0 -z-10 mt-[-27.57%] hidden aspect-[780/848] w-[40%] lg:block" />
          <MapArt
            id="hero-map"
            className="block h-auto w-full"
            route={route}
            draw={shown ? 1 : 0}
            animate={phase === "drawing"}
            pins={pins.map((at, i) => ({ at, n: i + 1, delayMs: 600 + i * 160 }))}
            pinsVisible={shown}
            falseTrail={
              current.found
                ? { route: fakeAside, origin: "Uji jurnal palsu", draw: 1, label: "Hendrawan & Sulistyo (2019)", note: "tidak ada", visible: true }
                : { route: fakeTrail, draw: shown ? 1 : 0, label: "Hendrawan & Sulistyo (2019)", note: "tidak ada", visible: shown }
            }
            // The fake journal's search found nothing, so every source island steps back.
            dimIslands={current.found ? [] : islands.map((isl) => isl.id)}
            light={LIGHT_HOME}
          />
        </div>

        <div aria-live="polite" className="mt-8 grid gap-x-10 gap-y-4 text-[1.0625rem] md:grid-cols-2">
          <div className="flex flex-col gap-4">
            <div>
              <p className="text-[0.9375rem] text-muted">Kamu</p>
              <p className="mt-1 text-ink">{current.question}</p>
            </div>
            <div>
              <p className="text-[0.9375rem] text-muted">
                Ciel <span className="tabular">· {current.sources.length} sumber</span>
              </p>
              {current.found ? (
                <p className="mt-1 text-ink">{current.answer}</p>
              ) : (
                <blockquote className="mt-1 font-display text-[1.375rem] leading-snug text-ink">{current.answer}</blockquote>
              )}
              {current.note && <p className="mt-2 font-display italic text-muted">{current.note}</p>}
            </div>
          </div>
          {current.sources.length > 0 && (
            <ol className="flex flex-col md:pt-7">
              {current.sources.map((s) => (
                <li key={s.n} className="flex items-center gap-2">
                  <span className="tabular font-bold text-ink">[{s.n}]</span>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center break-words">
                    {s.domain} · {s.title}
                  </a>
                </li>
              ))}
            </ol>
          )}
        </div>
        <p className="mt-5 text-[0.9375rem] text-muted">{hero.mapCaption}</p>
      </div>
    </div>
  );
}
