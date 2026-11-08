import { faq } from "@/content/site";

// Tanya jawab as marginal notes. From 1024px the heading holds the left margin (sticky at 96px)
// while the six questions scroll past on the right. Native <details>, so it works without JavaScript.
export default function Faq() {
  return (
    <section
      id="tanya-jawab"
      aria-labelledby="tanya-jawab-judul"
      data-pose="away"
      className="relative z-[1] py-[clamp(88px,11vw,184px)]"
    >
      <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)] lg:grid lg:grid-cols-12 lg:gap-x-6">
        <h2
          id="tanya-jawab-judul"
          className="display text-[clamp(2.25rem,4.4vw,4rem)] lg:sticky lg:top-[96px] lg:col-span-4 lg:self-start"
        >
          {faq.heading}
        </h2>

        {/* As wide as the answer measure, so each plus/minus ends where its answer ends. On desktop the
            negative top margin lines the first question up with the heading's cap height. */}
        <div className="mt-8 flex max-w-[62ch] flex-col gap-3 lg:col-span-7 lg:col-start-6 lg:-mt-3">
          {faq.items.map((item) => (
            <details key={item.q} className="group">
              {/* The hover tone bleeds into the gutter, so the question stays flush with its answer. */}
              <summary className="group/q -mx-3 min-h-11 list-none rounded-md px-3 py-3.5 transition-[background-color] duration-150 ease-out-expo [-webkit-tap-highlight-color:transparent] hover:bg-surface-2 focus-visible:bg-surface-2 active:bg-surface-2 sm:-mx-4 sm:px-4 [&::-webkit-details-marker]:hidden">
                <span className="flex items-start justify-between gap-4 font-display text-[1.5rem] leading-[1.3] tracking-[-0.01em] text-ink italic">
                  <span className="text-balance">{item.q}</span>
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    aria-hidden="true"
                    className="mt-[0.15em] shrink-0 text-muted transition-colors duration-150 ease-out-expo group-open:text-ink group-hover/q:text-ink group-focus-visible/q:text-ink"
                  >
                    <path d="M6 12h12" />
                    {/* Open: the upright stroke turns onto the flat one, so the plus becomes a minus. */}
                    <path
                      d="M12 6v12"
                      className="origin-center transition-transform duration-300 ease-out-expo [transform-box:fill-box] group-open:rotate-90"
                    />
                  </svg>
                </span>
              </summary>
              <p className="max-w-[62ch] pt-1 pb-6 text-pretty text-muted">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
