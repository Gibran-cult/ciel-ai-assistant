import { expect, test } from "./fixtures";

// Temuan tinjauan 3A: token pembaruan ada di storage.local, yang bawaannya
// terbaca content script. Service worker menutup aksesnya saat mulai.
test("a script in a shop tab cannot read the refresh token", async ({ agent, context }) => {
  const shop = await agent.open("/");
  const worker = context.serviceWorkers()[0]!;

  const seen = await worker.evaluate(async (url) => {
    const [tab] = await chrome.tabs.query({ url });
    const [frame] = await chrome.scripting.executeScript({
      target: { tabId: tab!.id! },
      // Dunia terisolasi, sama dengan content script Ciel.
      func: async () => {
        try {
          const stored = await chrome.storage.local.get("refreshToken");
          return typeof stored.refreshToken === "string" ? "readable" : "empty";
        } catch {
          return "denied";
        }
      },
    });
    const own = await chrome.storage.local.get("refreshToken");
    return { fromPage: frame?.result, fromWorker: typeof own.refreshToken };
  }, "https://toko.test/*");

  expect(seen.fromWorker).toBe("string");
  expect(seen.fromPage).not.toBe("readable");
  await shop.close();
});
