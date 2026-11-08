import { Fragment } from "react";
import RobotStill from "@/components/RobotStill";
import { fakeJournal } from "@/content/site";

// The struck line quotes the authors, year and journal straight from the request, so the drawing
// always names the reference the test asked about. A copy edit that breaks this fails the build.
const cited = fakeJournal.request.match(/karya (?<authors>.+? \(\d{4}\)), (?<journal>Jurnal .+?) Vol\./)?.groups;
if (!cited) {
  throw new Error("FakeJournal: fakeJournal.request no longer names the authors, year and journal.");
}
const reference = `${cited.authors}, ${cited.journal}`;

// The test as a case file: the request, the trail it set off (a short route that ends at a cross),
// Ciel's reply, how to read it, and a few facts about the app (fakeJournal.facts). From 1024px up
// the robot stands on the right and shakes its head (Motion.tsx); it never crosses behind text, so
// everything here sits in the left 58%.
export default function FakeJournal() {
  return (
    <section
      id="uji-jurnal-palsu"
      aria-labelledby="uji-jurnal-palsu-judul"
      data-pose="palsu"
      className="relative z-[1] py-[clamp(88px,11vw,184px)]"
    >
      <RobotStill pose="palsu" />
      <div className="mx-auto w-full max-w-[1440px] px-[var(--gutter)]">
        <div className="lg:w-[58%]">
          <h2 id="uji-jurnal-palsu-judul" className="display text-[clamp(2.25rem,4.4vw,4rem)] text-ink">
            {fakeJournal.heading}
          </h2>
          <p className="measure mt-6 text-pretty text-muted">{fakeJournal.lede}</p>

          <div className="mt-12 rounded-[20px] bg-surface px-5 py-6 sm:rounded-3xl sm:px-8 sm:py-8 lg:mt-14 lg:px-10 lg:py-9">
            <blockquote className="measure text-pretty text-muted">
              <p>{fakeJournal.request}</p>
            </blockquote>

            {/* The disproved trail: a ring for the question, the route in yellow, and the cross. The
                cross sits level with the strike on the first line of the struck reference. */}
            <div className="mt-4 flex items-start gap-3">
              <svg width="60" height="66" viewBox="0 0 60 66" fill="none" aria-hidden="true" className="shrink-0">
                <circle cx="8" cy="9" r="6" stroke="var(--text)" strokeWidth="2" />
                {/* pathLength makes the dash pattern end on a dash, right at the cross. */}
                <path
                  d="M8 19C8 39 19 56 43 58"
                  stroke="var(--yellow)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeDasharray="6 7"
                  pathLength={58}
                />
                <path d="M47 53l10 10M57 53l-10 10" stroke="var(--text)" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <p className="min-w-0 pt-[42px] font-display text-[1.125rem] leading-7 text-muted">
                <s className="line-through decoration-ink decoration-2">{reference}</s>{" "}
                <span className="ml-1 inline-block -rotate-3 text-[1.25rem] italic">tidak ada</span>
              </p>
            </div>
          </div>

          <blockquote className="mt-12 lg:mt-14">
            <p className="font-display text-[clamp(1.5rem,3vw,2.25rem)] leading-[1.2] font-semibold tracking-[-0.01em] text-balance text-ink">
              {fakeJournal.reply}
            </p>
            <p className="measure mt-4 text-pretty text-muted">{fakeJournal.followUp}</p>
          </blockquote>

          <p className="measure mt-12 text-pretty text-ink lg:mt-14">{fakeJournal.explain}</p>
          <p className="measure mt-3 text-base text-muted">{fakeJournal.caption}</p>

          <dl
            aria-label="Keterangan"
            className="mt-12 grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-3 sm:gap-x-10 lg:mt-16"
          >
            {fakeJournal.facts.map(({ k, v }) => (
              <Fragment key={k}>
                <dt className="text-muted">{k}</dt>
                <dd className="text-ink">{v}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
