// Mendeteksi pengguna mengambil alih tab tugas. Klik dan ketikan dari
// act.ts adalah event buatan (isTrusted false), jadi hanya masukan
// sungguhan dari pengguna yang dihitung. Service worker yang memutuskan
// apakah ini menjeda tugas.

const USER_EVENTS = ["pointerdown", "keydown"];

export function isUserInput(event: { isTrusted: boolean; type: string }): boolean {
  return event.isTrusted && USER_EVENTS.includes(event.type);
}

export function watchTakeover(doc: Document, report: () => void): () => void {
  let reported = false;

  const listener = (event: Event) => {
    if (!isUserInput(event) || reported) return;
    reported = true;
    report();
    // Lapor lagi paling cepat sedetik kemudian.
    setTimeout(() => (reported = false), 1000);
  };

  for (const type of USER_EVENTS) doc.addEventListener(type, listener, { capture: true, passive: true });
  return () => {
    for (const type of USER_EVENTS) doc.removeEventListener(type, listener, { capture: true });
  };
}
