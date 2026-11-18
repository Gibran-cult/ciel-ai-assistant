import { vi } from "vitest";

type Bag = Record<string, unknown>;

function area(data: Bag) {
  return {
    data,
    get: vi.fn(async (keys?: string | string[] | null) => {
      if (keys == null) return { ...data };
      const wanted = typeof keys === "string" ? [keys] : keys;
      return Object.fromEntries(wanted.filter((key) => key in data).map((key) => [key, data[key]]));
    }),
    set: vi.fn(async (items: Bag) => {
      Object.assign(data, items);
    }),
    remove: vi.fn(async (keys: string | string[]) => {
      for (const key of typeof keys === "string" ? [keys] : keys) delete data[key];
    }),
  };
}

/** chrome tiruan secukupnya untuk uji. Pasang dengan vi.stubGlobal("chrome", fakeChrome()). */
export function fakeChrome() {
  return {
    storage: { session: area({}), local: area({}) },
    identity: {
      getRedirectURL: vi.fn(() => "https://abcdefghijklmnop.chromiumapp.org/"),
      launchWebAuthFlow: vi.fn(async (_details: { url: string; interactive: boolean }): Promise<string | undefined> => undefined),
    },
    alarms: {
      create: vi.fn(async (_name: string, _info: { when?: number }) => undefined),
      clear: vi.fn(async (_name: string) => true),
      onAlarm: { addListener: vi.fn() },
    },
  };
}

export type FakeChrome = ReturnType<typeof fakeChrome>;

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
