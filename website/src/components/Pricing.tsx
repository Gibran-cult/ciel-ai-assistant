import { links, pricing } from "@/content/site";

type Plan = (typeof pricing.plans)[number];

// A pen tick in the map's blue ink, one per feature.
function Tick() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="var(--blue-text)"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="mt-[5px] shrink-0"
    >
      <path d="M3.5 9.6c1.2 1 2.4 2.2 3.4 3.5C8.6 9.6 11.1 6.9 14.6 4.6" />
    </svg>
  );
}

function PlanContent({ plan }: { plan: Plan }) {
  // Each plan has one condition line: Gratis its hourly limit, Pro its one-time payment.
  const condition = plan.limit ?? plan.note;
  return (
    <>
      <h3 className="font-display text-[clamp(1.375rem,1.9vw,1.75rem)] font-bold leading-[1.15] tracking-[-0.01em]">{plan.name}</h3>
      <p className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {/* Force lining figures: old-style digits would make Rp0 look like Rpo. */}
        <span className="display tabular text-[clamp(2rem,3.9vw,3.5rem)]" style={{ fontFeatureSettings: '"lnum"' }}>
          {plan.price}
        </span>
        {plan.period ? <span className="text-muted">{plan.period}</span> : null}
      </p>
      {/* role="list" keeps the list announced in Safari, which drops list semantics once the markers are removed. */}
      <ul role="list" className="mt-8 grid gap-3">
        {plan.features.map((feature) => (
          <li key={feature} className="flex items-start gap-3">
            <Tick />
            <span className="text-pretty">{feature}</span>
          </li>
        ))}
      </ul>
      {condition ? <p className="mt-6 font-display italic text-muted">{condition}</p> : null}
      <a href={plan.href} className="btn-secondary mt-7">
        {plan.cta}
      </a>
    </>
  );
}

// Harga. Two plans side by side from 900px, each as wide as its own content. Gratis stands on the
// open night ground; Pro sits one tone up on a surface field because it is the paid plan for skripsi.
// The robot is off screen here (data-pose "away"), so the section uses the full width.
export default function Pricing() {
  return (
    <section id="harga" aria-labelledby="harga-judul" data-pose="away" className="relative z-[1] py-[clamp(88px,11vw,184px)]">
      <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)]">
        {/* Under 360px the heading drops to 2rem so it still fits in two lines. */}
        <h2 id="harga-judul" className="display text-[clamp(2.25rem,4.4vw,4rem)] max-[360px]:text-[2rem]">
          {pricing.heading}
        </h2>
        <p className="measure mt-6 text-pretty text-muted">{pricing.lede}</p>
        <a href={links.pricing} className="link-quiet mt-2 underline">
          {pricing.detailLink}
        </a>

        {/* Gratis takes the Pro field's padding as top space, so names, prices and lists line up across both plans. */}
        <div className="mt-[clamp(48px,6vw,96px)] flex flex-col gap-12 [--plan-pad:clamp(24px,3.6vw,56px)] min-[900px]:flex-row min-[900px]:items-start min-[900px]:gap-[clamp(32px,5vw,88px)]">
          {pricing.plans.map((plan) =>
            plan.id === "pro" ? (
              <div key={plan.id} className="rounded-[22px] bg-surface p-[var(--plan-pad)] min-[900px]:flex-auto">
                <PlanContent plan={plan} />
              </div>
            ) : (
              <div key={plan.id} className="min-[900px]:pt-[var(--plan-pad)]">
                <PlanContent plan={plan} />
              </div>
            ),
          )}
        </div>
      </div>
    </section>
  );
}
