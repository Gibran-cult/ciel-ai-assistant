// @vitest-environment node
import { vi } from "vitest";
import { showBadge } from "../src/badge";

test("badge is empty, ON, or ! when Ciel waits for you", async () => {
  const action = {
    setBadgeText: vi.fn(async (_details: { text: string }) => undefined),
    setBadgeBackgroundColor: vi.fn(async (_details: { color: string }) => undefined),
  };
  vi.stubGlobal("chrome", { action });

  await showBadge("running");
  await showBadge("paused");
  await showBadge("handover");
  await showBadge("idle");
  await showBadge("stopped");
  await showBadge("running", true);

  expect(action.setBadgeText.mock.calls.map(([details]) => details.text)).toEqual(["ON", "!", "!", "", "", "!"]);
  vi.unstubAllGlobals();
});
