// Content script: disuntikkan hanya ke tab tugas (runner.ts). Menyediakan
// pembaca dan pelaksana aksi untuk service worker. Kalau disuntik dua kali
// di halaman yang sama, yang pertama dipakai supaya nomor rujukan tetap.
import { act } from "./act";
import { observe } from "./reader";

const scope = globalThis as { cielAgent?: { act: typeof act; observe: typeof observe } };
scope.cielAgent ??= Object.freeze({ act, observe });
