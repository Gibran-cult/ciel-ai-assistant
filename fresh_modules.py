"""
Modul lokal yang tertinggal versi lama setelah deploy.

Streamlit Cloud memperbarui file app di proses yang sedang berjalan (git pull),
satu file per satu. Jika app.py tiba duluan, rerun-nya bisa mengimpor modul
lokal versi lama (misalnya payments.py) dan gagal dengan ImportError sampai
app di-reboot (live setelah PR #55 dan PR #76). app.py memanggil
drop_stale_modules sebelum mengimpor modul lokalnya: jika ada file .py di
folder app yang berubah sejak pemanggilan sebelumnya, semua modul lokal dibuang
dari sys.modules supaya impor berikutnya membaca file terbaru. Cara yang sama
dipakai file watcher Streamlit sendiri saat sebuah file lokal berubah.
"""

import os
import sys

_seen = {}


def _source_mtimes(folder):
    with os.scandir(folder) as entries:
        return {e.name: e.stat().st_mtime_ns for e in entries if e.name.endswith(".py") and e.is_file()}


def _in_folder(module, folder):
    path = getattr(module, "__file__", None)
    return bool(path) and os.path.dirname(os.path.realpath(path)) == folder


def drop_stale_modules(folder):
    """
    Buang modul lokal dari folder ini jika ada file .py yang berubah sejak
    pemanggilan terakhir. Kembalikan nama modul yang dibuang (urut).

    Waktu file dicatat sebelum modul diimpor, jadi file yang berubah di tengah
    impor paling buruk membuat modul dimuat ulang sekali lagi, tidak tertinggal.
    """

    folder = os.path.realpath(folder)
    current = _source_mtimes(folder)
    previous = _seen.get(folder)
    _seen[folder] = current

    if previous is None or previous == current:
        return []

    stale = sorted(
        name
        for name, module in list(sys.modules.items())
        if name not in ("__main__", __name__) and _in_folder(module, folder)
    )
    for name in stale:
        sys.modules.pop(name, None)
    return stale
