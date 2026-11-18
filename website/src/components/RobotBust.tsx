// A still bust of the robot, rendered from the same three.js scene: what the visitor sees before
// the live 3D layer loads (and the only robot under reduced motion or without WebGL), and the box
// the live robot fits itself to (RobotStage reads [data-robot-anchor]). It always stands behind
// something that hides the cut through its chest: the map sheet, the route strip or the footer.
// It is drawn under the page content and hidden from assistive technology.
type Props = {
  anchor: "hero" | "mobile" | "closing";
  className: string;
  src?: string;
  // The hero's bust is the first screen's largest image; the closing one waits until it is near.
  eager?: boolean;
};

export default function RobotBust({ anchor, className, src = "/robot-bust.webp", eager = true }: Props) {
  return (
    <div data-robot-anchor={anchor} aria-hidden="true" className={`robot-bust pointer-events-none ${className}`}>
      <img
        src={src}
        width={780}
        height={848}
        alt=""
        fetchPriority={eager ? "high" : "auto"}
        loading={eager ? "eager" : "lazy"}
        decoding="async"
        className="block h-full w-full"
      />
    </div>
  );
}
