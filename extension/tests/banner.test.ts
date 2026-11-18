import { afterEach, vi } from "vitest";
import { BANNER_TEXT, mountBanner, onStopClick, unmountBanner } from "../src/content/banner";

let roots: ShadowRoot[] = [];
const original = Element.prototype.attachShadow;

function spyShadow() {
  roots = [];
  vi.spyOn(Element.prototype, "attachShadow").mockImplementation(function (this: Element, init: ShadowRootInit) {
    const root = original.call(this, init);
    roots.push(root);
    return root;
  });
}

const tick = () => new Promise((done) => setTimeout(done, 0));

afterEach(() => {
  unmountBanner(document);
  vi.restoreAllMocks();
  document.documentElement.innerHTML = "<head></head><body></body>";
});

test("the banner lives in a closed shadow root the page cannot reach", () => {
  spyShadow();
  mountBanner(document, "active");
  const host = document.querySelector("ciel-agent-banner")!;
  expect(host).not.toBeNull();
  expect(host.shadowRoot).toBeNull();
  expect(Element.prototype.attachShadow).toHaveBeenCalledWith({ mode: "closed" });
  expect(roots[0]!.textContent).toContain("Tab ini sedang dikontrol Ciel");
  const stop = roots[0]!.querySelector("button")!;
  expect(stop.textContent).toContain("Stop");
  expect(stop.getAttribute("title")).toContain("Alt+Shift+S");
});

test("each mode has its own text, and stopped has no Stop button", () => {
  spyShadow();
  mountBanner(document, "handover");
  expect(roots[0]!.textContent).toContain("Giliranmu. Ciel tidak melihat tab ini.");
  mountBanner(document, "stopped");
  expect(roots[0]!.textContent).toContain(BANNER_TEXT.stopped);
  expect(roots[0]!.querySelector("button")).toBeNull();
  expect(document.querySelectorAll("ciel-agent-banner")).toHaveLength(1);
});

test("removing the banner puts it back", async () => {
  mountBanner(document, "active");
  document.querySelector("ciel-agent-banner")!.remove();
  await tick();
  expect(document.querySelector("ciel-agent-banner")).not.toBeNull();
});

test("a style attribute set by the page is wiped", async () => {
  mountBanner(document, "active");
  const host = document.querySelector("ciel-agent-banner")!;
  host.setAttribute("style", "display:none !important");
  await tick();
  expect(host.getAttribute("style")).toBeNull();
});

test("the page is pushed down instead of covered, and restored afterwards", () => {
  document.documentElement.style.marginTop = "5px";
  mountBanner(document, "active");
  expect(document.documentElement.style.getPropertyValue("margin-top")).not.toBe("5px");
  unmountBanner(document);
  expect(document.documentElement.style.marginTop).toBe("5px");
  expect(document.querySelector("ciel-agent-banner")).toBeNull();
});

test("only a real click on Stop reaches the service worker", () => {
  const send = vi.fn();
  onStopClick({ isTrusted: false } as Event, send);
  expect(send).not.toHaveBeenCalled();
  onStopClick({ isTrusted: true } as Event, send);
  expect(send).toHaveBeenCalledWith({ type: "stop" });
});
