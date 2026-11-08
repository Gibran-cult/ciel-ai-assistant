// A still of the robot in a section's pose, rendered from the same three.js scene. It fills the
// robot's place for visitors who never get the live 3D layer (reduced motion, no WebGL, or before the
// first move), and hides itself once the live robot takes over (html[data-robot="live"]). Its width
// stays under 41vw, so it never reaches behind the section's text column (the left 58%).
export default function RobotStill({ pose }: { pose: "palsu" }) {
  return (
    <img
      src={`/robot-${pose}.webp`}
      width={680}
      height={900}
      alt=""
      aria-hidden="true"
      loading="lazy"
      decoding="async"
      className="robot-still pointer-events-none absolute right-0 top-1/2 -z-10 h-[min(100svh,900px,54vw)] w-auto -translate-y-1/2"
    />
  );
}
