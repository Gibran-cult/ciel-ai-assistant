import { render } from "@testing-library/react";
import { vi } from "vitest";
import type { PanelState } from "../src/controller";
import { App } from "../src/panel/App";

export const BASE: PanelState = {
  auth: "signed_in", loginFailed: false, connection: "ready", phase: "idle", dialog: null, log: [],
  needPermission: null, ended: null, instruction: "",
};

export function show(over: Partial<PanelState> = {}, currentTab: { id: number; url?: string } | null = { id: 7, url: "https://toko.test/daftar" }) {
  const send = vi.fn();
  const requestPermission = vi.fn(async () => true);
  const view = render(<App state={{ ...BASE, ...over }} send={send} currentTab={currentTab} requestPermission={requestPermission} />);
  return { send, requestPermission, view };
}

