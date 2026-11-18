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

// Tab aktif di jendela panel ini. Alamatnya hanya terlihat kalau ekstensi
// boleh melihatnya (activeTab dari klik ikon, atau izin situs).
function useActiveTab(): { id: number; url?: string } | null {
  const [tab, setTab] = useState<{ id: number; url?: string } | null>(null);

  useEffect(() => {
    const refresh = async () => {
      const [active] = await chrome.tabs.query({ active: true, currentWindow: true });
      setTab(active?.id !== undefined ? { id: active.id, url: active.url } : null);
    };

    void refresh();
    const onActivated = () => void refresh();
    const onUpdated = (_id: number, change: { url?: string; status?: string }) => {
      if (change.url !== undefined || change.status === "complete") void refresh();
    };
    chrome.tabs.onActivated.addListener(onActivated);
    chrome.tabs.onUpdated.addListener(onUpdated);
    return () => {
      chrome.tabs.onActivated.removeListener(onActivated);
      chrome.tabs.onUpdated.removeListener(onUpdated);
    };
  }, []);

  return tab;
}

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

  const currentTab = useActiveTab();
  return <App state={state} send={send} currentTab={currentTab} requestPermission={ensurePermission} />;
}

createRoot(document.getElementById("root")!).render(<Root />);
