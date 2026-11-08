import CtaLink from "@/components/CtaLink";
import RobotBust from "@/components/RobotBust";
import { closing, links } from "@/content/site";

// The route's last waypoint before the footer: the yellow dashed line arrives from the left edge
// and stops at a ring where the page asks for the one action; the footer carries it on to the
// Kepingan ring of the nameplate. From 1024px the robot stands
// at the section's lower right, its chest behind the footer's top edge, so it scrolls away with the
// section instead of being cut by the footer; it turns toward the button on hover or focus. The box
// sits 6% of its height below the section, so the cut stays under the footer even while scrolling.
export default function Closing() {
  return (
    <section
      id="mulai"
      aria-labelledby="mulai-judul"
      data-pose="closing"
      className="relative z-[1] flex items-center py-[clamp(88px,11vw,184px)] lg:min-h-[86svh]"
    >
      <RobotBust
        anchor="closing"
        src="/robot-bust-closing.webp"
        eager={false}
        className="absolute bottom-0 right-[max(var(--gutter),calc((100%_-_1440px)/2_+_var(--gutter)))] -z-10 hidden aspect-[780/848] h-[min(80%,680px)] translate-y-[6%] lg:block"
      />
      <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)]">
        <div className="lg:w-[55%]">
          <svg
            viewBox="0 0 520 64"
            className="-ml-[var(--gutter)] h-auto w-[min(100%+var(--gutter),520px)] max-w-none"
            aria-hidden="true"
            focusable="false"
          >
            <path
              d="M0 46 C120 46 170 14 290 18 S430 40 486 32"
              fill="none"
              stroke="var(--yellow)"
              strokeWidth="2.4"
              strokeDasharray="6 7"
              strokeLinecap="round"
            />
            <circle cx="500" cy="30" r="11" fill="var(--bg)" stroke="var(--yellow)" strokeWidth="2.4" />
            <circle cx="500" cy="30" r="4" fill="var(--yellow)" />
          </svg>

          <h2 id="mulai-judul" className="display mt-8 text-[clamp(2.75rem,6.2vw,5.5rem)]">
            {closing.heading}
          </h2>
          <p className="measure mt-6 max-w-[34rem] text-[1.1875rem] text-ink">{closing.lede}</p>
          <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3">
            <CtaLink href={links.login}>{closing.cta}</CtaLink>
            <a className="link-quiet" href={links.app}>
              {closing.alt}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
