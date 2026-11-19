import { act, fireEvent, screen } from "@testing-library/react";
import { show } from "./panel_helpers";

const CONFIRM = { tool: "tab_click", target: "toko.test", level: "R2", reason: "submits", widens: null, from_page: false,
  url: null, ref: 4, text: null, lookalike: null };

test("signed out: one sign-in button", () => {
  const { send } = show({ auth: "signed_out" });
  fireEvent.click(screen.getByRole("button", { name: "Masuk dengan Google" }));
  expect(send).toHaveBeenCalledWith({ type: "login" });
});

test("consent_required points to the agent settings on the web", () => {
  show({ auth: "consent_required" });
  expect(screen.getByText(/Pengaturan > Agent/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Masuk dengan Google" })).toBeTruthy();
});

test("signed in without a task: a command box and Mulai for the active tab", async () => {
  const { send } = show();
  fireEvent.change(screen.getByLabelText("Apa yang perlu Ciel kerjakan di tab ini?"), { target: { value: "Cari kaos polos" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Mulai" })));
  expect(send).toHaveBeenCalledWith({ type: "start", instruction: "Cari kaos polos", tabId: 7 });
});

test("running: status, log lines and an active Stop at the top", () => {
  const { send } = show({ phase: "running", log: [{ time: "10.42", action: "Mengklik", target: "toko.test", result: "Selesai" }] });
  expect(screen.getByText("Ciel sedang bekerja")).toBeTruthy();
  expect(screen.getByText("Mengklik")).toBeTruthy();
  const stop = screen.getByRole("button", { name: /Stop/ });
  expect(stop.hasAttribute("disabled")).toBe(false);
  expect(stop.getAttribute("title")).toContain("Alt+Shift+S");
  fireEvent.click(stop);
  expect(send).toHaveBeenCalledWith({ type: "stop" });
});

test("Stop stays visible without a task, but has nothing to stop", () => {
  show();
  expect(screen.getByRole("button", { name: /Stop/ }).hasAttribute("disabled")).toBe(true);
});

test("offline: the message shows and Stop still works", () => {
  const { send } = show({ phase: "running", connection: "closed" });
  expect(screen.getByText("Koneksi putus. Ciel berhenti dulu sampai tersambung lagi.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Stop/ }));
  expect(send).toHaveBeenCalledWith({ type: "stop" });
});

test("plan: numbered steps, scope, Tanya dulu by default, Mulai and Ubah", () => {
  const dialog = { kind: "plan" as const, id: 3, steps: ["Buka toko", "Cari kaos"], scope: { hosts: ["toko.test"], kinds: ["tab_open", "tab_type"], spend_cap: null, start_host: null } };
  const { send } = show({ phase: "running", dialog, instruction: "Cari kaos" });
  expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual(expect.arrayContaining(["Buka toko", "Cari kaos"]));
  expect(screen.getByText("toko.test")).toBeTruthy();
  expect((screen.getByLabelText("Tanya dulu") as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Mulai" }));
  expect(send).toHaveBeenLastCalledWith({ type: "answer", id: 3, value: "ask" });

  fireEvent.click(screen.getByLabelText("Jalan sendiri"));
  fireEvent.click(screen.getByRole("button", { name: "Mulai" }));
  expect(send).toHaveBeenLastCalledWith({ type: "answer", id: 3, value: "auto" });

  fireEvent.click(screen.getByRole("button", { name: "Ubah" }));
  expect(send).toHaveBeenLastCalledWith({ type: "answer", id: 3, value: null });
});

test("confirm: focus starts on Batal and Escape cancels", () => {
  const { send } = show({ phase: "running", dialog: { kind: "confirm", id: 5, prompt: CONFIRM } });
  expect(document.activeElement?.textContent).toBe("Batal");
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  expect(send).toHaveBeenLastCalledWith({ type: "answer", id: 5, value: false });
  fireEvent.click(screen.getByRole("button", { name: "Klik" }));
  expect(send).toHaveBeenLastCalledWith({ type: "answer", id: 5, value: true });
  expect(screen.getByRole("alertdialog", { name: "Klik di toko.test?" })).toBeTruthy();
  expect(screen.getByText("Aksi ini mengirim data, jadi butuh persetujuanmu.")).toBeTruthy();
});

test("server text is plain text: no script, no link", () => {
  const prompt = { ...CONFIRM, tool: "tab_type", text: "<script>alert(1)</script> [klik](https://evil.example)",
    url: "https://toko.test/a?b=<b>c</b>" };
  const { view } = show({ phase: "running", dialog: { kind: "confirm", id: 5, prompt } });
  expect(view.container.querySelector("script")).toBeNull();
  expect(view.container.querySelector("a")).toBeNull();
  expect(view.container.querySelector("b")).toBeNull();
  expect(view.container.textContent).toContain("<script>alert(1)</script> [klik](https://evil.example)");
  expect(view.container.textContent).toContain("https://toko.test/a?b=<b>c</b>");
});

test("a lookalike site shows both addresses side by side", () => {
  const prompt = { ...CONFIRM, tool: "tab_open", target: "shopee-promo.co.id", lookalike: "shopee.co.id", url: "https://shopee-promo.co.id/", from_page: true };
  show({ phase: "running", dialog: { kind: "confirm", id: 5, prompt } });
  expect(screen.getByText("shopee-promo.co.id", { selector: "code" })).toBeTruthy();
  expect(screen.getByText("shopee.co.id", { selector: "code" })).toBeTruthy();
  expect(screen.getByText("Alamat ini diambil dari isi halaman, bukan dari perintahmu.")).toBeTruthy();
});

test("ask mode shows a one-line preview with Jalankan and Lewati", () => {
  const prompt = { ...CONFIRM, tool: "tab_type", reason: "ask_mode", level: "R1", text: "kaos polos" };
  const { send } = show({ phase: "running", dialog: { kind: "confirm", id: 6, prompt } });
  expect(screen.getByText('Ketik "kaos polos" di toko.test')).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Jalankan" }));
  expect(send).toHaveBeenLastCalledWith({ type: "answer", id: 6, value: true });
  fireEvent.click(screen.getByRole("button", { name: "Lewati" }));
  expect(send).toHaveBeenLastCalledWith({ type: "answer", id: 6, value: false });
});

test("handover: Lanjutkan hands the tab back", () => {
  const prompt = { ...CONFIRM, tool: "tab_type", reason: "secret_field", level: "R3" };
  const { send } = show({ phase: "handover", dialog: { kind: "handover", id: 8, prompt } });
  expect(screen.getByText("Kolom ini meminta data rahasia, jadi kamu yang mengisinya sendiri.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Lanjutkan" }));
  expect(send).toHaveBeenLastCalledWith({ type: "handover_done", done: true });
});

test("ask: the question as text and an answer box", () => {
  const { send } = show({ phase: "running", dialog: { kind: "ask", id: 9, question: "Ukuran berapa? <b>M</b>" } });
  expect(screen.getByText("Ukuran berapa? <b>M</b>")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Jawabanmu"), { target: { value: "L" } });
  fireEvent.click(screen.getByRole("button", { name: "Kirim jawaban" }));
  expect(send).toHaveBeenLastCalledWith({ type: "answer", id: 9, value: "L" });
});

test("paused: Lanjutkan resumes", () => {
  const { send } = show({ phase: "paused" });
  fireEvent.click(screen.getByRole("button", { name: "Lanjutkan" }));
  expect(send).toHaveBeenLastCalledWith({ type: "resume" });
});

test("permission: the button asks Chrome from the click, then tells the worker", async () => {
  const { send, requestPermission } = show({ phase: "running", needPermission: "toko.test" });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Izinkan di toko.test" })));
  expect(requestPermission).toHaveBeenCalledWith("toko.test");
  expect(send).toHaveBeenLastCalledWith({ type: "permission_granted" });
});

test("the end report shows as plain text", () => {
  show({ ended: { status: "done", reason: null, steps: 3, report: "Kaos ada di keranjang. <img src=x>" } });
  expect(screen.getByText("Kaos ada di keranjang. <img src=x>")).toBeTruthy();
  expect(document.querySelector("img")).toBeNull();
});

test("a task that ends early says why", () => {
  show({ ended: { status: "failed", reason: "bad_plan", steps: 0, report: "" } });
  expect(screen.getByText(/tidak bisa menyusun rencana/)).toBeTruthy();
});

test("an unknown end reason still shows its code", () => {
  show({ ended: { status: "failed", reason: "baru_sekali", steps: 0, report: "" } });
  expect(screen.getByText("Kode: baru_sekali")).toBeTruthy();
});

test("task 3.27: Mulai asks for the open site first, then starts on that tab", async () => {
  const { send, requestPermission } = show();
  fireEvent.change(screen.getByLabelText("Apa yang perlu Ciel kerjakan di tab ini?"), { target: { value: "Isi nama" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Mulai" })));
  expect(requestPermission).toHaveBeenCalledWith("toko.test");
  expect(requestPermission.mock.invocationCallOrder[0]!).toBeLessThan(send.mock.invocationCallOrder[0]!);
  expect(send).toHaveBeenCalledWith({ type: "start", instruction: "Isi nama", tabId: 7 });
});

test("task 3.27: a tab without a readable https address starts without asking", async () => {
  const { send, requestPermission } = show({}, { id: 7 });
  fireEvent.change(screen.getByLabelText("Apa yang perlu Ciel kerjakan di tab ini?"), { target: { value: "Isi nama" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Mulai" })));
  expect(requestPermission).not.toHaveBeenCalled();
  expect(send).toHaveBeenCalledWith({ type: "start", instruction: "Isi nama", tabId: 7 });
});

test("task 3.27: the plan card names the site the task starts on", () => {
  show({ phase: "running", dialog: { kind: "plan", id: 3, steps: ["Isi nama"], scope: { hosts: ["toko.test"], kinds: ["tab_type"], spend_cap: 0, start_host: "toko.test" } } });
  expect(screen.getByText("Mulai di")).toBeTruthy();
  expect(screen.getAllByText("toko.test", { selector: "code" }).length).toBeGreaterThan(0);
});

test("review: a refused origin says what to do instead of 'koneksi putus'", () => {
  show({ connection: "origin_refused" });
  expect(screen.getByText("Layanan menolak ekstensi ini. Pasang ulang ekstensi dari Chrome Web Store.")).toBeTruthy();
});

test("review: Mulai never asks for permission on a blocked site", async () => {
  const { send, requestPermission } = show({}, { id: 7, url: "https://ib.klikbca.com/login" });
  fireEvent.change(screen.getByLabelText("Apa yang perlu Ciel kerjakan di tab ini?"), { target: { value: "Cek saldo" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Mulai" })));
  expect(requestPermission).not.toHaveBeenCalled();
  expect(send).toHaveBeenCalledWith({ type: "start", instruction: "Cek saldo", tabId: 7 });
});

test("review: a tab whose address Ciel cannot see says the task starts without that page", () => {
  show({}, { id: 7 });
  expect(screen.getByText(/Ciel belum bisa melihat alamat tab ini/)).toBeTruthy();
});

test("review: no such note when the tab can be read", () => {
  show();
  expect(screen.queryByText(/Ciel belum bisa melihat alamat tab ini/)).toBeNull();
});

test("groundwork review: a task that needs a blocked site says so and names it", () => {
  show({ ended: { status: "refused", reason: "blocked_host", steps: 0, report: "Situs yang selalu diblokir untuk agent: bca.co.id" } });
  expect(screen.getByText(/membutuhkan situs yang selalu diblokir/)).toBeTruthy();
  expect(screen.getByText(/Buka situs itu sendiri/)).toBeTruthy();
  expect(screen.getByText("Situs yang selalu diblokir untuk agent: bca.co.id")).toBeTruthy();
  expect(screen.queryByText(/Kode: blocked_host/)).toBeNull();
});
