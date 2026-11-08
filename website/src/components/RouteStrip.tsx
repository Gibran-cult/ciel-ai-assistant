import { smoothPath, type Pt } from "@/lib/mapGeometry";

// Phones and tablets: a strip of the chart along the bottom of the robot's block, so the first
// screen already shows the mechanism while the robot looks down at it from behind: a question routed
// to four numbered sources, and below it the fake-journal test, a separate question in the same
// test, whose trail ends at a cross. Decorative; the full map and its facts follow below.

const ring: Pt = [26, 42];
const found: Pt[] = [[90, 62], [148, 36], [208, 60], [268, 38]];
const aside: Pt = [22, 92];
const cross: Pt = [44, 112];
const label = "Hendrawan & Sulistyo (2019)";
const labelW = label.length * 5.5;

export default function RouteStrip({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 360 128" className={className} aria-hidden="true" focusable="false">
      <rect width="360" height="128" fill="var(--surface)" />
      <rect x="3.5" y="3.5" width="353" height="121" fill="none" stroke="var(--muted)" strokeOpacity="0.5" strokeWidth="1" />

      <path d={smoothPath([ring, ...found])} fill="none" stroke="var(--yellow)" strokeWidth="2" strokeDasharray="5 6" strokeLinecap="round" />
      <circle cx={ring[0]} cy={ring[1]} r="6.5" fill="var(--bg)" stroke="var(--yellow)" strokeWidth="2" />
      <text x="14" y="24" fill="var(--text)" style={{ font: "italic 700 15px var(--font-alegreya), Georgia, serif" }}>
        Pertanyaanmu
      </text>
      {found.map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r="9" fill="none" stroke="var(--yellow)" strokeOpacity="0.4" strokeWidth="1.2" />
          <circle cx={x} cy={y} r="4.2" fill="var(--yellow)" />
          <text x={x + 10} y={y - 9} fill="var(--text)" style={{ font: "700 13px var(--font-alegreya-sans), system-ui, sans-serif" }}>
            [{i + 1}]
          </text>
        </g>
      ))}

      <path d={smoothPath([aside, [26, 104], cross])} fill="none" stroke="var(--muted)" strokeWidth="1.6" strokeDasharray="3 6" strokeLinecap="round" />
      <circle cx={aside[0]} cy={aside[1]} r="5" fill="var(--bg)" stroke="var(--yellow)" strokeWidth="1.6" />
      <text x={aside[0] + 12} y={aside[1] + 4} fill="var(--muted)" style={{ font: "italic 400 12.5px var(--font-alegreya), Georgia, serif" }}>
        Uji jurnal palsu
      </text>
      <path d={`M${cross[0] - 5} ${cross[1] - 5}l10 10m0 -10l-10 10`} stroke="var(--muted)" strokeWidth="2" strokeLinecap="round" />
      <text x={cross[0] + 14} y={cross[1] + 5} fill="var(--muted)" style={{ font: "italic 400 13px var(--font-alegreya), Georgia, serif" }}>
        {label}
      </text>
      <line x1={cross[0] + 12} y1={cross[1]} x2={cross[0] + 16 + labelW} y2={cross[1]} stroke="var(--muted)" strokeWidth="1.2" />
      <text x={cross[0] + 24 + labelW} y={cross[1] + 5} fill="var(--text)" style={{ font: "italic 700 13px var(--font-alegreya), Georgia, serif" }}>
        tidak ada
      </text>
    </svg>
  );
}
