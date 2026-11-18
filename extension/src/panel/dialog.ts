import { type RefObject, useEffect } from "react";

/** Fokus awal di tombol aman, dan Escape menjawab "tidak". */
export function useSafeDialog(safe: RefObject<HTMLButtonElement | null>, onCancel: () => void, key: unknown): void {
  useEffect(() => {
    safe.current?.focus();
  }, [safe, key]);

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, [onCancel]);
}

/** Nilai teks dari prompt server, atau null. Isi server selalu ditampilkan sebagai teks biasa. */
export function textOf(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}
