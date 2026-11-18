import { render } from "@testing-library/react";
import { vi } from "vitest";
import type { PanelState } from "../src/controller";
import { App } from "../src/panel/App";

export const BASE: PanelState = {
  auth: "signed_in", loginFailed: false, connection: "ready", phase: "idle", dialog: null, log: [],
  needPermission: null, ended: null, instruction: "",
};

export function show(over: Partial<PanelState> = {}) {
  const send = vi.fn();
  const requestPermission = vi.fn(async () => true);
  const view = render(<App state={{ ...BASE, ...over }} send={send} activeTab={async () => 7} requestPermission={requestPermission} />);
  return { send, requestPermission, view };
}

