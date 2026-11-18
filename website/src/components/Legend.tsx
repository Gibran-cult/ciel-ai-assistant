import type { ReactNode } from "react";
import { legend } from "@/content/site";

// The screen as an annotated chart: a sample of the app's own layout (chat on the left, the source
// panel on the right) carries six numbered marks, and the key beside it explains each number, the
// way a map's legend explains its symbols.

const KEY = Object.fromEntries(legend.items.map((item, i) => [item.id, i + 1])) as Record<string, number>;

// A numbered mark: the same drafted ring in the key and on the screen. On the screen it sits beside
// the part it names, on the page's ground, so it reads as an annotation and not as a control of the
// app, and it never covers the app's own text.
function Num({ n, className = "" }: { n: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`tabular inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-bg text-[0.875rem] font-bold leading-none text-ink ring-[1.5px] ring-ink ${className}`}
    >
      {n}
    </span>
  );
}

// Sets the mark in line beside the part, after it or (where the part sits against the right edge
// of its column) before it. In the flow, so it never covers text or runs off a narrow screen.
function Marked({ id, children, before = false, className = "" }: { id: string; children: ReactNode; before?: boolean; className?: string }) {
  const mark = <Num n={KEY[id]} />;
  return (
    <div className={`flex max-w-full items-center gap-2.5 ${className}`}>
      {before && mark}
      <div className="min-w-0">{children}</div>
      {!before && mark}
    </div>
  );
}

// Each "[n]" in the answer becomes a small raised blue number that points at a source row below.
function withRefs(text: string): ReactNode[] {
  return text.split(/\s*(\[\d+\])/).map((part, i) =>
    /^\[\d+\]$/.test(part) ? (
      <sup key={i} className="ml-0.5 font-bold text-link">
        {part}
      </sup>
    ) : (
      part
    ),
  );
}

