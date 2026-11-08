import { cases, footer, type FooterLink } from "@/content/site";

// The footer is the bottom margin of the night chart. Its top edge is the map's graduated neatline,
// so the closing robot stands behind it the way the hero robot stands behind the map sheet. The
// route makes its last leg here: in from the page edge to the Kepingan ring of the nameplate set
// under the robot. Beside it, the margin carries what a chart prints there: its key (the links)
// and a note on where the first map's data comes from, drawn with the map's own symbols.

const RING = "M24.89 10.6A11.8 11.8 0 1 0 24.89 21.4H20.57A8.2 8.2 0 1 1 20.57 10.6Z";
const PIECE = "M28.39 10.6A11.8 11.8 0 0 1 28.39 21.4H24.07A8.2 8.2 0 0 0 24.07 10.6Z";
// The closing section's route, mirrored, ending a few pixels short of the ring. The svg is drawn
// 1:1 and anchored right, so narrow screens show only its last bend.
const ROUTE = "M1100 18 H1514 C1634 18 1684 50 1804 46 S1944 24 1988 32";

// The map's graduated border, as a single strip: 27 equal steps between two rules, filled at both
// ends, whatever the width. No numbers: the band carries no scale it could not back up.
function Neatline() {
  return (
    <svg className="block h-[7px] w-full" aria-hidden="true" focusable="false" shapeRendering="crispEdges">
      <defs>
        <pattern id="footer-scale" patternUnits="objectBoundingBox" patternContentUnits="objectBoundingBox" width={2 / 27} height="1">
          <rect y="0.143" width={1 / 27} height="0.714" fill="var(--muted)" fillOpacity="0.32" />
        </pattern>
      </defs>
      <rect width="100%" height="7" fill="url(#footer-scale)" />
      <line x1="0" y1="0.5" x2="100%" y2="0.5" stroke="var(--muted)" strokeOpacity="0.55" />
      <line x1="0" y1="6.5" x2="100%" y2="6.5" stroke="var(--muted)" strokeOpacity="0.4" />
      <line x1="0.5" y1="0" x2="0.5" y2="7" stroke="var(--muted)" strokeOpacity="0.55" />
      <svg x="100%" overflow="visible">
        <line x1="-0.5" y1="0" x2="-0.5" y2="7" stroke="var(--muted)" strokeOpacity="0.55" />
      </svg>
    </svg>
  );
}

// The map key's symbols: a found source is the pin (ring and dot), a missing one the cross.
function KeyMark({ found }: { found: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true" focusable="false" className="shrink-0">
      {found ? (
        <>
          <circle cx="9" cy="9" r="7.4" stroke="var(--yellow)" strokeOpacity="0.4" strokeWidth="1.2" />
          <circle cx="9" cy="9" r="3.6" fill="var(--yellow)" />
        </>
      ) : (
        <path d="M4.6 4.6l8.8 8.8m0-8.8l-8.8 8.8" stroke="var(--muted)" strokeWidth="1.8" strokeLinecap="round" />
      )}
    </svg>
  );
}

