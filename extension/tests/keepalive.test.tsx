import { renderHook } from "@testing-library/react";
import { vi } from "vitest";
import { useKeepalive } from "../src/panel/keepalive";

test("review: the panel keeps the service worker awake while a task is active", () => {
  vi.useFakeTimers();
  const post = vi.fn();
  const { rerender, unmount } = renderHook(({ active }) => useKeepalive(active, post), { initialProps: { active: true } });
  vi.advanceTimersByTime(61_000);
  expect(post).toHaveBeenCalledTimes(3);
  expect(post).toHaveBeenCalledWith({ type: "keepalive" });

  rerender({ active: false });
  vi.advanceTimersByTime(60_000);
  expect(post).toHaveBeenCalledTimes(3);
  unmount();
  vi.useRealTimers();
});
