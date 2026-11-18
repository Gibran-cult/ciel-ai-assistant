import CtaLink from "@/components/CtaLink";
import ResearchMap from "@/components/ResearchMap";
import RobotBust from "@/components/RobotBust";
import RouteStrip from "@/components/RouteStrip";
import { hero, links } from "@/content/site";

// From 1024px the headline holds the top band and the chart sheet starts at about a third of the
// screen height, so the whole route and the robot's head above the sheet fit in the first screen.
export default function Hero() {
  return (
    <section id="peta" aria-labelledby="judul" data-pose="hero" className="relative z-[1]">
      <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)] pb-[clamp(72px,9vw,140px)] lg:pt-[clamp(20px,2.4vw,36px)]">
        {/* Phones and tablets: the robot's own block under the nav. The robot stands behind the route
            strip with its head above the strip's top edge, the same way it stands behind the sheet
            on wide screens (the strip's top cuts the bust frame at 63.4% of its height). */}
        <div className="relative h-[var(--hero-media-h)] lg:hidden" aria-hidden="true">
          <div className="absolute bottom-0 left-0 w-full max-w-[26rem]">
            <RobotBust
              anchor="mobile"
              className="absolute bottom-[calc(100%_-_var(--hero-media-h)*0.3144)] right-[4%] -z-10 aspect-[780/848] h-[calc(var(--hero-media-h)*0.86)]"
            />
            <RouteStrip className="block h-auto w-full" />
          </div>
        </div>

        <div className="mt-8 lg:mt-0 lg:min-h-[calc(36svh_-_9rem)]">
          <h1 id="judul" className="display text-[clamp(2.75rem,5.2vw,4.75rem)]">
            {hero.titleLines[0]}
            <br />
            {hero.titleLines[1]}
          </h1>
        </div>

        <div className="mt-8 lg:mt-6">
          <ResearchMap
            intro={
              <>
                <p className="measure text-[1.1875rem] text-ink">{hero.lede}</p>
                <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3">
                  <CtaLink href={links.login}>{hero.cta}</CtaLink>
                  <a className="link-quiet" href={links.app}>
                    {hero.alt}
                  </a>
                </div>
                <p className="mt-3 text-[0.9375rem] text-muted">{hero.note}</p>
              </>
            }
          />
        </div>
      </div>
    </section>
  );
}
