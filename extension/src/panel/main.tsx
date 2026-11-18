import { createRoot } from "react-dom/client";
import { useCallback, useEffect, useState } from "react";
import type { PanelCommand, PanelState } from "../controller";
import { ensurePermission } from "../permissions";
import { App } from "./App";
import { useKeepalive } from "./keepalive";
import "./panel.css";

const INITIAL: PanelState = {
  auth: "unknown", loginFailed: false, connection: "connecting", phase: "idle", dialog: null, log: [],
  needPermission: null, ended: null, instruction: "",
};

// Panel tersambung ke service worker lewat satu port. Semua keadaan datang
// dari sana; panel hanya menampilkan dan mengirim perintah.
function Root() {
  const [state, setState] = useState<PanelState>(INITIAL);
  const [port, setPort] = useState<chrome.runtime.Port | null>(null);

  useEffect(() => {
    let current: chrome.runtime.Port | null = null;
    let closed = false;

    const connect = () => {
      current = chrome.runtime.connect({ name: "panel" });
      current.onMessage.addListener((message: { type?: string; state?: PanelState }) => {
        if (message?.type === "state" && message.state) setState(message.state);
      });
      // Service worker bisa berhenti; sambung lagi.
      current.onDisconnect.addListener(() => {
        if (!closed) setTimeout(connect, 500);
      });
      setPort(current);
    };

    connect();
    return () => {
      closed = true;
      current?.disconnect();
    };
  }, []);

  const send = useCallback((command: PanelCommand) => port?.postMessage(command), [port]);
  useKeepalive(state.phase !== "idle", send);

  const activeTab = async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    return tab?.id ?? null;
  };

  return <App state={state} send={send} activeTab={activeTab} requestPermission={ensurePermission} />;
}

createRoot(document.getElementById("root")!).render(<Root />);
