import { contours, isobaths, islands, labelCurve, outline, smoothPath, start, VIEW, type Pt } from "@/lib/mapGeometry";

// The night map as a chart sheet, drawn in code: a graduated neatline, depth lines that cross the
// sheet, stippled land with names set along the coast, and a key for the three drafting symbols.
// Purely visual: every fact it shows is also in the HTML next to it, so the whole SVG is hidden
// from assistive technology.

export type MapPin = { at: Pt; n?: number; delayMs?: number };

type Props = {
  id: string;
  route?: Pt[];
  // 0..1 of the route drawn; transitions when `animate` is set.
  draw?: number;
  animate?: boolean;
  pins?: MapPin[];
  pinsVisible?: boolean;
  // A trail toward a source that does not exist, ending in a cross and a struck label. With
  // `origin` it was a different question from the main route: it starts at a ring of its own,
  // named, instead of looking like part of the same search.
  falseTrail?: { route: Pt[]; draw: number; label: string; note: string; visible: boolean; origin?: string };
  dimIslands?: string[];
  // Island names in viewBox units. A map shown smaller sets them larger so they stay readable.
  labelSize?: number;
  // Where the robot's light rests first. When set, the route takes its colour from the light and a
  // warm pool lies on the sheet; ResearchMap moves both by rewriting the gradients' centres.
  light?: Pt;
  className?: string;
};

const INNER = 12;
const coast = islands.map((isl) => ({
  ...isl,
  d: smoothPath(outline(isl), true),
  rings: contours(isl).map((r) => smoothPath(r, true)),
}));

// The graduated border: a band between two rules, filled in alternate steps like a chart's scale.
function Neatline() {
  const steps: string[] = [];
  const stepX = (VIEW.w - INNER * 2) / 18;
  const stepY = (VIEW.h - INNER * 2) / 10;
  for (let i = 0; i < 18; i += 2) {
    const x = INNER + i * stepX;
    steps.push(`M${x} 6h${stepX}v6h${-stepX}Z`, `M${x} ${VIEW.h - 12}h${stepX}v6h${-stepX}Z`);
  }
  for (let i = 1; i < 10; i += 2) {
    const y = INNER + i * stepY;
    steps.push(`M6 ${y}h6v${stepY}h-6Z`, `M${VIEW.w - 12} ${y}h6v${stepY}h-6Z`);
  }
  return (
    <g>
      <path d={steps.join("")} fill="var(--muted)" fillOpacity="0.32" />
      <rect x="6" y="6" width={VIEW.w - 12} height={VIEW.h - 12} fill="none" stroke="var(--muted)" strokeOpacity="0.55" strokeWidth="1" />
      <rect x={INNER} y={INNER} width={VIEW.w - INNER * 2} height={VIEW.h - INNER * 2} fill="none" stroke="var(--muted)" strokeOpacity="0.4" strokeWidth="1" />
    </g>
  );
}

// The key, lower right: ring for the question, dot for a source that was found, cross for one that
// does not exist. Sized from the label size so it reads at the same scale as the island names.
function Key({ size }: { size: number }) {
  const fs = Math.round(size * 0.9);
  const row = Math.round(fs * 1.5);
  const w = Math.round(fs * 10.2);
  const h = Math.round(fs * 0.9 + row * 3 + fs * 0.9);
  const x = VIEW.w - INNER - 14 - w;
  const y = VIEW.h - INNER - 14 - h;
  const sx = x + fs * 1.1;
  const tx = x + fs * 2.2;
  const rowY = (i: number) => y + fs * 1.55 + row * (i + 0.5);
  const text = { font: `italic 400 ${fs}px var(--font-alegreya), Georgia, serif` };
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} fill="var(--surface)" stroke="var(--muted)" strokeOpacity="0.45" strokeWidth="1" />
      <text x={x + fs * 0.75} y={y + fs * 1.25} fill="var(--text)" style={{ font: `italic 700 ${fs}px var(--font-alegreya), Georgia, serif` }}>
        Keterangan
      </text>
      <circle cx={sx} cy={rowY(0) - fs * 0.32} r={fs * 0.32} fill="var(--bg)" stroke="var(--yellow)" strokeWidth="2" />
      <text x={tx} y={rowY(0)} fill="var(--muted)" style={text}>
        pertanyaanmu
      </text>
      <circle cx={sx} cy={rowY(1) - fs * 0.32} r={fs * 0.26} fill="var(--yellow)" />
      <text x={tx} y={rowY(1)} fill="var(--muted)" style={text}>
        sumber ditemukan
      </text>
      <path
        d={`M${sx - fs * 0.3} ${rowY(2) - fs * 0.62}l${fs * 0.6} ${fs * 0.6}m0 ${-fs * 0.6}l${-fs * 0.6} ${fs * 0.6}`}
        stroke="var(--muted)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <text x={tx} y={rowY(2)} fill="var(--muted)" style={text}>
        sumber tidak ada
      </text>
    </g>
  );
}

