// Semua teks panel. Bahasa mengikuti docs/design-system.md bagian 10.
// Kalimat aksi dan alasan diambil dari agent_log.py lewat vektor bersama,
// supaya panel dan log di web memakai kalimat yang sama.
import logText from "../shared/vectors/log_text.json";

export const ACTIONS = logText.actions as Record<string, string>;
export const REASONS = logText.reasons as Record<string, string>;

export const TEXT = {
  title: "Ciel Agent",
  signIn: "Masuk dengan Google",
  signInIntro: "Masuk dengan akun Google yang sama dengan web Ciel. Ciel hanya bekerja di tab yang kamu pilih.",
  signInFailed: "Login gagal. Coba lagi.",
  consentRequired: "Agent belum aktif untuk akun ini. Aktifkan dulu di web Ciel lewat Pengaturan > Agent, lalu masuk lagi di sini.",
  signOut: "Keluar",
  commandLabel: "Apa yang perlu Ciel kerjakan di tab ini?",
  commandHint: "Ciel menunjukkan rencananya dulu sebelum mulai.",
  tabUnreadable: "Ciel belum bisa melihat alamat tab ini, jadi tugas dimulai tanpa membaca halaman ini. Klik ikon Ciel di toolbar saat tab ini terbuka, lalu tekan Mulai.",
  start: "Mulai",
  edit: "Ubah",
  stop: "Stop",
  stopTitle: "Stop (Alt+Shift+S)",
  offline: "Koneksi putus. Ciel berhenti dulu sampai tersambung lagi.",
  connecting: "Menyambung ke Ciel…",
  updateRequired: "Versi ekstensi ini sudah terlalu lama. Perbarui ekstensi dulu.",
  originRefused: "Layanan menolak ekstensi ini. Pasang ulang ekstensi dari Chrome Web Store.",
  status: {
    idle: "Siap",
    running: "Ciel sedang bekerja",
    waiting: "Menunggu persetujuanmu",
    handover: "Giliranmu. Ciel tidak melihat tab ini.",
    paused: "Dijeda. Lanjutkan atau stop?",
    stopped: "Dihentikan",
  },
  planTitle: "Rencana Ciel",
  planStart: "Mulai di",
  planScope: "Situs yang akan dibuka",
  planKinds: "Yang akan dilakukan",
  planMode: "Cara kerja",
  modeAsk: "Tanya dulu",
  modeAskHint: "Setiap langkah yang mengubah sesuatu menunggu persetujuanmu.",
  modeAuto: "Jalan sendiri",
  modeAutoHint: "Ciel tetap bertanya untuk langkah berisiko.",
  cancel: "Batal",
  run: "Jalankan",
  skip: "Lewati",
  continue: "Lanjutkan",
  skipStep: "Batalkan langkah ini",
  handoverTitle: "Giliranmu",
  handoverNote: "Ciel tidak melihat tab ini sampai kamu menekan Lanjutkan.",
  pausedTitle: "Dijeda karena kamu memakai tab ini",
  pausedNote: "Ciel menunggu sampai kamu memilih. Aksi yang belum jalan tetap ditahan.",
  askLabel: "Jawabanmu",
  askSend: "Kirim jawaban",
  fromPage: "Alamat ini diambil dari isi halaman, bukan dari perintahmu.",
  lookalikeTarget: "Tujuan",
  lookalikeCopied: "Mirip dengan",
  typedText: "Teks yang akan diketik",
  fullAddress: "Alamat lengkap",
  widens: (what: string) => `Ini menambah ${what} ke lingkup tugas.`,
  risk: (level: string) => `Risiko ${level}`,
  permissionNeeded: (host: string) => `Ciel butuh izinmu untuk membaca dan mengisi halaman di ${host}.`,
  permissionButton: (host: string) => `Izinkan di ${host}`,
  logTitle: "Aktivitas tugas ini",
  logEmpty: "Belum ada aktivitas. Langkah yang dikerjakan Ciel akan tercatat di sini.",
  endTitle: { done: "Selesai", stopped: "Dihentikan", failed: "Gagal", refused: "Tugas tidak dimulai" } as Record<string, string>,
  endSteps: (steps: number) => `${steps} langkah dikerjakan.`,
  // Alasan tugas berakhir, dari agent_api/loop.py dan agent_api/ws.py.
  endReason: {
    bad_plan: "Ciel tidak bisa menyusun rencana yang aman untuk perintah ini. Coba tulis perintahnya dengan lebih jelas.",
    model_error: "Ciel sedang tidak bisa dihubungi. Coba lagi sebentar lagi.",
    unavailable: "Layanan Ciel sedang bermasalah. Coba lagi sebentar lagi.",
    client_gone: "Koneksi ke ekstensi terputus, jadi tugas dihentikan.",
    log_error: "Ada masalah di layanan Ciel, jadi tugas dihentikan.",
    switch_error: "Ada masalah di layanan Ciel, jadi tugas dihentikan.",
    internal_error: "Ada masalah di layanan Ciel, jadi tugas dihentikan.",
    plan_rejected: "Kamu memilih Ubah, jadi rencana ini tidak dijalankan.",
    stop: "Kamu menekan Stop.",
    busy: "Masih ada tugas lain yang berjalan.",
    bad_instruction: "Perintahnya kosong atau terlalu panjang.",
    agent_off: "Agent sedang dimatikan sementara.",
    cost_cap: "Batas pemakaian harian sudah tercapai. Coba lagi besok.",
    consent_required: "Agent belum aktif untuk akun ini. Aktifkan dulu di web Ciel lewat Pengaturan > Agent.",
  } as Record<string, string>,
  endCode: (reason: string) => `Kode: ${reason}`,
  dismiss: "Tutup",
};

/** Judul dialog konfirmasi: efeknya, berbentuk pertanyaan. */
export function confirmTitle(tool: string, target: string): string {
  const titles: Record<string, string> = {
    tab_open: `Buka ${target}?`,
    tab_click: `Klik di ${target}?`,
    tab_type: `Ketik di ${target}?`,
    tab_select: `Pilih opsi di ${target}?`,
    form_submit: `Kirim formulir di ${target}?`,
  };
  return titles[tool] ?? `Jalankan aksi di ${target}?`;
}

/** Tombol aksi mengulang efeknya, bukan "OK". */
export function confirmButton(tool: string): string {
  const labels: Record<string, string> = {
    tab_open: "Buka situs", tab_click: "Klik", tab_type: "Ketik", tab_select: "Pilih", form_submit: "Kirim formulir",
  };
  return labels[tool] ?? "Jalankan";
}

/** Kalimat preview di mode "Tanya dulu". */
export function previewSentence(tool: string, target: string, text: string | null, url: string | null): string {
  switch (tool) {
    case "tab_type":
      return `Ketik "${text ?? ""}" di ${target}`;
    case "tab_select":
      return `Pilih "${text ?? ""}" di ${target}`;
    case "tab_click":
      return `Klik di ${target}`;
    case "tab_open":
      return `Buka ${url ?? target}`;
    case "form_submit":
      return `Kirim formulir di ${target}`;
    default:
      return `${ACTIONS[tool] ?? "Jalankan aksi"} di ${target}`;
  }
}

export function reasonText(reason: string): string {
  return REASONS[reason] ?? logText.unknown_reason.replace("{reason}", reason);
}