export default function Legend() {
  const s = legend.sample;

  return (
    <section
      id="legenda"
      aria-labelledby="legenda-judul"
      data-pose="away"
      className="relative z-[1] py-[clamp(88px,11vw,184px)]"
    >
      <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)]">
        <h2 id="legenda-judul" className="display text-[clamp(2.25rem,4.4vw,4rem)]">
          {legend.heading}
        </h2>
        <p className="measure mt-6 text-muted">{legend.lede}</p>

        <div className="mt-[clamp(56px,7vw,104px)] grid gap-y-14 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)] lg:gap-x-[clamp(48px,6vw,112px)]">
          <dl aria-label="Keterangan contoh layar" className="flex flex-col gap-7 lg:mt-12">
            {legend.items.map((item, i) => (
              <div key={item.id}>
                <dt className="flex items-center gap-4 font-display text-[1.375rem] font-bold leading-[1.25] text-ink">
                  <Num n={i + 1} />
                  {item.term}
                </dt>
                {/* Indented by the mark's width and gap, so the text lines up under the term. */}
                <dd className="mt-1 pl-11 text-muted">{item.text}</dd>
              </div>
            ))}
          </dl>

          {/* data-ui marks the app's own interface. Only inside it do 1px separators and the yellow
              Dugaan label appear, because that is how the app draws them. */}
          {/* From 1024px the screen stretches to the key's height; the chat's composer takes the room
              at the bottom, where the app has it. */}
          <figure className="flex w-full flex-col">
            <figcaption className="mb-5 font-display text-base italic text-muted">{s.label}</figcaption>
            <div data-ui className="flex flex-1 flex-col rounded-[18px] bg-surface text-base text-ink">
              <p className="flex items-center gap-2.5 border-b border-ink/10 py-3 pl-6 pr-5 text-[15px] font-medium">{/* taste-skill-ignore: the app's own header separator, inside data-ui */}
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--blue-text)" strokeWidth="1.5" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
                  <path d="M3.5 7a1.5 1.5 0 0 1 1.5-1.5h4l2 2h8a1.5 1.5 0 0 1 1.5 1.5v8.5a1.5 1.5 0 0 1-1.5 1.5H5a1.5 1.5 0 0 1-1.5-1.5Z" />
                </svg>
                {s.project}
                <Num n={KEY.proyek} />
              </p>

              <div className="grid flex-1 md:grid-cols-[minmax(0,1fr)_minmax(0,15rem)]">
                <div className="flex flex-col px-6 pb-6 pt-6">
                  {/* The question was written from a template; the app sends it as plain text, so
                      the mark points at the question itself. */}
                  <div className="flex justify-end">
                    <Marked id="template" before className="max-w-[90%]">
                      <p className="rounded-[16px] bg-surface-2 px-4 py-2.5">{s.question}</p>
                    </Marked>
                  </div>

                  <p className="mt-6">{withRefs(s.answer)}</p>
                  <Marked id="dugaan" className="mt-3">
                    {/* The app's own label for a point with no source yet ([Dugaan] in chat_sources.py). */}
                    <p className="flex gap-3 text-[15px]">
                      <strong className="shrink-0 font-bold text-gold">Dugaan</strong>
                      <span className="text-muted">{s.guess}</span>
                    </p>
                  </Marked>
                  <Marked id="sumber" className="mt-4">
                    <ul className="-mx-2">
                      {s.sources.map((src) => (
                        <li key={src.n}>
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group flex min-h-11 items-start gap-3 rounded-md px-2 py-[11px] text-[15px] hover:bg-surface-2"
                          >
                            <span className="tabular min-w-4 font-bold text-link group-hover:text-link-hi">{src.n}</span>
                            <span className="min-w-0">
                              <span className="text-ink">{src.domain}</span>{" "}
                              <span aria-hidden="true" className="text-muted">
                                ·
                              </span>{" "}
                              <span className="text-muted">{src.title}</span>
                              <span className="sr-only"> (buka di tab baru)</span>
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </Marked>
                  <div aria-hidden="true" className="flex-1" />
                  {/* The composer, with the placeholder a project chat shows (composer() in app.py). */}
                  <p aria-hidden="true" className="mt-8 rounded-full bg-surface-2 px-5 py-3 text-[15px] text-muted">
                    {s.composer}
                  </p>
                </div>

                {/* The right-hand panel, as render_rail() in app.py lays it out. */}
                <div className="flex flex-col gap-7 border-t border-ink/10 px-6 py-6 md:border-l md:border-t-0">{/* taste-skill-ignore: the app's own panel separator, inside data-ui */}
                  <div>
                    <p className="flex items-center gap-2 text-[15px] font-bold">
                      {s.railSources}
                      <span className="tabular rounded-full bg-surface-2 px-2 text-[12px] font-normal leading-5 text-muted">{s.sources.length}</span>
                      <Num n={KEY.panel} className="ml-0.5" />
                    </p>
                    <ol className="mt-3 flex flex-col gap-3 text-[14px]">
                      {s.sources.map((src) => (
                        <li key={src.n} className="flex gap-2.5">
                          <span className="tabular font-bold text-link">{src.n}</span>
                          <span className="min-w-0">
                            <span className="block font-medium text-ink">{src.title}</span>
                            <span className="block italic text-muted">{src.domain}</span>
                          </span>
                        </li>
                      ))}
                    </ol>
                  </div>
                  <div>
                    <p className="flex items-center gap-2 text-[15px] font-bold">
                      {s.railGaps}
                      <span className="tabular rounded-full bg-surface-2 px-2 text-[12px] font-normal leading-5 text-muted">1</span>
                    </p>
                    {/* The app's own marker for a point still without a source (.ciel-gap in app.py). */}
                    <p className="mt-3 flex items-start gap-2.5 rounded-lg bg-surface-2 px-3 py-2 text-[14px] text-ink">
                      <span aria-hidden="true" className="mt-[3px] size-3.5 shrink-0 rounded bg-gold" />
                      {s.guess}
                    </p>
                  </div>
                  <div>
                    <p className="flex items-center gap-2 text-[15px] font-bold">
                      {s.railMemory}
                      <span className="tabular rounded-full bg-surface-2 px-2 text-[12px] font-normal leading-5 text-muted">1</span>
                      <Num n={KEY.ingatan} className="ml-0.5" />
                    </p>
                    <p className="mt-3">
                      <span className="inline-block rounded-full bg-surface-2 px-3 py-1 text-[14px]">{s.memory}</span>
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </figure>
        </div>
      </div>
    </section>
  );
}
