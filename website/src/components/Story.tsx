"use client";

import { useEffect, useRef, useState } from "react";
import MapArt from "@/components/MapArt";
import { fakeJournal, story } from "@/content/site";
import { fakeAside, start, storyPins } from "@/lib/mapGeometry";
import { setMood } from "@/lib/robotBus";

const STEPS = story.steps.length;
// Tailwind's lg, in rem like the layout, with motion allowed.
const QUERY = "(min-width: 64rem) and (prefers-reduced-motion: no-preference)";

// "Dari pertanyaan ke sumber". On wide screens the map is pinned beside the steps while they scroll
// past, and each step draws its part of the route. Every step and its sample stay in the page the
// whole time, so keyboard and screen reader users reach all of them, and the frame never has to fit
// in one screen. Without the pin (phones, reduced motion, no JS) the map shows the finished route.
export default function Story() {
  const listRef = useRef<HTMLOListElement>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const [live, setLive] = useState(false);
  const [step, setStep] = useState(STEPS - 1);
  const [local, setLocal] = useState(1);

  useEffect(() => {
    // GSAP is only downloaded where the pin runs, and the query is watched so a tablet rotated
    // into a wide layout gets it too.
    const mq = window.matchMedia(QUERY);
    let revert = () => {};
    let loading = false;
    let cancelled = false;
    const load = () => {
      if (loading || !mq.matches) return;
      loading = true;
      Promise.all([import("gsap"), import("gsap/ScrollTrigger")]).then(([{ default: gsap }, { ScrollTrigger }]) => {
        if (cancelled) return;
        gsap.registerPlugin(ScrollTrigger);
        const mm = gsap.matchMedia();
        revert = () => mm.revert();
        mm.add(QUERY, () => {
          setLive(true);
          setStep(0);
          setLocal(0);
          const triggers: Array<ReturnType<typeof ScrollTrigger.create>> = [];
          // Measure once React has drawn the scroll layout (taller steps).
          let raf = requestAnimationFrame(() => {
            raf = requestAnimationFrame(() => {
              const list = listRef.current;
              const map = mapRef.current;
              if (!list || !map) return;
              // The map holds still in the middle of the screen while the steps scroll past it.
              const top = () => Math.max(24, (window.innerHeight - map.offsetHeight) / 2);
              triggers.push(
                ScrollTrigger.create({
                  trigger: map,
                  start: () => `top ${top()}px`,
                  endTrigger: list,
                  end: () => `bottom ${top() + map.offsetHeight}px`,
                  pin: map,
                  pinSpacing: false,
                  refreshPriority: 1,
                }),
              );
              Array.from(list.children).forEach((li, i) => {
                triggers.push(
                  ScrollTrigger.create({
                    trigger: li,
                    start: "top 60%",
                    end: "bottom 60%",
                    onToggle: (self) => {
                      if (!self.isActive) return;
                      setStep(i);
                      // The robot in the corner acts the step out: it searches and finds on the
                      // search step, and comes back empty on the not-found step.
                      if (i === 1) setMood("found");
                      if (i === STEPS - 1) setMood("missing");
                    },
                    onUpdate: (self) => {
                      // Rounded so the map re-renders in small steps, not on every scroll event.
                      if (self.isActive) setLocal(Math.round(self.progress * 50) / 50);
                    },
                  }),
                );
              });
              ScrollTrigger.sort();
              ScrollTrigger.refresh();
            });
          });
          return () => {
            cancelAnimationFrame(raf);
            triggers.forEach((t) => t.kill());
            setLive(false);
            setStep(STEPS - 1);
            setLocal(1);
          };
        });
      });
    };
    load();
    mq.addEventListener("change", load);
    return () => {
      cancelled = true;
      mq.removeEventListener("change", load);
      revert();
    };
  }, []);

  // Map state for the current step. Without the scroll story it shows the finished map.
  const routeDraw = !live ? 1 : step === 0 ? 0 : step === 1 ? local : 1;
  const pinsShown = !live || step >= 2;
  const trailDraw = !live ? 1 : step === 3 ? Math.min(1, local * 1.6) : 0;
  const trailShown = !live || (step === 3 && local > 0.55);

  return (
    <section id="cara-kerja" aria-labelledby="cara-kerja-judul" data-pose="story" data-pose-narrow="away" className="relative z-[1]">
      {/* From 1280px the robot stands in the lower right corner of the screen while the steps scroll:
          this box, fixed to the viewport, is where it fits itself (RobotStage). Its lower tenth hangs
          below the screen, so the cut through the robot's chest is never in view. */}
      <div
        data-robot-anchor="story"
        aria-hidden="true"
        className="pointer-events-none invisible fixed bottom-0 right-[var(--gutter)] hidden aspect-[780/848] h-[min(44svh,400px)] translate-y-[10%] xl:block"
      />
      <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)] py-[clamp(72px,9vw,120px)]">
        {/* From 1280px the right 21% stays clear for the robot, which stands small at the edge here;
            below that it steps away (data-pose-narrow) and the map takes the room. */}
        <h2 id="cara-kerja-judul" className="display text-[clamp(2.25rem,4.4vw,4rem)]">
          {story.heading}
        </h2>
        <div className="mt-8 grid w-full gap-10 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-[clamp(32px,4vw,64px)] xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] xl:pr-[21%]">
          <div>
            <ol ref={listRef} className="flex flex-col gap-6 lg:gap-0" aria-label="Langkah kerja Ciel">
              {story.steps.map((s, i) => {
                const current = live && i === step;
                return (
                  <li key={s.id} aria-current={current ? "step" : undefined} className={live ? "lg:flex lg:min-h-[44svh] lg:flex-col lg:justify-center lg:py-6" : undefined}>
                    {/* Only the step's own sentence dims; its sample keeps full contrast. */}
                    <p className="text-ink transition-opacity duration-500" style={{ opacity: !live || current ? 1 : 0.55 }}>
                      {s.text}
                    </p>
                    <StepSample index={i} />
                  </li>
                );
              })}
            </ol>
            <p className="mt-8 text-[0.9375rem] text-muted">{story.footnote}</p>
          </div>

          <div ref={mapRef} className="self-start">
            {/* Shown smaller than the hero map, so its names are set larger to stay readable. */}
            <MapArt
              id="story-map"
              className="block h-auto w-full"
              labelSize={28}
              route={[start, ...storyPins]}
              draw={routeDraw}
              pins={storyPins.map((at, i) => ({ at, n: i + 1 }))}
              pinsVisible={pinsShown}
              animate={false}
              falseTrail={{
                route: fakeAside,
                origin: "Uji jurnal palsu",
                draw: trailDraw,
                label: "Hendrawan & Sulistyo (2019)",
                note: "tidak ada",
                visible: trailShown,
              }}
              dimIslands={["arxiv", "neurips", "acl", "doi"]}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function StepSample({ index }: { index: number }) {
  const s = story.steps[index];
  if (index === 0) {
    return <p className="mt-3 inline-block rounded-[18px] bg-blue px-4 py-3 text-ink">{s.sample}</p>;
  }
  if (index === 1) {
    return (
      <p className="mt-3 flex items-center gap-3 font-display italic text-muted">
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10" cy="10" r="6.5" fill="none" stroke="var(--blue-text)" strokeWidth="1.5" />
          <path d="M15 15l5 5" stroke="var(--blue-text)" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        {s.sample}
      </p>
    );
  }
  if (index === 2) {
    return (
      <div className="mt-3 rounded-[18px] bg-surface p-4">
        <p className="text-ink">{s.sample}</p>
        <ol className="mt-2 flex flex-col text-[1rem]">
          {story.sampleSources.map((src) => (
            <li key={src.n} className="flex items-center gap-2">
              <span className="tabular font-bold">[{src.n}]</span>
              <a href={src.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center">
                {src.domain} · {src.title}
              </a>
            </li>
          ))}
        </ol>
      </div>
    );
  }
  return (
    <div className="mt-3">
      <blockquote className="font-display text-[1.25rem] leading-snug text-ink">{fakeJournal.reply}</blockquote>
      <p className="mt-2 text-muted">
        Tempat lain buat nyari: <span className="text-ink">{story.elsewhere.join(", ")}</span>.
      </p>
    </div>
  );
}
