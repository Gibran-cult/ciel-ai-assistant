// Service worker Ciel Agent. Satu-satunya tempat token disegarkan (lihat auth.ts).
import { handleAlarm } from "./auth";

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => undefined);
chrome.alarms.onAlarm.addListener(handleAlarm);
