// Keadaan tugas di perangkat: berjalan, dijeda karena pengguna mengambil
// alih, serah terima, atau dihentikan. Stop bekerja di perangkat dulu:
// antrean dikosongkan dan tugas diakhiri di sini tanpa menunggu server,
// lalu pesan stop dikirim (atau ditahan Socket sampai tersambung lagi).

export type Phase = "idle" | "running" | "paused" | "handover" | "stopped";

export interface SessionView {
  phase: Phase;
}

export interface SessionDeps {
  socket: { sendStop(): boolean; answer(id: number, value: unknown): boolean };
  runner: { onAction(signed: unknown): Promise<void>; end(): void; taskTab: number | null };
  /** Jawab aksi dengan {ok: false} tanpa menyentuh tab. */
  refuse(signed: unknown, reason: "stopped" | "handover"): void;
  /** Perbarui badge, banner, dan panel. */
  show(view: SessionView): void;
}

export class Session {
  phase: Phase = "idle";
  private queue: unknown[] = [];
  private chain: Promise<void> = Promise.resolve();
  private handoverId: number | null = null;
  // Naik setiap stop atau tugas baru, supaya aksi dari masa sebelumnya tidak jalan.
  private epoch = 0;

  constructor(private deps: SessionDeps) {}

  private set(phase: Phase): void {
    this.phase = phase;
    this.deps.show({ phase });
  }

  begin(): void {
    this.epoch += 1;
    this.queue = [];
    this.handoverId = null;
    this.set("running");
  }

  onAction(signed: unknown): void {
    if (this.phase === "handover") {
      // Selama serah terima pembaca halaman mati.
      this.deps.refuse(signed, "handover");
      return;
    }

    if (this.phase !== "running" && this.phase !== "paused") {
      this.deps.refuse(signed, "stopped");
      return;
    }

    this.queue.push(signed);
    if (this.phase === "running") this.drain();
  }

  private drain(): void {
    const epoch = this.epoch;

    this.chain = this.chain.then(async () => {
      while (this.phase === "running" && this.epoch === epoch && this.queue.length > 0) {
        const next = this.queue.shift();

        try {
          await this.deps.runner.onAction(next);
        } catch {
          // Runner sudah menjawab {ok: false} untuk kegagalannya sendiri.
        }
      }
    });
  }

  /** Masukan sungguhan dari pengguna di sebuah tab. */
  takeover(tabId: number): void {
    if (this.phase === "running" && tabId === this.deps.runner.taskTab) this.set("paused");
  }

  /** Pengguna memilih Lanjutkan setelah mengambil alih. */
  resume(): void {
    if (this.phase !== "paused") return;
    this.set("running");
    this.drain();
  }

  onHandover(id: number): void {
    if (this.phase !== "running" && this.phase !== "paused") return;
    this.handoverId = id;
    this.set("handover");
  }

  /** Tombol "Lanjutkan" (true) atau "Batal" (false) di panel saat serah terima. */
  finishHandover(done: boolean): void {
    if (this.phase !== "handover" || this.handoverId === null) return;
    this.deps.socket.answer(this.handoverId, done);
    this.handoverId = null;
    this.set("running");
    this.drain();
  }

  stop(): void {
    this.epoch += 1;
    this.queue = [];
    this.handoverId = null;
    this.deps.runner.end();
    this.set("stopped");
    this.deps.socket.sendStop();
  }

  onEnd(): void {
    this.epoch += 1;
    this.queue = [];
    this.handoverId = null;
    this.deps.runner.end();
    this.set("idle");
  }

  /** Selesai menjalankan antrean saat ini (untuk uji). */
  idle(): Promise<void> {
    return this.chain;
  }
}