// Every footer link: blue ink, a 44px row, and a hairline that draws under the label on hover or
// keyboard focus (the route's "ink draws along the path", at its smallest).
function KeyLink({ link }: { link: FooterLink }) {
  const label = link.handle ? (
    <>
      <span className="text-muted">{link.label}</span>&nbsp;<span translate="no">{link.handle}</span>
    </>
  ) : (
    link.label
  );
  return (
    <a
      href={link.href}
      className={`ink-link link-quiet ${link.strong ? "font-bold" : ""}`}
      {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      {...(link.href.startsWith("mailto:") ? { translate: "no" as const } : {})}
    >
      <span className="[overflow-wrap:anywhere]">{label}</span>
      {link.external && <span className="sr-only"> (tab baru)</span>}
    </a>
  );
}

export default function Footer() {
  return (
    <footer className="footer-sheet relative z-[1] bg-surface">
      <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)] pb-[clamp(24px,3vw,40px)]">
        <Neatline />

        <div className="footer-grid mt-[clamp(40px,4.5vw,72px)] grid grid-cols-[minmax(0,1fr)_auto] md:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_clamp(24rem,36vw,32rem)]">
          {/* The route's last leg, from the page edge to the ring. */}
          <svg
            viewBox="0 0 2000 64"
            preserveAspectRatio="xMaxYMid slice"
            className="col-start-1 row-start-1 -ml-[var(--gutter)] block h-16 w-[calc(100%+var(--gutter))] self-center"
            aria-hidden="true"
            focusable="false"
          >
            <defs>
              <mask id="footer-route-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="2000" height="64">
                <path className="footer-route-draw" d={ROUTE} pathLength={1} fill="none" stroke="#fff" strokeWidth="10" strokeDasharray="1" strokeDashoffset="0" />
              </mask>
            </defs>
            <path
              className="footer-route"
              d={ROUTE}
              fill="none"
              stroke="var(--yellow)"
              strokeWidth="2.4"
              strokeDasharray="6 7"
              strokeLinecap="round"
              mask="url(#footer-route-mask)"
            />
          </svg>

          {/* The nameplate: the Kepingan ring is where the route arrives. */}
          <p
            translate="no"
            className="col-start-2 row-start-1 flex items-center gap-[0.12em] self-center whitespace-nowrap font-mark text-[clamp(4rem,12vw,10rem)] font-medium leading-[0.9] tracking-[-0.03em] text-ink"
          >
            <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false" className="size-[0.64em] shrink-0">
              <path d={RING} fill="var(--blue-text)" />
              <path d={PIECE} fill="var(--yellow)" />
            </svg>
            Ciel
          </p>

          <div className="col-span-2 row-start-2 mt-4 md:col-span-1 md:col-start-2 md:mt-5">
            <p className="ml-auto max-w-[17rem] text-balance text-right font-display text-[1.0625rem] italic leading-snug text-muted md:ml-0 md:max-w-none md:text-left md:text-[1.1875rem]">
              {footer.tagline}
            </p>

            {/* The links, set like the map's key: an italic term, then what it opens. */}
            <nav aria-label="Tautan Ciel" className="mt-[clamp(28px,3vw,40px)]">
              <dl className="grid grid-cols-[4.75rem_minmax(0,1fr)] items-baseline gap-x-4 text-[1.0625rem]">
                {footer.key.map((row) => (
                  <div key={row.term} className="col-span-2 grid grid-cols-subgrid items-baseline">
                    <dt className="font-display italic leading-7 text-muted">{row.term}</dt>
                    <dd className="flex flex-wrap gap-x-5">
                      {row.links.map((link) => (
                        <KeyLink key={link.href} link={link} />
                      ))}
                    </dd>
                  </div>
                ))}
              </dl>
            </nav>
          </div>

          {/* What a chart prints in its margin about its own data. */}
          <section
            aria-labelledby="sumber-peta"
            className="col-span-2 row-start-3 mt-[clamp(48px,10vw,56px)] md:col-span-1 md:col-start-1 md:row-start-2 md:mt-5 md:pr-[clamp(24px,4vw,64px)]"
          >
            <h2 id="sumber-peta" className="font-display text-[1.375rem] font-bold italic leading-tight text-ink">
              {footer.sourcesTitle}
            </h2>
            <p className="measure mt-2 text-[0.9375rem] text-muted">{footer.sourcesNote}</p>
            <ul className="mt-4 flex flex-col font-display text-[1.125rem] italic">
              {cases.map((c) => (
                <li key={c.id} className="flex min-h-9 flex-wrap items-center gap-x-2.5">
                  <KeyMark found={c.found} />
                  {c.found ? (
                    <>
                      <span className="text-ink">{c.chip}</span>
                      <span className="tabular text-muted">· {footer.found(c.sources.length)}</span>
                    </>
                  ) : (
                    <>
                      <s className="text-muted decoration-ink decoration-1">{c.chip}</s>
                      <span className="font-bold text-ink">{footer.notFound}</span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="mt-[clamp(40px,4.5vw,72px)] flex flex-wrap items-center justify-between gap-x-6 text-[0.9375rem] text-muted">
          <p className="flex min-h-11 items-center">
            {footer.copyright}&nbsp;·&nbsp;<span translate="no">{footer.domain}</span>
          </p>
          {/* Hovering or focusing it lights the route it leads back along (globals.css). */}
          <a href="#atas" data-back="" className="ink-link link-quiet">
            <span>{footer.backToTop}</span>
          </a>
        </div>
      </div>
    </footer>
  );
}