export default function MapArt({
  id,
  route,
  draw = 1,
  animate = false,
  pins = [],
  pinsVisible = true,
  falseTrail,
  dimIslands = [],
  labelSize = 22,
  light,
  className,
}: Props) {
  const routeD = route ? smoothPath(route) : "";
  const trailD = falseTrail ? smoothPath(falseTrail.route) : "";
  const crossAt = falseTrail?.route[falseTrail.route.length - 1];
  const drawTransition = animate ? "stroke-dashoffset 1.5s var(--ease-out)" : "none";
  const small = Math.round(labelSize * 0.95);

  return (
    <svg viewBox={`0 0 ${VIEW.w} ${VIEW.h}`} className={className} aria-hidden="true" focusable="false">
      <defs>
        <pattern id={`${id}-stipple`} width="9" height="9" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="0.95" fill="var(--muted)" opacity="0.3" />
          <circle cx="6.5" cy="6.2" r="0.7" fill="var(--muted)" opacity="0.22" />
        </pattern>
        <clipPath id={`${id}-sheet`}>
          <rect x={INNER} y={INNER} width={VIEW.w - INNER * 2} height={VIEW.h - INNER * 2} />
        </clipPath>
        {coast.map((isl) => (
          <path key={isl.id} id={`${id}-name-${isl.id}`} d={labelCurve(isl, labelSize)} />
        ))}
        {light && (
          <>
            {/* The route is brightest where the light falls and stays readable everywhere else. */}
            <radialGradient id={`${id}-lit`} data-light="" gradientUnits="userSpaceOnUse" cx={light[0]} cy={light[1]} r="240">
              <stop offset="0" stopColor="var(--yellow-hi)" />
              <stop offset="0.55" stopColor="var(--yellow)" />
              <stop offset="1" stopColor="var(--yellow)" stopOpacity="0.55" />
            </radialGradient>
            <radialGradient id={`${id}-pool`} data-light="" gradientUnits="userSpaceOnUse" cx={light[0]} cy={light[1]} r="240">
              <stop offset="0" stopColor="var(--yellow)" stopOpacity="0.13" />
              <stop offset="1" stopColor="var(--yellow)" stopOpacity="0" />
            </radialGradient>
          </>
        )}
        {routeD && (
          <mask id={`${id}-route`} maskUnits="userSpaceOnUse" x="0" y="0" width={VIEW.w} height={VIEW.h}>
            <path
              d={routeD}
              pathLength={1}
              fill="none"
              stroke="#fff"
              strokeWidth="10"
              strokeDasharray="1"
              strokeDashoffset={1 - draw}
              style={{ transition: drawTransition }}
            />
          </mask>
        )}
        {trailD && (
          <mask id={`${id}-trail`} maskUnits="userSpaceOnUse" x="0" y="0" width={VIEW.w} height={VIEW.h}>
            <path
              d={trailD}
              pathLength={1}
              fill="none"
              stroke="#fff"
              strokeWidth="10"
              strokeDasharray="1"
              strokeDashoffset={1 - (falseTrail?.draw ?? 0)}
              style={{ transition: drawTransition }}
            />
          </mask>
        )}
      </defs>

      <rect width={VIEW.w} height={VIEW.h} fill="var(--surface)" />

      <g clipPath={`url(#${id}-sheet)`}>
        {isobaths.map((d, i) => (
          <path key={i} d={d} fill="none" stroke="var(--muted)" strokeOpacity="0.16" strokeWidth="1" strokeDasharray="1 5" strokeLinecap="round" />
        ))}

        {coast.map((isl) => {
          const dim = dimIslands.includes(isl.id);
          // A dimmed island fades its land; its name only steps back a little, so it stays above
          // 4.5:1 on the sheet.
          return (
            <g key={isl.id}>
              <g opacity={dim ? 0.45 : 1} style={{ transition: "opacity 500ms var(--ease-out)" }}>
                <path d={isl.d} fill="var(--surface-2)" />
                <path d={isl.d} fill={`url(#${id}-stipple)`} />
                {isl.rings.map((r, i) => (
                  <path key={i} d={r} fill="none" stroke="var(--muted)" strokeOpacity={0.2 - i * 0.03} strokeWidth="0.9" />
                ))}
                <path d={isl.d} fill="none" stroke="var(--muted)" strokeOpacity="0.55" strokeWidth="1.2" />
              </g>
              <text
                fill="var(--muted)"
                opacity={dim ? 0.8 : 1}
                style={{ font: `italic 400 ${labelSize}px var(--font-alegreya), Georgia, serif`, transition: "opacity 500ms var(--ease-out)" }}
              >
                <textPath href={`#${id}-name-${isl.id}`} startOffset="50%" textAnchor="middle">
                  {isl.label}
                </textPath>
              </text>
            </g>
          );
        })}

        {light && <rect width={VIEW.w} height={VIEW.h} fill={`url(#${id}-pool)`} />}
      </g>

      {trailD && (
        <path
          d={trailD}
          fill="none"
          stroke="var(--muted)"
          strokeWidth="2"
          strokeDasharray="4 8"
          strokeLinecap="round"
          mask={`url(#${id}-trail)`}
        />
      )}
      {routeD && (
        <path
          d={routeD}
          fill="none"
          stroke={light ? `url(#${id}-lit)` : "var(--yellow)"}
          strokeWidth="2.4"
          strokeDasharray="6 7"
          strokeLinecap="round"
          mask={`url(#${id}-route)`}
        />
      )}

      <g>
        <circle cx={start[0]} cy={start[1]} r="8" fill="var(--bg)" stroke="var(--yellow)" strokeWidth="2.4" />
        <text x={start[0] - 6} y={start[1] - 20} fill="var(--text)" style={{ font: `italic 700 ${labelSize + 2}px var(--font-alegreya), Georgia, serif` }}>
          Pertanyaanmu
        </text>
      </g>

      {pins.map((p, i) => (
        // The outer group reveals the pin (with its delay); the inner one follows the light at once,
        // so the light never restarts the reveal's transition.
        <g
          key={`${p.at[0]}-${p.at[1]}-${i}`}
          style={{
            opacity: pinsVisible ? 1 : 0,
            transform: pinsVisible ? "scale(1)" : "scale(0.6)",
            transformOrigin: `${p.at[0]}px ${p.at[1]}px`,
            transition: animate ? `opacity 400ms var(--ease-out) ${p.delayMs ?? 0}ms, transform 400ms var(--ease-out) ${p.delayMs ?? 0}ms` : "none",
          }}
        >
          <g data-pin={`${p.at[0]},${p.at[1]}`} style={{ opacity: "calc(0.6 + 0.4 * var(--lit, 1))" }}>
            <circle cx={p.at[0]} cy={p.at[1]} r="12" fill="none" stroke="var(--yellow)" strokeOpacity="0.4" strokeWidth="1.5" />
            <circle cx={p.at[0]} cy={p.at[1]} r="5.5" fill="var(--yellow)" />
            {p.n !== undefined && (
              <text x={p.at[0] + 15} y={p.at[1] - 12} fill="var(--text)" style={{ font: `700 ${small}px var(--font-alegreya-sans), system-ui, sans-serif` }}>
                [{p.n}]
              </text>
            )}
          </g>
        </g>
      ))}

      {falseTrail && crossAt && (
        <g
          style={{
            opacity: falseTrail.visible ? 1 : 0,
            transition: animate ? "opacity 400ms var(--ease-out) 900ms" : "none",
          }}
        >
          {falseTrail.origin && (
            <>
              <circle cx={falseTrail.route[0][0]} cy={falseTrail.route[0][1]} r="6.5" fill="var(--bg)" stroke="var(--yellow)" strokeWidth="2" />
              <text
                x={falseTrail.route[0][0] - 8}
                y={falseTrail.route[0][1] - 16}
                fill="var(--muted)"
                style={{ font: `italic 400 ${small}px var(--font-alegreya), Georgia, serif` }}
              >
                {falseTrail.origin}
              </text>
            </>
          )}
          <path
            d={`M${crossAt[0] - 8} ${crossAt[1] - 8} L${crossAt[0] + 8} ${crossAt[1] + 8} M${crossAt[0] + 8} ${crossAt[1] - 8} L${crossAt[0] - 8} ${crossAt[1] + 8}`}
            stroke="var(--muted)"
            strokeWidth="2.6"
            strokeLinecap="round"
          />
          <text x={crossAt[0] - 8} y={crossAt[1] + small + 18} fill="var(--muted)" style={{ font: `italic 400 ${small}px var(--font-alegreya), Georgia, serif` }}>
            {falseTrail.label}
          </text>
          <line
            x1={crossAt[0] - 10}
            y1={crossAt[1] + small * 0.62 + 18}
            x2={crossAt[0] - 6 + falseTrail.label.length * small * 0.42}
            y2={crossAt[1] + small * 0.62 + 18}
            stroke="var(--muted)"
            strokeWidth="1.6"
          />
          <text x={crossAt[0] - 8} y={crossAt[1] + small * 2.25 + 22} fill="var(--text)" style={{ font: `italic 700 ${small}px var(--font-alegreya), Georgia, serif` }}>
            {falseTrail.note}
          </text>
        </g>
      )}

      <Key size={labelSize} />
      <Neatline />
    </svg>
  );
}
